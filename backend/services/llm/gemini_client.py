"""
backend/services/llm/gemini_client.py
=======================================
Google Gemini provider client.

Responsibilities (this class only)
------------------------------------
* Initialise and authenticate with the Gemini SDK.
* Translate :class:`LLMRequest` → Gemini SDK call parameters.
* Execute the SDK call and capture timing.
* Translate the SDK response → :class:`LLMRawResponse`.
* Catch and re-raise Gemini-specific exceptions as LLM-layer exceptions.

Explicitly NOT responsible for
--------------------------------
* Retry logic             → handled by :class:`RetryHandler`
* Response caching        → handled by :class:`CacheManager`
* Token accounting        → handled by :class:`UsageTracker`
* JSON validation         → handled by :class:`ResponseParser`
* Prompt rendering        → handled by :class:`PromptManager`
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import google.generativeai as genai
import google.api_core.exceptions as google_exceptions

from backend.services.llm.base_client import BaseLLMClient, LLMRawResponse, LLMRequest
from backend.services.llm.config import LLMConfig, get_llm_config
from backend.services.llm.exceptions import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

_PROVIDER = "gemini"


class GeminiClient(BaseLLMClient):
    """
    Concrete LLM client implementation for Google Gemini.

    Parameters
    ----------
    config:
        :class:`LLMConfig` instance injected at construction time.
        Defaults to the process-level singleton.

    Thread safety
    -------------
    The underlying ``google.generativeai`` SDK is **not** thread-safe for
    concurrent configuration changes.  This class is safe to use from a
    single async event loop via ``asyncio.to_thread``.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        super().__init__(provider_name=_PROVIDER)
        self._config: LLMConfig = config or get_llm_config()
        self._model: genai.GenerativeModel | None = None  # lazy-initialised
        self._authenticate()

    # ── Initialisation ──────────────────────────────────────────────────────

    def _authenticate(self) -> None:
        """Configure the Gemini SDK with the API key from :attr:`_config`."""
        api_key = self._config.gemini_api_key
        if not api_key:
            raise LLMAuthenticationError(
                "GEMINI_API_KEY is not set. "
                "Set it in the environment or .env file.",
                details={"provider": _PROVIDER},
            )
        genai.configure(api_key=api_key)
        logger.info(
            "Gemini SDK authenticated — model=%s", self._config.gemini_model
        )

    def _get_model(
        self,
        *,
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> genai.GenerativeModel:
        """
        Return (or build) the :class:`genai.GenerativeModel` instance.

        A new model object is created whenever ``system_prompt`` or
        ``json_mode`` differ from the cached model to avoid mutating shared
        state.
        """
        generation_config: dict[str, Any] = {
            "temperature": self._config.llm_temperature,
            "max_output_tokens": self._config.llm_max_tokens,
        }
        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        return genai.GenerativeModel(
            model_name=self._config.gemini_model,
            generation_config=genai.types.GenerationConfig(**generation_config),
            system_instruction=system_prompt,
        )

    # ── Private SDK call executor ───────────────────────────────────────────

    def _call_sdk(
        self,
        model: genai.GenerativeModel,
        prompt: str,
        request: LLMRequest,
    ) -> LLMRawResponse:
        """
        Execute a synchronous Gemini SDK call and return a raw response DTO.

        This method is intentionally synchronous so it can be run safely
        inside ``asyncio.to_thread`` without holding the event loop.

        Parameters
        ----------
        model:    Pre-configured ``GenerativeModel`` instance.
        prompt:   Fully-rendered prompt string.
        request:  Original request (for metadata pass-through).

        Returns
        -------
        LLMRawResponse

        Raises
        ------
        LLMAuthenticationError, LLMRateLimitError, LLMTimeoutError,
        LLMProviderError
        """
        generation_config_override: dict[str, Any] = {}
        if request.temperature is not None:
            generation_config_override["temperature"] = request.temperature
        if request.max_tokens is not None:
            generation_config_override["max_output_tokens"] = request.max_tokens

        config_arg = (
            genai.types.GenerationConfig(**generation_config_override)
            if generation_config_override
            else None
        )

        start = time.monotonic()
        try:
            response = model.generate_content(
                prompt,
                generation_config=config_arg,
                request_options={"timeout": self._config.llm_timeout},
            )
        except google_exceptions.Unauthenticated as exc:
            raise LLMAuthenticationError(
                "Gemini API key is invalid or expired.",
                details={"provider": _PROVIDER, "original": str(exc)},
            ) from exc
        except google_exceptions.ResourceExhausted as exc:
            raise LLMRateLimitError(
                "Gemini quota exceeded. Back off and retry.",
                provider=_PROVIDER,
                status_code=429,
                details={"original": str(exc)},
            ) from exc
        except google_exceptions.DeadlineExceeded as exc:
            raise LLMTimeoutError(
                f"Gemini request timed out after {self._config.llm_timeout}s.",
                provider=_PROVIDER,
                details={"original": str(exc)},
            ) from exc
        except google_exceptions.GoogleAPIError as exc:
            raise LLMProviderError(
                f"Gemini API error: {exc}",
                provider=_PROVIDER,
                details={"original": str(exc)},
            ) from exc

        latency_ms = (time.monotonic() - start) * 1000

        # Extract token usage (may be absent on some model tiers)
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens: int = getattr(usage, "prompt_token_count", -1) or -1
        output_tokens: int = getattr(usage, "candidates_token_count", -1) or -1

        # Extract finish reason
        finish_reason = "STOP"
        if response.candidates:
            finish_reason = str(
                getattr(response.candidates[0], "finish_reason", "STOP")
            )

        text = response.text  # raises ValueError if content was blocked

        return LLMRawResponse(
            text=text,
            model=self._config.gemini_model,
            provider=_PROVIDER,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
        )

    # ── BaseLLMClient interface ─────────────────────────────────────────────

    async def generate(self, request: LLMRequest) -> LLMRawResponse:
        """
        Send a text-generation request to Gemini.

        Runs the blocking SDK call in a thread executor so the async event
        loop is not stalled.

        Parameters
        ----------
        request:    Fully-prepared :class:`LLMRequest`.

        Returns
        -------
        LLMRawResponse
        """
        logger.debug(
            "Gemini generate — prompt_len=%d system_prompt=%s",
            len(request.prompt),
            bool(request.system_prompt),
        )
        model = self._get_model(
            system_prompt=request.system_prompt,
            json_mode=False,
        )
        return await asyncio.to_thread(
            self._call_sdk, model, request.prompt, request
        )

    async def generate_json(self, request: LLMRequest) -> LLMRawResponse:
        """
        Send a JSON-mode generation request to Gemini.

        Gemini's ``response_mime_type = "application/json"`` is set so the
        model is constrained to emit valid JSON.

        Parameters
        ----------
        request:    Fully-prepared :class:`LLMRequest`.

        Returns
        -------
        LLMRawResponse   (``text`` will be a JSON string)
        """
        logger.debug("Gemini generate_json — prompt_len=%d", len(request.prompt))
        model = self._get_model(
            system_prompt=request.system_prompt,
            json_mode=True,
        )
        return await asyncio.to_thread(
            self._call_sdk, model, request.prompt, request
        )

    async def health_check(self) -> bool:
        """
        Verify Gemini API connectivity with a minimal embedding call.

        Returns
        -------
        bool
            ``True`` if healthy, ``False`` on any error.
        """
        try:
            logger.debug("Running Gemini health check …")
            await asyncio.to_thread(
                genai.embed_content,
                model="models/text-embedding-004",
                content="health",
                task_type="retrieval_document",
            )
            logger.debug("Gemini health check passed.")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini health check failed — %s", exc)
            return False
