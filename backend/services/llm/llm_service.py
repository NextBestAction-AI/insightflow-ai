"""
backend/services/llm/llm_service.py
=====================================
Public entry point for the entire LLM infrastructure layer.

Contract
--------
* This is the **only** class that AI agents, routers, and other services
  should import from the LLM layer.
* It exposes a clean, domain-oriented public API.
* It **never** communicates directly with any LLM SDK.
* It **never** implements retry logic, caching, or JSON parsing.
* Every method body currently raises ``NotImplementedError``; it will be
  fleshed out in the AI-agent implementation phase.

Dependency injection
--------------------
All collaborators are injected via :meth:`__init__` or the factory
function :func:`create_llm_service`.  Callers should use the factory
rather than instantiating the class directly.

Usage
-----
    from backend.services.llm import create_llm_service

    llm = create_llm_service()
    result = await llm.generate_text(raw_prompt="Summarise this text …")
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.llm.config import LLMConfig, LLMProvider, get_llm_config
from backend.services.llm.cache_manager import CacheManager
from backend.services.llm.execution_pipeline import (
    LLMExecutionPipeline,
    PipelineRequest,
    PipelineResponse,
)
from backend.services.llm.prompt_manager import PromptManager
from backend.services.llm.response_parser import ResponseParser
from backend.services.llm.retry_handler import RetryHandler
from backend.services.llm.usage_tracker import UsageStats, UsageTracker

logger = logging.getLogger(__name__)


class LLMService:
    """
    Domain-facing façade for all LLM operations.

    Parameters
    ----------
    pipeline:
        Pre-built :class:`LLMExecutionPipeline` (all collaborators already
        wired together).  Use :func:`create_llm_service` to build a
        correctly-configured instance.

    Public methods
    --------------
    * :meth:`understand_interaction`    – Analyse a conversation turn.
    * :meth:`analyze_risks`             – Surface risk signals.
    * :meth:`assess_health`             – Compute / explain a health score.
    * :meth:`generate_recommendations`  – Produce actionable suggestions.
    * :meth:`explain_decision`          – Justify an agent decision.
    * :meth:`summarize_conversation`    – Condense a thread.
    * :meth:`analyze_sentiment`         – Classify tone / sentiment.
    * :meth:`generate_text`             – Generic text generation.
    * :meth:`parse_json`                – Extract JSON from LLM output.
    * :meth:`get_stats`                 – Return usage / performance stats.
    """

    def __init__(self, pipeline: LLMExecutionPipeline) -> None:
        self._pipeline = pipeline
        logger.info("LLMService initialised.")

    # =========================================================================
    # Domain methods
    # All bodies raise NotImplementedError; implement during agent phase.
    # =========================================================================

    async def understand_interaction(
        self,
        conversation: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyse a customer interaction and extract structured intent,
        entities, and key topics.

        Parameters
        ----------
        conversation:   Raw conversation transcript or message.
        context:        Optional contextual metadata (customer tier, history, …).

        Returns
        -------
        dict[str, Any]
            Structured representation of the interaction.

        Raises
        ------
        NotImplementedError
            Until the agent-phase implementation is complete.
        """
        raise NotImplementedError(
            "understand_interaction() will be implemented in the agent phase."
        )

    async def analyze_risks(
        self,
        customer_data: dict[str, Any],
        *,
        risk_categories: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Identify and rank risk signals from customer data.

        Parameters
        ----------
        customer_data:      Health scores, usage metrics, support tickets, etc.
        risk_categories:    Optional list of risk types to focus on.

        Returns
        -------
        dict[str, Any]
            Ranked risk signals with confidence scores and reasoning.

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError(
            "analyze_risks() will be implemented in the agent phase."
        )

    async def assess_health(
        self,
        customer_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Assess the overall health of a customer account.

        Parameters
        ----------
        customer_data:  Aggregated customer metrics.

        Returns
        -------
        dict[str, Any]
            Health assessment with score, trend, and narrative explanation.

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError(
            "assess_health() will be implemented in the agent phase."
        )

    async def generate_recommendations(
        self,
        context: dict[str, Any],
        *,
        max_recommendations: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Generate prioritised, actionable recommendations for a CS rep.

        Parameters
        ----------
        context:                 Aggregated signals (risks, health, history).
        max_recommendations:     Maximum number of items to return.

        Returns
        -------
        list[dict[str, Any]]
            Ordered list of recommendation objects.

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError(
            "generate_recommendations() will be implemented in the agent phase."
        )

    async def explain_decision(
        self,
        decision: str,
        supporting_data: dict[str, Any],
    ) -> str:
        """
        Produce a human-readable explanation of an agent decision.

        Parameters
        ----------
        decision:           The decision or recommendation to explain.
        supporting_data:    Evidence / signals the decision was based on.

        Returns
        -------
        str
            A plain-language justification.

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError(
            "explain_decision() will be implemented in the agent phase."
        )

    async def summarize_conversation(
        self,
        conversation: str,
        *,
        max_sentences: int = 5,
    ) -> str:
        """
        Produce a concise summary of a conversation thread.

        Parameters
        ----------
        conversation:   Full conversation transcript.
        max_sentences:  Approximate length of the summary.

        Returns
        -------
        str
            Plain-text summary.

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError(
            "summarize_conversation() will be implemented in the agent phase."
        )

    async def analyze_sentiment(
        self,
        text: str,
    ) -> dict[str, Any]:
        """
        Classify the sentiment and tone of a piece of text.

        Parameters
        ----------
        text:   Customer message, email, or support ticket body.

        Returns
        -------
        dict[str, Any]
            e.g. ``{"sentiment": "negative", "confidence": 0.87, "tone": ["frustrated"]}``

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError(
            "analyze_sentiment() will be implemented in the agent phase."
        )

    # =========================================================================
    # Generic / utility methods — these WILL call the pipeline
    # =========================================================================

    async def generate_text(
        self,
        *,
        template_name: str | None = None,
        raw_prompt: str | None = None,
        template_variables: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        cache_enabled: bool = True,
    ) -> PipelineResponse:
        """
        Generate free-form text via the execution pipeline.

        This is the preferred low-level generation method for use inside
        the agent phase (domain methods above will delegate here).

        Parameters
        ----------
        template_name:       Prompt template file name (without extension).
        raw_prompt:          Pre-built prompt string (skip PromptManager).
        template_variables:  Variables forwarded to PromptManager.render().
        system_prompt:       Optional instruction prefix.
        temperature:         Override default temperature.
        max_tokens:          Override default max tokens.
        cache_enabled:       Set ``False`` to bypass the cache.

        Returns
        -------
        PipelineResponse

        Raises
        ------
        ValueError
            If neither ``template_name`` nor ``raw_prompt`` is provided.
        LLMBaseError
            For any LLM-layer error.
        """
        logger.debug(
            "generate_text — template=%s raw_prompt_len=%s",
            template_name,
            len(raw_prompt) if raw_prompt else None,
        )
        request = PipelineRequest(
            template_name=template_name,
            raw_prompt=raw_prompt,
            template_variables=template_variables or {},
            system_prompt=system_prompt,
            response_format="text",
            temperature=temperature,
            max_tokens=max_tokens,
            cache_enabled=cache_enabled,
        )
        return await self._pipeline.run(request)

    async def parse_json(
        self,
        *,
        template_name: str | None = None,
        raw_prompt: str | None = None,
        template_variables: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        cache_enabled: bool = True,
    ) -> dict[str, Any] | list[Any]:
        """
        Generate a structured JSON response via the execution pipeline and
        return the parsed Python object.

        Parameters
        ----------
        Same as :meth:`generate_text` — all parameters are forwarded.

        Returns
        -------
        dict | list
            The parsed JSON structure.

        Raises
        ------
        LLMJSONParseError
            If the model's output cannot be parsed as valid JSON.
        LLMBaseError
            For any other LLM-layer error.
        """
        logger.debug(
            "parse_json — template=%s raw_prompt_len=%s",
            template_name,
            len(raw_prompt) if raw_prompt else None,
        )
        request = PipelineRequest(
            template_name=template_name,
            raw_prompt=raw_prompt,
            template_variables=template_variables or {},
            system_prompt=system_prompt,
            response_format="json",
            temperature=temperature,
            max_tokens=max_tokens,
            cache_enabled=cache_enabled,
        )
        response = await self._pipeline.run(request)
        return response.parsed  # type: ignore[return-value]

    async def get_stats(self) -> dict[str, Any]:
        """
        Return a serialisable snapshot of LLM usage statistics.

        Aggregates metrics from :class:`UsageTracker` via the pipeline.

        Returns
        -------
        dict[str, Any]
            Fields: total_requests, successful_requests, failed_requests,
            cache_hits, cache_misses, total_tokens, total_cost_usd,
            avg_latency_ms, success_rate, cache_hit_rate.
        """
        stats: UsageStats = await self._pipeline.get_stats()
        return {
            "total_requests":       stats.total_requests,
            "successful_requests":  stats.successful_requests,
            "failed_requests":      stats.failed_requests,
            "cache_hits":           stats.cache_hits,
            "cache_misses":         stats.cache_misses,
            "total_prompt_tokens":  stats.total_prompt_tokens,
            "total_output_tokens":  stats.total_output_tokens,
            "total_tokens":         stats.total_tokens,
            "total_cost_usd":       stats.total_cost_usd,
            "avg_latency_ms":       stats.avg_latency_ms,
            "min_latency_ms":       stats.min_latency_ms,
            "max_latency_ms":       stats.max_latency_ms,
            "success_rate":         round(stats.success_rate, 4),
            "cache_hit_rate":       round(stats.cache_hit_rate, 4),
        }

    async def health_check(self) -> dict[str, Any]:
        """
        Run a connectivity test against the active LLM provider.

        Returns
        -------
        dict[str, Any]
            e.g. ``{"status": "healthy", "providers": {"gemini": True}}``
        """
        provider_status = await self._pipeline.health_check()
        all_healthy = all(provider_status.values())
        return {
            "status": "healthy" if all_healthy else "degraded",
            "providers": provider_status,
        }


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def create_llm_service(config: LLMConfig | None = None) -> LLMService:
    """
    Build and return a fully-wired :class:`LLMService` instance.

    This factory is the **recommended** way to obtain an ``LLMService``.
    It reads the active provider from :class:`LLMConfig` and assembles the
    entire dependency graph.

    Parameters
    ----------
    config:
        :class:`LLMConfig` to use.  Defaults to the process-level singleton.

    Returns
    -------
    LLMService

    Raises
    ------
    LLMConfigurationError
        If the active provider is unknown.
    """
    cfg = config or get_llm_config()

    # ── Select concrete client ──────────────────────────────────────────────
    if cfg.llm_model_type == LLMProvider.GEMINI:
        from backend.services.llm.gemini_client import GeminiClient
        client = GeminiClient(config=cfg)
    elif cfg.llm_model_type == LLMProvider.OPENAI:
        from backend.services.llm.openai_client import OpenAIClient
        client = OpenAIClient(config=cfg)
    else:
        from backend.services.llm.exceptions import LLMConfigurationError
        raise LLMConfigurationError(
            f"Unknown LLM provider: '{cfg.llm_model_type}'. "
            f"Set LLM_MODEL_TYPE to 'gemini' or 'openai'."
        )

    # ── Build collaborators ─────────────────────────────────────────────────
    prompt_manager  = PromptManager()
    cache_manager   = CacheManager(ttl=cfg.llm_cache_ttl, max_size=cfg.llm_cache_max_size)
    retry_handler   = RetryHandler(
        max_retries=cfg.llm_max_retries,
        base_delay=cfg.llm_retry_base_delay,
        max_delay=cfg.llm_retry_max_delay,
    )
    response_parser = ResponseParser()
    usage_tracker   = UsageTracker()

    # ── Assemble pipeline ───────────────────────────────────────────────────
    pipeline = LLMExecutionPipeline(
        client=client,
        prompt_manager=prompt_manager,
        cache_manager=cache_manager,
        retry_handler=retry_handler,
        response_parser=response_parser,
        usage_tracker=usage_tracker,
        config=cfg,
    )

    logger.info(
        "LLMService created — provider=%s model=%s",
        cfg.llm_model_type.value,
        cfg.active_model_name,
    )
    return LLMService(pipeline=pipeline)
