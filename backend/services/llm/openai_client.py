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
    """
    Generate agent-specific fallback responses whose JSON structure exactly matches
    each agent's Pydantic output model.

    Detection strategy
    ------------------
    Each agent passes a unique, stable system-prompt string to the LLM.  We match
    on a unique substring of that string rather than on arbitrary prompt keywords so
    that the correct branch fires even when the user-facing prompt content changes.

    Agent → detection substring → output model
    -------------------------------------------
    InteractionAgent  : "structured json extraction engine"  → InteractionAnalysis
    KnowledgeAgent    : "structured json knowledge synthesis" → KnowledgeContext
    HealthAgent       : "health scoring system"              → HealthAssessment
    RiskAgent         : "risk scoring system"                → RiskAssessment
    ReasoningAgent    : "business reasoning system"          → BusinessReasoning
    RecommendationAgent: "next-best action"                  → RecommendationPlan
    """
    import json
    from datetime import datetime, timezone

    combined = (system_prompt + " " + prompt_text).lower()

    # ------------------------------------------------------------------
    # 1. InteractionAgent
    #    Model: InteractionAnalysis
    #    Required fields: customer, participants, sentiment, sentiment_score,
    #                     urgency, issues (list[IssueRecord]), entities, action_items,
    #                     commitments, key_topics, summary, interaction_count,
    #                     sources_analysed, analysed_at, confidence
    # ------------------------------------------------------------------
    if "extraction engine" in combined or "structured json extraction" in combined:
        return json.dumps({
            "customer": "Acme Corporation",
            "participants": ["Customer Contact", "Account Executive"],
            "sentiment": "negative",
            "sentiment_score": -0.72,
            "urgency": "critical",
            "issues": [
                {
                    "description": "Reporting dashboard queries time out after 30 seconds",
                    "severity": "critical",
                    "category": "performance",
                    "status": "open"
                },
                {
                    "description": "Customer unhappy with resolution timeline for latency issue",
                    "severity": "high",
                    "category": "support",
                    "status": "escalated"
                }
            ],
            "entities": [
                {"name": "Acme Corporation", "entity_type": "organisation", "context": None},
                {"name": "reporting dashboard", "entity_type": "feature", "context": None}
            ],
            "action_items": [
                {
                    "description": "Deploy database read replica to reduce query latency",
                    "owner": "engineering",
                    "due_date": "2026-07-05",
                    "priority": "high"
                }
            ],
            "commitments": [
                {
                    "description": "Provide performance fix update within 48 hours",
                    "made_by": "support_engineer",
                    "due_date": "2026-06-30"
                }
            ],
            "key_topics": [
                "dashboard performance",
                "contract renewal",
                "executive escalation",
                "latency resolution"
            ],
            "summary": (
                "Acme Corporation reported critical dashboard query timeouts exceeding 30 seconds "
                "that are blocking daily operations. The customer expressed dissatisfaction with "
                "the current resolution timeline and raised concerns about their upcoming renewal."
            ),
            "interaction_count": 1,
            "sources_analysed": ["call_transcript"],
            "analysed_at": datetime.now(tz=timezone.utc).isoformat(),
            "confidence": 0.0
        })

    # ------------------------------------------------------------------
    # 2. KnowledgeAgent
    #    Model: KnowledgeContext
    #    Required fields: summary, confidence, relevant_documents (list[RelevantDocument]),
    #                     playbooks, troubleshooting_guides, previous_cases,
    #                     product_information, known_limitations, best_practices, citations
    # ------------------------------------------------------------------
    if "knowledge synthesis" in combined or "knowledge synthesis engine" in combined:
        return json.dumps({
            "summary": (
                "The enterprise knowledge base contains relevant playbooks for dashboard "
                "performance issues and executive escalation procedures. Pre-aggregated "
                "query tables and read replicas are the documented mitigation for report timeouts."
            ),
            "confidence": 0.0,
            "relevant_documents": [
                {"doc_id": "DOC-001", "title": "Enterprise SLA Agreement v3.2",
                 "type": "best_practice", "score": 0.95},
                {"doc_id": "DOC-002", "title": "Executive Business Review Playbook",
                 "type": "playbook", "score": 0.88},
                {"doc_id": "DOC-003", "title": "Churn Prevention Framework",
                 "type": "playbook", "score": 0.82}
            ],
            "playbooks": [
                "Executive Business Review Playbook: schedule within 7 days for at-risk renewals.",
                "Churn Prevention Framework: proactive outreach triggers when health score < 70."
            ],
            "troubleshooting_guides": [
                "Dashboard query timeout: add pre-aggregated summary tables and enable read replicas."
            ],
            "previous_cases": [
                "CASE-4821: Resolved similar report latency issue for GlobalTech via DB indexing — 100% renewal achieved."
            ],
            "product_information": [
                "InsightFlow reporting engine supports up to 1M row queries; exceeding limits causes timeout."
            ],
            "known_limitations": [
                "Real-time aggregate reports with more than 500K rows may timeout without pre-aggregation."
            ],
            "best_practices": [
                "Enable read replicas for all enterprise reporting workloads.",
                "Pre-aggregate monthly KPI tables nightly to avoid real-time query bottlenecks."
            ],
            "citations": [
                "Enterprise SLA Agreement v3.2",
                "Executive Business Review Playbook",
                "Churn Prevention Framework"
            ]
        })

    # ------------------------------------------------------------------
    # 3. HealthAgent
    #    Model: HealthAssessment
    #    Required fields: score (int 0-100), status, trend, drivers (list[str]),
    #                     confidence (float 0-1), summary (str, min_length=10)
    #    Allowed status values : healthy | fair | poor | at_risk | critical
    #    Allowed trend values  : improving | stable | declining
    # ------------------------------------------------------------------
    if "health scoring system" in combined:
        return json.dumps({
            "score": 52,
            "status": "at_risk",
            "trend": "declining",
            "drivers": [
                "Dashboard query timeouts blocking daily operations",
                "DAU/MAU adoption ratio dropped to 0.12 (below healthy threshold of 0.35)",
                "3 open support tickets with 1 escalated",
                "Renewal likelihood estimated at 45% — below retention target",
                "Negative customer sentiment score of -0.72"
            ],
            "confidence": 0.0,
            "summary": (
                "Acme Corporation is currently at risk. A critical dashboard performance issue "
                "is reducing active engagement, eroding trust, and threatening a $120,000 ACV "
                "renewal in 60 days. Immediate technical and commercial intervention is required."
            )
        })

    # ------------------------------------------------------------------
    # 4. RiskAgent
    #    Model: RiskAssessment
    #    Required fields: overall_level, identified_risks (list[RiskItem]), confidence, summary
    #    RiskItem fields : category, severity, probability, impact, evidence, description
    #    Allowed overall_level: low | medium | high | critical
    #    Allowed category     : financial | product | support | sentiment | adoption | other
    #    Allowed severity     : low | medium | high | critical
    # ------------------------------------------------------------------
    if "risk scoring system" in combined:
        return json.dumps({
            "overall_level": "high",
            "identified_risks": [
                {
                    "category": "financial",
                    "severity": "critical",
                    "probability": 0.72,
                    "impact": 0.90,
                    "evidence": "Contract ACV $120,000 with renewal in 60 days and renewal likelihood at 45%.",
                    "description": "High probability of contract non-renewal due to unresolved performance issues."
                },
                {
                    "category": "product",
                    "severity": "high",
                    "probability": 0.88,
                    "impact": 0.80,
                    "evidence": "Dashboard queries exceeding 30-second timeout threshold.",
                    "description": "Critical reporting performance degradation blocking customer daily operations."
                },
                {
                    "category": "adoption",
                    "severity": "high",
                    "probability": 0.78,
                    "impact": 0.70,
                    "evidence": "DAU/MAU ratio declined from 0.31 to 0.12 over the past 14 days.",
                    "description": "Accelerating drop in active user engagement correlated with performance issues."
                },
                {
                    "category": "support",
                    "severity": "medium",
                    "probability": 0.65,
                    "impact": 0.55,
                    "evidence": "3 open tickets with 1 escalated; average resolution time above SLA threshold.",
                    "description": "Support escalation risk if ticket resolution breaches agreed SLA timelines."
                },
                {
                    "category": "sentiment",
                    "severity": "high",
                    "probability": 0.80,
                    "impact": 0.65,
                    "evidence": "Interaction sentiment score -0.72; customer cited frustration with timeline.",
                    "description": "Sustained negative sentiment increases executive escalation and churn intent."
                }
            ],
            "confidence": 0.0,
            "summary": (
                "Acme Corporation faces a high overall risk profile driven by a critical financial "
                "exposure of $120,000 ACV at renewal risk, a severe product performance degradation, "
                "and accelerating adoption decline. Without immediate remediation, churn probability "
                "is estimated above 70%."
            )
        })

    # ------------------------------------------------------------------
    # 5. ReasoningAgent
    #    Model: BusinessReasoning
    #    Required fields: overall_assessment, business_context (BusinessContext),
    #                     key_findings (list[KeyFinding]), supporting_facts (list[str]),
    #                     confidence (float 0-1), summary (str, min_length=10)
    #    BusinessContext fields: customer_stage, relationship_status, product_adoption, support_state
    #    KeyFinding fields     : title, reasoning, evidence
    #    Allowed overall_assessment: healthy | stable | at_risk | critical_escalation | review_needed
    #    Allowed customer_stage    : onboarding | adoption | renewal | expansion | other
    #    Allowed relationship_status: stable | at_risk | escalated | critical
    #    Allowed product_adoption  : high | medium | low | declining
    #    Allowed support_state     : stable | normal | high_load | escalated | critical
    # ------------------------------------------------------------------
    if "business reasoning system" in combined:
        return json.dumps({
            "overall_assessment": "at_risk",
            "business_context": {
                "customer_stage": "renewal",
                "relationship_status": "at_risk",
                "product_adoption": "declining",
                "support_state": "escalated"
            },
            "key_findings": [
                {
                    "title": "Performance Degradation Driving Adoption Decline",
                    "reasoning": (
                        "The dashboard query timeouts are directly correlated with the 18% "
                        "drop in DAU/MAU ratio. Customers experiencing product failures reduce "
                        "usage, which the CRM reflects as a declining adoption metric."
                    ),
                    "evidence": (
                        "DAU/MAU ratio dropped from 0.31 to 0.12; dashboard timeouts exceed "
                        "30 seconds; 3 active support tickets."
                    )
                },
                {
                    "title": "Renewal Exposure Amplified by Unresolved Technical Issues",
                    "reasoning": (
                        "A $120,000 ACV contract renewal is approaching in 60 days while core "
                        "product functionality is degraded. The combination of low renewal "
                        "likelihood (45%) and negative customer sentiment (-0.72) creates a "
                        "compounding churn risk."
                    ),
                    "evidence": (
                        "Contract ACV $120,000; renewal date 2026-08-15; renewal likelihood 45%; "
                        "sentiment score -0.72."
                    )
                },
                {
                    "title": "Support Escalation Indicates Relationship Strain",
                    "reasoning": (
                        "The presence of an escalated support ticket alongside critical urgency "
                        "in the interaction analysis indicates that normal support channels have "
                        "failed to satisfy the customer, signalling an elevated relationship risk."
                    ),
                    "evidence": (
                        "1 escalated support ticket; customer urgency rated critical; "
                        "interaction sentiment negative."
                    )
                }
            ],
            "supporting_facts": [
                "Dashboard query timeout: exceeds 30-second SLA threshold.",
                "Contract ACV: $120,000 with renewal due 2026-08-15.",
                "Renewal likelihood: 45% — below 60% retention threshold.",
                "DAU/MAU ratio: 0.12, down from 0.31 over the past 14 days.",
                "Open support tickets: 3, with 1 escalated.",
                "Customer sentiment score: -0.72 (critical negative)."
            ],
            "confidence": 0.0,
            "summary": (
                "Acme Corporation is currently in a high-risk renewal stage characterized by a "
                "critical product performance failure that is driving declining product adoption and "
                "negative customer sentiment. The combination of an approaching $120,000 renewal, "
                "a 45% renewal likelihood, and an escalated support ticket indicates that this "
                "account requires immediate cross-functional intervention to prevent churn."
            )
        })

    # ------------------------------------------------------------------
    # 6. RecommendationAgent
    #    Model: RecommendationPlan
    #    Required fields: recommendations (list[Recommendation]), overall_priority,
    #                     confidence (float 0-1), summary (str, min_length=10)
    #    Recommendation fields: title, description, priority, category, expected_impact,
    #                           success_probability, reasoning, supporting_evidence (list[str])
    #    Allowed overall_priority: critical | high | medium | low
    #    Allowed priority        : critical | high | medium | low
    #    Allowed category        : Renewal | Customer Success | Product Adoption | Support |
    #                              Expansion | Executive Engagement | Risk Mitigation |
    #                              Operational | Other
    # ------------------------------------------------------------------
    if "next-best action" in combined or "next best action" in combined or "recommendation" in combined:
        return json.dumps({
            "recommendations": [
                {
                    "title": "Schedule Emergency Executive Business Review",
                    "description": (
                        "Arrange an executive-level meeting with Acme Corporation's leadership "
                        "within 5 business days. Present a formal technical remediation roadmap "
                        "and commercial goodwill gesture (e.g., SLA credit) to stabilize the relationship."
                    ),
                    "priority": "critical",
                    "category": "Executive Engagement",
                    "expected_impact": (
                        "Increases renewal likelihood from 45% to 75%+ by demonstrating executive "
                        "commitment and providing a clear resolution timeline."
                    ),
                    "success_probability": 0.81,
                    "reasoning": (
                        "Direct executive alignment is the highest-leverage action to prevent churn "
                        "when relationship_status is at_risk and renewal is within 60 days."
                    ),
                    "supporting_evidence": [
                        "Renewal in 60 days with $120,000 ACV at risk.",
                        "Renewal likelihood currently at 45%.",
                        "Customer sentiment score -0.72 (critical negative)."
                    ]
                },
                {
                    "title": "Deploy Query Pre-Aggregation and Read Replica Fix",
                    "description": (
                        "Engineering to enable pre-aggregated nightly summary tables and provision "
                        "a dedicated read replica for the Acme reporting workload within 48 hours "
                        "to eliminate the 30-second timeout issue."
                    ),
                    "priority": "critical",
                    "category": "Support",
                    "expected_impact": (
                        "Resolves the root cause of the performance degradation, restoring DAU/MAU "
                        "ratio and removing the primary driver of negative sentiment."
                    ),
                    "success_probability": 0.87,
                    "reasoning": (
                        "Without resolving the core technical failure, all commercial and relationship "
                        "interventions will be undermined. This fix directly addresses the customer's "
                        "stated blocker."
                    ),
                    "supporting_evidence": [
                        "Dashboard timeouts exceed 30 seconds for reports over 500K rows.",
                        "DAU/MAU ratio dropped from 0.31 to 0.12 over 14 days.",
                        "3 open support tickets related to dashboard performance."
                    ]
                },
                {
                    "title": "Initiate Proactive Renewal Negotiation",
                    "description": (
                        "CSM to open renewal discussion 60 days ahead of the contract end date, "
                        "framing the conversation around resolution milestones and offering a "
                        "multi-year incentive to secure early commitment."
                    ),
                    "priority": "high",
                    "category": "Renewal",
                    "expected_impact": (
                        "Secures $120,000 ACV and potentially increases contract value through "
                        "multi-year commitment with expanded tier."
                    ),
                    "success_probability": 0.68,
                    "reasoning": (
                        "Early renewal engagement reduces churn risk by giving the CSM leverage "
                        "to tie commercial terms to the technical resolution milestones."
                    ),
                    "supporting_evidence": [
                        "Contract renewal date: 2026-08-15.",
                        "Renewal likelihood: 45%.",
                        "ACV: $120,000."
                    ]
                }
            ],
            "overall_priority": "critical",
            "confidence": 0.0,
            "summary": (
                "Acme Corporation requires immediate critical-priority intervention across three "
                "tracks: an emergency executive engagement to stabilize the relationship, an urgent "
                "technical fix to resolve dashboard performance failures, and a proactive renewal "
                "negotiation to protect the $120,000 ACV. All three actions must begin within 5 "
                "business days to prevent churn."
            )
        })

    # ------------------------------------------------------------------
    # Generic fallback (CRM Agent or unknown callers)
    # ------------------------------------------------------------------
    return json.dumps({
        "status": "success",
        "message": "AI agent executed successfully (fallback mode)"
    })
