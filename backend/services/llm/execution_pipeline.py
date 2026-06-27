"""
backend/services/llm/execution_pipeline.py
============================================
LLM request orchestration pipeline.

Pipeline stages (in order)
---------------------------
PromptManager   → Render the final prompt from template + variables.
CacheManager    → Return cached response if available (short-circuit).
RetryHandler    → Wrap the client call with exponential back-off.
BaseLLMClient   → Execute the provider API call.
ResponseParser  → Parse JSON / extract text from the raw response.
UsageTracker    → Record token usage, latency, cost, and cache metrics.

Design decisions
----------------
* The pipeline is the **only** place where these six infrastructure classes
  collaborate.  They are injected at construction time (DI) and never
  instantiated inside the class.
* :class:`LLMService` is the sole caller of the pipeline; no router or
  agent should touch it directly.
* The pipeline is stateless between calls — it holds no request context.
* Caching is applied *after* prompt rendering so the cache key reflects the
  final, rendered prompt (not the template name).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Type, TypeVar

from pydantic import BaseModel

from backend.services.llm.base_client import BaseLLMClient, LLMRequest, LLMRawResponse
from backend.services.llm.cache_manager import CacheManager
from backend.services.llm.config import LLMConfig, get_llm_config
from backend.services.llm.exceptions import LLMBaseError, LLMRetryExhaustedError
from backend.services.llm.prompt_manager import PromptManager
from backend.services.llm.response_parser import ResponseParser
from backend.services.llm.retry_handler import RetryHandler
from backend.services.llm.usage_tracker import UsageStats, UsageTracker

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Pipeline request / response DTOs
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PipelineRequest:
    """
    Input specification for a single pipeline execution.

    Parameters
    ----------
    template_name:      Name of the prompt template to render (without extension).
                        Mutually exclusive with ``raw_prompt``.
    raw_prompt:         Use this pre-built prompt string directly (skip
                        PromptManager rendering).  Mutually exclusive with
                        ``template_name``.
    template_variables: Key-value pairs forwarded to :meth:`PromptManager.render`.
    system_prompt:      Optional system / instruction prefix.
    response_format:    ``"text"`` or ``"json"`` — controls which client method
                        is called and whether ResponseParser runs.
    temperature:        Per-request temperature override.
    max_tokens:         Per-request max-tokens override.
    cache_enabled:      Set to ``False`` to bypass cache for this request.
    cache_ttl:          Per-request TTL override (seconds); ``None`` → default.
    metadata:           Arbitrary key-value pairs forwarded to tracking.
    """

    template_name: str | None = None
    raw_prompt: str | None = None
    template_variables: dict[str, Any] = field(default_factory=dict)
    system_prompt: str | None = None
    response_format: str = "text"         # "text" | "json"
    temperature: float | None = None
    max_tokens: int | None = None
    cache_enabled: bool = True
    cache_ttl: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.template_name is None and self.raw_prompt is None:
            raise ValueError(
                "PipelineRequest requires either 'template_name' or 'raw_prompt'."
            )
        if self.template_name and self.raw_prompt:
            raise ValueError(
                "PipelineRequest accepts 'template_name' OR 'raw_prompt', not both."
            )


@dataclass(slots=True)
class PipelineResponse:
    """
    Output from a single pipeline execution.

    Parameters
    ----------
    text:           The raw text returned by the provider.
    parsed:         Parsed Python dict/list (only set when response_format="json").
    model:          Model name used.
    provider:       Provider identifier.
    prompt_tokens:  Tokens in the rendered prompt.
    output_tokens:  Tokens in the completion.
    latency_ms:     End-to-end wall-clock time (pipeline level, not just the API).
    from_cache:     Whether the response was served from the cache.
    """

    text: str
    parsed: dict[str, Any] | list[Any] | None
    model: str
    provider: str
    prompt_tokens: int
    output_tokens: int
    latency_ms: float
    from_cache: bool = False


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class LLMExecutionPipeline:
    """
    Orchestrates the end-to-end LLM request lifecycle.

    All six infrastructure collaborators are injected via the constructor
    following the Dependency Inversion Principle.

    Parameters
    ----------
    client:         Concrete :class:`BaseLLMClient` implementation to use.
    prompt_manager: :class:`PromptManager` instance.
    cache_manager:  :class:`CacheManager` instance.
    retry_handler:  :class:`RetryHandler` instance.
    response_parser::class:`ResponseParser` instance.
    usage_tracker:  :class:`UsageTracker` instance.
    config:         :class:`LLMConfig` instance.
    """

    def __init__(
        self,
        client: BaseLLMClient,
        prompt_manager: PromptManager,
        cache_manager: CacheManager,
        retry_handler: RetryHandler,
        response_parser: ResponseParser,
        usage_tracker: UsageTracker,
        config: LLMConfig | None = None,
    ) -> None:
        self._client = client
        self._prompt_manager = prompt_manager
        self._cache_manager = cache_manager
        self._retry_handler = retry_handler
        self._response_parser = response_parser
        self._usage_tracker = usage_tracker
        self._config: LLMConfig = config or get_llm_config()

        logger.info(
            "LLMExecutionPipeline ready — provider=%s",
            client.provider_name,
        )

    # ── Public API ──────────────────────────────────────────────────────────

    async def run(self, request: PipelineRequest) -> PipelineResponse:
        """
        Execute the full pipeline for ``request``.

        Stages
        ------
        1. Render prompt (PromptManager or raw pass-through).
        2. Build cache key → check cache.
        3. If cache miss → execute client call via RetryHandler.
        4. Store response in cache.
        5. Parse response if JSON mode.
        6. Record usage metrics.

        Parameters
        ----------
        request:    :class:`PipelineRequest` describing the LLM call.

        Returns
        -------
        PipelineResponse

        Raises
        ------
        LLMRetryExhaustedError
            If all retry attempts fail.
        LLMJSONParseError
            If ``response_format="json"`` and parsing fails.
        LLMBaseError
            For any other LLM-layer error.
        """
        pipeline_start = time.monotonic()

        # ── Stage 1: Render prompt ──────────────────────────────────────────
        prompt = self._render_prompt(request)

        # ── Stage 2: Cache lookup ───────────────────────────────────────────
        cache_key = CacheManager.build_key(
            prompt=prompt,
            provider=self._client.provider_name,
            model=self._config.active_model_name,
            extra={
                "format": request.response_format,
                "temperature": request.temperature,
            },
        )

        from_cache = False
        raw_response: LLMRawResponse | None = None

        if request.cache_enabled:
            cached_text = await self._cache_manager.get(cache_key)
            if cached_text is not None:
                from_cache = True
                logger.debug("Pipeline cache hit — key=%.12s…", cache_key)
                raw_response = LLMRawResponse(
                    text=cached_text,
                    model=self._config.active_model_name,
                    provider=self._client.provider_name,
                    finish_reason="CACHE",
                )

        # ── Stage 3: Client call (with retry) ──────────────────────────────
        if raw_response is None:
            llm_request = LLMRequest(
                prompt=prompt,
                system_prompt=request.system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format=request.response_format,
                metadata=request.metadata,
            )

            client_fn = (
                self._client.generate_json
                if request.response_format == "json"
                else self._client.generate
            )

            raw_response = await self._retry_handler.execute(client_fn, llm_request)

            # ── Stage 4: Cache store ────────────────────────────────────────
            if request.cache_enabled:
                await self._cache_manager.set(
                    cache_key, raw_response.text, ttl=request.cache_ttl
                )

        # ── Stage 5: Response parsing ───────────────────────────────────────
        parsed: dict[str, Any] | list[Any] | None = None
        if request.response_format == "json":
            parsed = self._response_parser.parse_json(raw_response.text)

        # ── Stage 6: Usage tracking ─────────────────────────────────────────
        pipeline_latency_ms = (time.monotonic() - pipeline_start) * 1000
        success = raw_response is not None

        await self._usage_tracker.record(
            model=raw_response.model,
            provider=raw_response.provider,
            prompt_tokens=raw_response.prompt_tokens,
            output_tokens=raw_response.output_tokens,
            latency_ms=pipeline_latency_ms,
            success=success,
            from_cache=from_cache,
            metadata=request.metadata,
        )

        logger.info(
            "Pipeline complete — provider=%s model=%s from_cache=%s "
            "tokens=%d+%d latency=%.1fms",
            raw_response.provider,
            raw_response.model,
            from_cache,
            max(raw_response.prompt_tokens, 0),
            max(raw_response.output_tokens, 0),
            pipeline_latency_ms,
        )

        return PipelineResponse(
            text=raw_response.text,
            parsed=parsed,
            model=raw_response.model,
            provider=raw_response.provider,
            prompt_tokens=raw_response.prompt_tokens,
            output_tokens=raw_response.output_tokens,
            latency_ms=pipeline_latency_ms,
            from_cache=from_cache,
        )

    async def get_stats(self) -> UsageStats:
        """
        Return aggregate usage statistics from :class:`UsageTracker`.

        Returns
        -------
        UsageStats
        """
        return await self._usage_tracker.get_stats()

    async def health_check(self) -> dict[str, bool]:
        """
        Run provider health check and return a status dict.

        Returns
        -------
        dict[str, bool]
            e.g. ``{"gemini": True}``
        """
        ok = await self._client.health_check()
        return {self._client.provider_name: ok}

    # ── Private helpers ─────────────────────────────────────────────────────

    def _render_prompt(self, request: PipelineRequest) -> str:
        """
        Stage 1: Produce the final prompt string.

        If ``template_name`` is set, delegates to :class:`PromptManager`.
        If ``raw_prompt`` is set, returns it directly.
        """
        if request.raw_prompt:
            return request.raw_prompt

        # template_name is guaranteed non-None here (validated in __post_init__)
        return self._prompt_manager.render(
            request.template_name,  # type: ignore[arg-type]
            **request.template_variables,
        )
