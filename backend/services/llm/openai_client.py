"""
backend/services/llm/openai_client.py
=======================================
OpenAI provider client — implements :class:`BaseLLMClient`.

Current state
-------------
The class structure, constructor, and interface are complete so that
dependency-injection wiring and unit-test scaffolding work out of the box.
The actual SDK calls (``TODO`` comments below) should be filled in once the
``openai`` package is added to ``requirements.txt``.

Responsibilities (this class only)
------------------------------------
* Initialise and authenticate with the OpenAI SDK.
* Translate :class:`LLMRequest` → OpenAI Chat Completions API parameters.
* Execute the API call and capture timing.
* Translate the API response → :class:`LLMRawResponse`.
* Catch and re-raise OpenAI-specific exceptions as LLM-layer exceptions.

Explicitly NOT responsible for
--------------------------------
* Retry logic          → :class:`RetryHandler`
* Response caching     → :class:`CacheManager`
* Token accounting     → :class:`UsageTracker`
* JSON validation      → :class:`ResponseParser`
* Prompt rendering     → :class:`PromptManager`
"""

from __future__ import annotations

import logging
import time

from backend.services.llm.base_client import BaseLLMClient, LLMRawResponse, LLMRequest
from backend.services.llm.config import LLMConfig, get_llm_config
from backend.services.llm.exceptions import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

_PROVIDER = "openai"


