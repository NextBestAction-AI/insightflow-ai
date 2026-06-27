"""
backend/services/llm/exceptions.py
=====================================
Custom exception hierarchy for the LLM infrastructure layer.

All LLM-layer errors derive from ``LLMBaseError`` so callers can catch the
entire family with a single ``except LLMBaseError`` clause, or target a
specific sub-class for fine-grained handling.

Hierarchy
---------
LLMBaseError
├── LLMConfigurationError       — missing or invalid configuration
├── LLMAuthenticationError      — invalid or missing API key
├── LLMProviderError            — provider returned an error response
│   ├── LLMRateLimitError       — 429 / quota exceeded
│   └── LLMTimeoutError         — request timed out
├── LLMResponseError            — response received but unusable
│   └── LLMJSONParseError       — JSON extraction / parsing failed
├── LLMCacheError               — cache read/write failure
└── LLMRetryExhaustedError      — all retry attempts failed
"""

from __future__ import annotations

from typing import Any


class LLMBaseError(Exception):
    """
    Root exception for all LLM infrastructure errors.

    Attributes
    ----------
    message:    Human-readable error description.
    details:    Optional dict with structured diagnostic information.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, details={self.details!r})"


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------

class LLMConfigurationError(LLMBaseError):
    """Raised when a required configuration value is missing or invalid."""


# ---------------------------------------------------------------------------
# Authentication errors
# ---------------------------------------------------------------------------

class LLMAuthenticationError(LLMBaseError):
    """Raised when the provider rejects the supplied API key."""


# ---------------------------------------------------------------------------
# Provider / network errors
# ---------------------------------------------------------------------------

class LLMProviderError(LLMBaseError):
    """
    Raised when the LLM provider returns an error response.

    Attributes
    ----------
    status_code:  HTTP status code from the provider, if available.
    provider:     Name of the provider that raised the error.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.provider = provider
        self.status_code = status_code


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider returns a rate-limit or quota-exceeded error."""


class LLMTimeoutError(LLMProviderError):
    """Raised when a provider request exceeds the configured timeout."""


# ---------------------------------------------------------------------------
# Response errors
# ---------------------------------------------------------------------------

class LLMResponseError(LLMBaseError):
    """
    Raised when a response is received from the provider but cannot be used.

    For example: empty content, safety filters, finish-reason=STOP missing.
    """


class LLMJSONParseError(LLMResponseError):
    """
    Raised when JSON extraction from an LLM response fails.

    Attributes
    ----------
    raw_text:    The raw string that could not be parsed.
    """

    def __init__(
        self,
        message: str,
        *,
        raw_text: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.raw_text = raw_text


# ---------------------------------------------------------------------------
# Infrastructure errors
# ---------------------------------------------------------------------------

class LLMCacheError(LLMBaseError):
    """Raised when a cache read or write operation fails."""


class LLMRetryExhaustedError(LLMBaseError):
    """
    Raised when all retry attempts for an LLM call have been exhausted.

    Attributes
    ----------
    attempts:       Number of attempts made.
    last_error:     The exception raised on the final attempt.
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: int = 0,
        last_error: Exception | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.attempts = attempts
        self.last_error = last_error
