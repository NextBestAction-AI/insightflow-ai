"""
backend/services/llm/__init__.py
==================================
LLM infrastructure package — public surface area.

External code (agents, routers, other services) should import exclusively
from this module.  Never import directly from sub-modules.

Public exports
--------------
LLMService          — the only entry point for LLM operations.
create_llm_service  — factory that wires the full dependency graph.
LLMConfig           — configuration data class.
get_llm_config      — singleton config accessor.
PipelineRequest     — input DTO for :meth:`LLMService.generate_text`.
PipelineResponse    — output DTO from the pipeline.
LLMProvider         — enum of supported providers.

Exceptions (re-exported for convenience)
-----------------------------------------
LLMBaseError
LLMConfigurationError
LLMAuthenticationError
LLMProviderError
LLMRateLimitError
LLMTimeoutError
LLMResponseError
LLMJSONParseError
LLMCacheError
LLMRetryExhaustedError

Example
-------
    from backend.services.llm import create_llm_service, LLMJSONParseError

    llm = create_llm_service()

    try:
        response = await llm.generate_text(raw_prompt="Hello, Gemini!")
        print(response.text)
    except LLMJSONParseError as exc:
        ...
"""

from backend.services.llm.config import LLMConfig, LLMProvider, get_llm_config
from backend.services.llm.execution_pipeline import PipelineRequest, PipelineResponse
from backend.services.llm.exceptions import (
    LLMAuthenticationError,
    LLMBaseError,
    LLMCacheError,
    LLMConfigurationError,
    LLMJSONParseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
)
from backend.services.llm.llm_service import LLMService, create_llm_service

__all__ = [
    # Service
    "LLMService",
    "create_llm_service",
    # Config
    "LLMConfig",
    "LLMProvider",
    "get_llm_config",
    # Pipeline DTOs
    "PipelineRequest",
    "PipelineResponse",
    # Exceptions
    "LLMBaseError",
    "LLMConfigurationError",
    "LLMAuthenticationError",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMResponseError",
    "LLMJSONParseError",
    "LLMCacheError",
    "LLMRetryExhaustedError",
]