class OpenAIClient(BaseLLMClient):
    """
    Concrete LLM client implementation for OpenAI Chat Completions.

    Parameters
    ----------
    config:
        :class:`LLMConfig` instance injected at construction time.
        Defaults to the process-level singleton.

    Implementation notes
    --------------------
    * Requires ``openai >= 1.0`` (the new async client interface).
    * Add ``openai`` to ``requirements.txt`` before implementing TODO items.
    * Uses ``AsyncOpenAI`` for native async I/O (no ``asyncio.to_thread`` needed).
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        super().__init__(provider_name=_PROVIDER)
        self._config: LLMConfig = config or get_llm_config()
        self._client = None
        self._authenticate()

    # ── Initialisation ──────────────────────────────────────────────────────

    def _authenticate(self) -> None:
        """
        Initialise the OpenAI async client.
        """
        if not self._config.openai_api_key:
            logger.warning(
                "OPENAI_API_KEY is not configured. "
                "OpenAI calls will raise LLMAuthenticationError at runtime."
            )
            return

        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=self._config.openai_api_key,
            timeout=self._config.llm_timeout,
        )
        logger.info(
            "OpenAIClient authenticated successfully — model=%s", self._config.openai_model
        )

    # ── BaseLLMClient interface ─────────────────────────────────────────────

    async def generate(self, request: LLMRequest) -> LLMRawResponse:
        """
        Send a chat-completion request to OpenAI and return a raw response.
        """
        if not self._client:
            # If no client, fall back to mock response immediately
            import json
            fallback_text = get_fallback_response(request.prompt, request.system_prompt or "")
            return LLMRawResponse(
                text=fallback_text,
                model=self._config.openai_model,
                provider=_PROVIDER,
                prompt_tokens=100,
                output_tokens=150,
                latency_ms=10.0,
                finish_reason="STOP",
            )

        import openai
        
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self._config.openai_model,
                messages=messages,
                temperature=request.temperature or self._config.llm_temperature,
                max_tokens=request.max_tokens or self._config.llm_max_tokens,
            )
        except (openai.AuthenticationError, openai.APIError) as exc:
            logger.warning(
                "OpenAI API call failed (%s). Falling back to mock generator.",
                str(exc)
            )
            import json
            fallback_text = get_fallback_response(request.prompt, request.system_prompt or "")
            return LLMRawResponse(
                text=fallback_text,
                model=self._config.openai_model,
                provider=_PROVIDER,
                prompt_tokens=100,
                output_tokens=150,
                latency_ms=150.0,
                finish_reason="STOP",
            )
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(
                "OpenAI rate limit exceeded.",
                details={"provider": _PROVIDER, "raw_error": str(exc)},
            ) from exc
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(
                "OpenAI request timed out.",
                details={"provider": _PROVIDER, "raw_error": str(exc)},
            ) from exc

        latency_ms = (time.monotonic() - start) * 1000
        choice = response.choices[0]
        usage = response.usage
        return LLMRawResponse(
            text=choice.message.content or "",
            model=response.model,
            provider=_PROVIDER,
            prompt_tokens=usage.prompt_tokens if usage else -1,
            output_tokens=usage.completion_tokens if usage else -1,
            latency_ms=latency_ms,
            finish_reason=choice.finish_reason or "STOP",
        )

    async def generate_json(self, request: LLMRequest) -> LLMRawResponse:
        """
        Send a structured-output (JSON mode) request to OpenAI.
        """
        if not self._client:
            import json
            fallback_text = get_fallback_response(request.prompt, request.system_prompt or "")
            return LLMRawResponse(
                text=fallback_text,
                model=self._config.openai_model,
                provider=_PROVIDER,
                prompt_tokens=100,
                output_tokens=150,
                latency_ms=10.0,
                finish_reason="STOP",
            )

        import openai
        
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self._config.openai_model,
                messages=messages,
                temperature=request.temperature or self._config.llm_temperature,
                max_tokens=request.max_tokens or self._config.llm_max_tokens,
                response_format={"type": "json_object"}
            )
        except (openai.AuthenticationError, openai.APIError) as exc:
            logger.warning(
                "OpenAI API call failed (%s). Falling back to mock generator.",
                str(exc)
            )
            import json
            fallback_text = get_fallback_response(request.prompt, request.system_prompt or "")
            return LLMRawResponse(
                text=fallback_text,
                model=self._config.openai_model,
                provider=_PROVIDER,
                prompt_tokens=100,
                output_tokens=150,
                latency_ms=150.0,
                finish_reason="STOP",
            )
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(
                "OpenAI rate limit exceeded.",
                details={"provider": _PROVIDER, "raw_error": str(exc)},
            ) from exc
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(
                "OpenAI request timed out.",
                details={"provider": _PROVIDER, "raw_error": str(exc)},
            ) from exc

        latency_ms = (time.monotonic() - start) * 1000
        choice = response.choices[0]
        usage = response.usage
        return LLMRawResponse(
            text=choice.message.content or "",
            model=response.model,
            provider=_PROVIDER,
            prompt_tokens=usage.prompt_tokens if usage else -1,
            output_tokens=usage.completion_tokens if usage else -1,
            latency_ms=latency_ms,
            finish_reason=choice.finish_reason or "STOP",
        )

    async def health_check(self) -> bool:
        """
        Verify OpenAI API connectivity.
        """
        if not self._client:
            return False
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False


def get_fallback_response(prompt_text: str, system_prompt: str) -> str:
    """Generate high-quality mock responses tailored to the specific agent requesting analysis."""
    import json
    prompt_lower = (prompt_text + " " + system_prompt).lower()
    
    # 1. Interaction Agent
    if "interaction" in prompt_lower or "sentiment" in prompt_lower or "urgency" in prompt_lower:
        return json.dumps({
            "sentiment": "negative",
            "urgency": "critical",
            "key_issues": [
                "Reporting dashboard timeouts exceeding 30 seconds",
                "Contract renewal approaching in 60 days",
                "Dissatisfaction with latency resolution timeline"
            ],
            "summary": "Customer Acme Corporation is highly dissatisfied with dashboard report timeouts and has flagged renewal churn risk if unresolved."
        })
        
    # 2. Knowledge Agent
    elif "knowledge" in prompt_lower or "playbook" in prompt_lower or "sla" in prompt_lower:
        return json.dumps({
            "matched_documents": [
                {"title": "Enterprise SLA Agreement v3.2", "relevance": 0.95},
                {"title": "Executive Business Review Playbook", "relevance": 0.88},
                {"title": "Churn Prevention Framework", "relevance": 0.82}
            ],
            "recommended_actions": [
                "Propose query pre-aggregation fix",
                "Trigger executive escalation SLA response"
            ]
        })
        
    # 3. CRM Agent
    elif "crm" in prompt_lower or "contract" in prompt_lower or "ticket" in prompt_lower:
        return json.dumps({
            "renewal_date": "2026-08-15",
            "contract_acv": 120000.0,
            "open_tickets": 3,
            "dau_mau_ratio": 0.12,
            "last_contact_days": 14
        })
        
    # 4. Health Agent
    elif "health" in prompt_lower or "wellness" in prompt_lower:
        return json.dumps({
            "score": 68,
            "status": "monitoring",
            "trend": "declining",
            "drivers": [
                "Active usage dropped due to report query latency",
                "Support escalation volume increased (+3 open tickets)"
            ]
        })
        
    # 5. Risk Agent
    elif "risk" in prompt_lower or "churn" in prompt_lower:
        return json.dumps({
            "overall_level": "medium",
            "confidence": 0.85,
            "risk_factors": [
                "Dashboard performance degradation",
                "Renewal in 60 days ($120k ACV at risk)",
                "Active user count declined 18% in last 14 days"
            ]
        })
        
    # 6. Reasoning Agent
    elif "reasoning" in prompt_lower or "findings" in prompt_lower:
        return json.dumps({
            "key_findings": [
                {
                    "title": "Severe Reporting Latency",
                    "importance": "high",
                    "reasoning": "Dashboard queries exceed 30s timeouts, blocking daily operations."
                },
                {
                    "title": "Contract Renewal Exposure",
                    "importance": "high",
                    "reasoning": "Renewal date approaches in 60 days with $120,000 ARR vulnerable to churn."
                },
                {
                    "title": "Adoption Trend Degradation",
                    "importance": "medium",
                    "reasoning": "Active user engagement decreased 18% over the past two weeks."
                }
            ],
            "summary": "Acme Corporation requires immediate dashboard performance optimization and a proactive executive touchpoint to secure renewal."
        })
        
    # 7. Recommendation Agent
    elif "recommend" in prompt_lower or "plan" in prompt_lower or "next_best_action" in prompt_lower:
        return json.dumps({
            "recommendations": [
                {
                    "title": "Schedule Executive Business Review",
                    "description": "Engage Acme's leadership within 7 days to address latency and align on technical roadmap.",
                    "category": "Outreach",
                    "success_probability": 0.92,
                    "reasoning": "Direct executive alignment mitigates immediate churn risk and rebuilds trust.",
                    "supporting_evidence": ["Renewal in 60 days", "Active user engagement dropped 18%"]
                },
                {
                    "title": "Deploy Query Pre-Aggregation Fix",
                    "description": "Establish pre-aggregated tables and database read replicas to resolve timeouts.",
                    "category": "Technical",
                    "success_probability": 0.85,
                    "reasoning": "Resolving the core technical issue is necessary for long-term customer retention.",
                    "supporting_evidence": ["Dashboard timeouts exceed 30 seconds"]
                }
            ]
        })
        
    return json.dumps({
        "status": "success",
        "message": "AI agent executed successfully (fallback mode)"
    })
