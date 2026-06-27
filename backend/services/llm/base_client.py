"""
backend/services/llm/base_client.py
=====================================
Abstract Base Class for all LLM provider clients.

Design decisions
----------------
* Enforces a uniform interface across providers (Gemini, OpenAI, …).
* Provider-specific SDK details are completely hidden behind this contract.
* Uses Python's ``abc`` module — concrete classes *must* override every
  abstract method or instantiation will raise ``TypeError``.
* No retry logic, caching, or token accounting lives here; those
  cross-cutting concerns are handled by dedicated infrastructure classes.

Implementing a new provider
----------------------------
1. Subclass ``BaseLLMClient``.
2. Implement ``generate()``, ``generate_json()``, and ``health_check()``.
3. Register the provider in ``LLMConfig`` (``LLMProvider`` enum) and the
   client factory in ``LLMExecutionPipeline``.

Usage (within the execution pipeline only)
------------------------------------------
    client: BaseLLMClient = GeminiClient(config)
    raw: LLMRawResponse = await client.generate(request)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer objects shared by all clients
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LLMRequest:
    """
    Immutable value object that carries a fully-rendered prompt and
    generation parameters to a provider client.

    Attributes
    ----------
    prompt:          The final, rendered prompt string.
    system_prompt:   Optional system/instruction prefix.
    temperature:     Sampling temperature override (``None`` → use config).
    max_tokens:      Max tokens override (``None`` → use config).
    response_format: Hint to the provider — ``"text"`` | ``"json"``.
    metadata:        Arbitrary key-value pairs forwarded to the provider
                     for tracing or routing purposes (not used in generation).
    """

    prompt: str
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: str = "text"          # "text" | "json"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LLMRawResponse:
    """
    Mutable value object returned by provider clients.

    The pipeline transforms this into a richer structure before returning
    to callers.

    Attributes
    ----------
    text:           Raw text content returned by the provider.
    model:          Exact model name used for generation.
    provider:       Provider identifier string (e.g. ``"gemini"``).
    prompt_tokens:  Tokens consumed by the prompt (-1 if unavailable).
    output_tokens:  Tokens in the generated completion (-1 if unavailable).
    latency_ms:     Wall-clock time from request send to response receipt.
    finish_reason:  Provider finish-reason string (e.g. ``"STOP"``).
    raw_metadata:   Any additional provider-specific metadata.
    """

    text: str
    model: str
    provider: str
    prompt_tokens: int = -1
    output_tokens: int = -1
    latency_ms: float = 0.0
    finish_reason: str = "STOP"
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Return total token usage, or -1 if either count is unavailable."""
        if self.prompt_tokens == -1 or self.output_tokens == -1:
            return -1
        return self.prompt_tokens + self.output_tokens


# ---------------------------------------------------------------------------
# Abstract Base Client
# ---------------------------------------------------------------------------

class BaseLLMClient(ABC):
    """
    Provider-agnostic interface that every LLM client must implement.

    The class is intentionally minimal: it defines *what* each client must
    do without dictating *how* it does it.

    Parameters
    ----------
    provider_name:  Unique string identifier for the provider
                    (used in logging and error messages).
    """

    def __init__(self, provider_name: str) -> None:
        self._provider_name = provider_name
        self._logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )

    # ── Abstract interface ──────────────────────────────────────────────────

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMRawResponse:
        """
        Send ``request`` to the provider and return the raw response.

        Parameters
        ----------
        request:    A fully-prepared :class:`LLMRequest` value object.

        Returns
        -------
        LLMRawResponse
            The provider's response wrapped in the shared DTO.

        Raises
        ------
        LLMAuthenticationError
            If the provider rejects the API key.
        LLMRateLimitError
            If the provider quota is exceeded.
        LLMTimeoutError
            If the request exceeds the configured timeout.
        LLMProviderError
            For any other provider-side error.
        """

    @abstractmethod
    async def generate_json(self, request: LLMRequest) -> LLMRawResponse:
        """
        Send ``request`` to the provider with JSON-mode enabled.

        The returned :attr:`LLMRawResponse.text` MUST be a valid JSON string.
        The :class:`ResponseParser` will handle further validation.

        Raises
        ------
        Same exceptions as :meth:`generate`.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify that the provider API is reachable and the key is valid.

        Returns
        -------
        bool
            ``True`` if the provider is healthy, ``False`` otherwise.
            Must *never* raise — exceptions should be caught and logged.
        """

    # ── Shared helpers ──────────────────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        """Read-only name of this provider (e.g. ``"gemini"``)."""
        return self._provider_name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self._provider_name!r})"
