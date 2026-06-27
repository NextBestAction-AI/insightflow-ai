"""
backend/services/llm/config.py
================================
LLM layer configuration — loaded exclusively from environment variables.

All LLM infrastructure classes receive an ``LLMConfig`` instance via
dependency injection; they never read ``os.environ`` directly.

Supported environment variables
--------------------------------
GEMINI_API_KEY          : Google Gemini API key
GEMINI_MODEL            : Gemini model identifier (e.g. gemini-1.5-pro)
OPENAI_API_KEY          : OpenAI API key
OPENAI_MODEL            : OpenAI model identifier (e.g. gpt-4o)
LLM_MODEL_TYPE          : Active provider — "gemini" | "openai"
LLM_TEMPERATURE         : Sampling temperature  (0.0 – 2.0)
LLM_MAX_TOKENS          : Maximum tokens in the completion
LLM_TIMEOUT             : Per-request timeout in seconds
LLM_CACHE_TTL           : Cache entry TTL in seconds
LLM_CACHE_MAX_SIZE      : Maximum number of cached entries
LLM_MAX_RETRIES         : Maximum retry attempts on transient errors
LLM_RETRY_BASE_DELAY    : Base backoff delay in seconds
LLM_RETRY_MAX_DELAY     : Maximum backoff delay in seconds
"""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class LLMProvider(str, Enum):
    """Supported LLM providers."""

    GEMINI = "gemini"
    OPENAI = "openai"


# ---------------------------------------------------------------------------
# Configuration model
# ---------------------------------------------------------------------------

class LLMConfig(BaseSettings):
    """
    Pydantic-Settings model for the entire LLM infrastructure layer.

    Instantiate via :func:`get_llm_config` to leverage the module-level
    singleton cache.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Provider selection ──────────────────────────────────────────────────
    llm_model_type: LLMProvider = Field(
        default=LLMProvider.GEMINI,
        alias="LLM_MODEL_TYPE",
        description="Active LLM provider: 'gemini' or 'openai'.",
    )

    # ── Gemini ──────────────────────────────────────────────────────────────
    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY",
        description="Google Gemini API key.",
    )
    gemini_model: str = Field(
        default="gemini-1.5-pro",
        alias="GEMINI_MODEL",
        description="Gemini model identifier.",
    )

    # ── OpenAI ──────────────────────────────────────────────────────────────
    openai_api_key: str = Field(
        default="",
        alias="OPENAI_API_KEY",
        description="OpenAI API key.",
    )
    openai_model: str = Field(
        default="gpt-4o",
        alias="OPENAI_MODEL",
        description="OpenAI model identifier.",
    )

    # ── Shared generation parameters ────────────────────────────────────────
    llm_temperature: float = Field(
        default=0.2,
        alias="LLM_TEMPERATURE",
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0 = deterministic, 2.0 = creative).",
    )
    llm_max_tokens: int = Field(
        default=8192,
        alias="LLM_MAX_TOKENS",
        gt=0,
        description="Maximum tokens in a single completion.",
    )
    llm_timeout: float = Field(
        default=60.0,
        alias="LLM_TIMEOUT",
        gt=0,
        description="Per-request network timeout in seconds.",
    )

    # ── Cache ────────────────────────────────────────────────────────────────
    llm_cache_ttl: int = Field(
        default=3600,
        alias="LLM_CACHE_TTL",
        ge=0,
        description="Cache entry TTL in seconds. 0 disables expiry.",
    )
    llm_cache_max_size: int = Field(
        default=512,
        alias="LLM_CACHE_MAX_SIZE",
        ge=1,
        description="Maximum number of responses held in the in-memory cache.",
    )

    # ── Retry ────────────────────────────────────────────────────────────────
    llm_max_retries: int = Field(
        default=3,
        alias="LLM_MAX_RETRIES",
        ge=0,
        description="Maximum retry attempts on transient errors.",
    )
    llm_retry_base_delay: float = Field(
        default=1.0,
        alias="LLM_RETRY_BASE_DELAY",
        gt=0,
        description="Base backoff delay in seconds (doubles each attempt).",
    )
    llm_retry_max_delay: float = Field(
        default=30.0,
        alias="LLM_RETRY_MAX_DELAY",
        gt=0,
        description="Maximum backoff delay cap in seconds.",
    )

    # ── Cross-field validation ───────────────────────────────────────────────
    @model_validator(mode="after")
    def _validate_api_keys(self) -> "LLMConfig":
        """Warn (not error) if the active provider's API key is empty."""
        if self.llm_model_type == LLMProvider.GEMINI and not self.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY is not set. "
                "All Gemini requests will fail until it is configured."
            )
        if self.llm_model_type == LLMProvider.OPENAI and not self.openai_api_key:
            logger.warning(
                "OPENAI_API_KEY is not set. "
                "All OpenAI requests will fail until it is configured."
            )
        return self

    @field_validator("llm_retry_max_delay")
    @classmethod
    def _max_delay_gte_base(cls, v: float, info) -> float:
        base = info.data.get("llm_retry_base_delay", 1.0)
        if v < base:
            raise ValueError(
                f"llm_retry_max_delay ({v}s) must be >= llm_retry_base_delay ({base}s)."
            )
        return v

    # ── Convenience helpers ──────────────────────────────────────────────────
    @property
    def active_model_name(self) -> str:
        """Return the model identifier string for the active provider."""
        return (
            self.gemini_model
            if self.llm_model_type == LLMProvider.GEMINI
            else self.openai_model
        )

    @property
    def active_api_key(self) -> str:
        """Return the API key for the active provider."""
        return (
            self.gemini_api_key
            if self.llm_model_type == LLMProvider.GEMINI
            else self.openai_api_key
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_llm_config() -> LLMConfig:
    """
    Return the process-level singleton :class:`LLMConfig`.

    The result is cached after the first call.  In tests, call
    ``get_llm_config.cache_clear()`` before patching environment variables.
    """
    config = LLMConfig()
    logger.info(
        "LLM configuration loaded — provider=%s model=%s",
        config.llm_model_type.value,
        config.active_model_name,
    )
    return config
