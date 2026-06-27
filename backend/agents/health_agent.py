"""
backend/agents/health_agent.py
==============================
HealthAgent evaluates the overall health of a customer relationship by combining 
outputs from previously completed agents.

Single responsibility
---------------------
**Answer one question: "How healthy is this customer relationship based on all currently available business information?"**

This agent reads from the interaction analysis, knowledge context, CRM context, 
and customer profile. It normalizes these signals, applies deterministic business rules, 
and uses the LLM to qualitatively evaluate the health of the relationship.

It does NOT:
* Retrieve CRM data
* Retrieve knowledge
* Analyze conversations
* Detect churn risk
* Generate recommendations
* Explain business decisions
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.agents.base_agent import BaseAgent
from backend.orchestrator.agent_result import AgentResult
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.workflow_state import WorkflowState
from backend.services.llm.exceptions import LLMBaseError, LLMJSONParseError
from backend.services.llm.response_parser import ResponseParser

# =============================================================================
# Section 1: Output Schema & Domain Models
# =============================================================================

class HealthAssessment(BaseModel):
    """
    Strongly typed Pydantic model representing the output of HealthAgent.
    """
    score: int = Field(ge=0, le=100, description="Health score from 0 (critical) to 100 (healthy).")
    status: str = Field(description="Health status: healthy, fair, poor, at_risk, critical.")
    trend: str = Field(description="Health trend: improving, stable, declining.")
    drivers: list[str] = Field(default_factory=list, description="Key drivers contributing to the status.")
    confidence: float = Field(ge=0.0, le=1.0, description="LLM's confidence score in this assessment.")
    summary: str = Field(min_length=10, description="Concise qualitative explanation of the health status.")

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: Any) -> str:
        normalised = str(v).lower().strip().replace(" ", "_")
        allowed = {"healthy", "fair", "poor", "at_risk", "critical"}
        if normalised in allowed:
            return normalised
        return "fair"

    @field_validator("trend")
    @classmethod
    def _validate_trend(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"improving", "stable", "declining"}
        if normalised in allowed:
            return normalised
        return "stable"

# =============================================================================
# Section 2: Helper Data Structures & Components
# =============================================================================

class CustomerSignals(BaseModel):
    """
    Grouped customer demographic and identity signals.
    """
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    account_type: Optional[str] = None
    region: Optional[str] = None
    annual_revenue_usd: Optional[float] = None
    employee_count: Optional[int] = None


class InteractionSignals(BaseModel):
    """
    Grouped signals from conversational interaction analysis.
    """
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    urgency: Optional[str] = None
    commitments_count: int = 0
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None


class KnowledgeSignals(BaseModel):
    """
    Grouped signals from vector knowledge retrieval context.
    """
    summary: Optional[str] = None
    citations: List[str] = Field(default_factory=list)
    best_practices: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class CRMSignals(BaseModel):
    """
    Grouped signals from enterprise CRM context.
    """
    contract_active: Optional[bool] = None
    contract_acv: Optional[float] = None
    contract_end_date: Optional[str] = None
    renewal_date: Optional[str] = None
    renewal_likelihood: Optional[float] = None
    renewal_risk_level: Optional[str] = None
    usage_dau: Optional[int] = None
    usage_mau: Optional[int] = None
    usage_api_calls: Optional[int] = None
    support_open_tickets: int = 0
    support_resolved_tickets: int = 0
    support_avg_resolution_time: Optional[float] = None
    support_escalated: bool = False
    opportunities_active_count: int = 0
    opportunities_pipeline_value: float = 0.0


class HealthSignalBundle(BaseModel):
    """
    Logical grouping of business signals collected from WorkflowState.
    """
    customer: CustomerSignals
    interaction: InteractionSignals
    knowledge: KnowledgeSignals
    crm: CRMSignals


class HealthSignalCollector:
    """
    Responsible for extracting all customer signals from WorkflowState.
    """
    def collect(self, state: WorkflowState) -> HealthSignalBundle:
        # Collect customer parameters
        customer_signals = CustomerSignals(
            customer_id=state.customer.customer_id,
            customer_name=state.customer.customer_name,
            company=state.customer.company,
            industry=state.customer.industry,
            account_type=state.customer.account_type,
            region=state.customer.region,
            annual_revenue_usd=state.customer.annual_revenue_usd,
            employee_count=state.customer.employee_count
        )

        # Interaction Analysis
        ia = state.analysis.interaction_analysis or {}
        interaction_sentiment_score = state.analysis.sentiment_score
        if interaction_sentiment_score is None:
            interaction_sentiment_score = ia.get("sentiment_score")

        interaction_signals = InteractionSignals(
            sentiment=ia.get("sentiment"),
            sentiment_score=interaction_sentiment_score,
            urgency=ia.get("urgency"),
            commitments_count=len(ia.get("commitments") or []),
            issues=ia.get("issues") or [],
            summary=ia.get("summary")
        )

        # Knowledge Context
        kb_context = state.context.knowledge_context or []
        knowledge_summary = None
        knowledge_citations = []
        knowledge_best_practices = []
        knowledge_limitations = []
        if kb_context:
            first_kb = kb_context[0]
            knowledge_summary = first_kb.get("summary")
            knowledge_citations = first_kb.get("citations") or []
            knowledge_best_practices = first_kb.get("best_practices") or []
            knowledge_limitations = first_kb.get("known_limitations") or []

        knowledge_signals = KnowledgeSignals(
            summary=knowledge_summary,
            citations=knowledge_citations,
            best_practices=knowledge_best_practices,
            limitations=knowledge_limitations
        )

        # CRM Context
        crm = state.context.crm_context or {}
        profile = crm.get("profile") or {}
        contract = crm.get("contract") or {}
        renewal = crm.get("renewal") or {}
        usage = crm.get("usage") or {}
        support = crm.get("support") or {}
        opp = crm.get("opportunities") or {}

        # Merge CRM profile fields to customer signals if missing
        if not customer_signals.industry:
            customer_signals.industry = profile.get("industry")
        if not customer_signals.account_type:
            customer_signals.account_type = profile.get("account_type")
        if not customer_signals.region:
            customer_signals.region = profile.get("region")
        if not customer_signals.employee_count:
            customer_signals.employee_count = profile.get("employee_count")

        crm_signals = CRMSignals(
            contract_active=contract.get("is_active"),
            contract_acv=contract.get("annual_contract_value_usd"),
            contract_end_date=contract.get("end_date"),
            renewal_date=renewal.get("target_date"),
            renewal_likelihood=renewal.get("renewal_likelihood"),
            renewal_risk_level=renewal.get("risk_level"),
            usage_dau=usage.get("dau"),
            usage_mau=usage.get("mau"),
            usage_api_calls=usage.get("api_calls_last_30_days"),
            support_open_tickets=support.get("open_tickets_count", 0),
            support_resolved_tickets=support.get("resolved_tickets_last_90_days", 0),
            support_avg_resolution_time=support.get("avg_resolution_time_hours"),
            support_escalated=bool(support.get("escalation_status", False)),
            opportunities_active_count=opp.get("active_opportunities_count", 0),
            opportunities_pipeline_value=opp.get("pipeline_value_usd", 0.0)
        )

        return HealthSignalBundle(
            customer=customer_signals,
            interaction=interaction_signals,
            knowledge=knowledge_signals,
            crm=crm_signals
        )


class NormalizedHealthSignals(BaseModel):
    """
    Cleaned, typed, and normalized health metrics.
    """
    sentiment_score: float
    days_until_renewal: Optional[int] = None
    dau_mau_ratio: Optional[float] = None
    contract_active: bool
    acv_usd: float
    open_tickets_count: int
    escalated_support: bool
    api_calls_last_30_days: int
    renewal_likelihood: float


class HealthSignalNormalizer:
    """
    Normalizes collected signals into consistent formats.
    """
    def normalize(self, bundle: HealthSignalBundle) -> NormalizedHealthSignals:
        # Determine sentiment score
        score = bundle.interaction.sentiment_score
        if score is None:
            sentiment_map = {"positive": 0.5, "neutral": 0.0, "negative": -0.5, "mixed": -0.1}
            score = sentiment_map.get(str(bundle.interaction.sentiment).lower(), 0.0)
        else:
            score = max(-1.0, min(1.0, float(score)))

        # Calculate renewal timing
        days_until = None
        if bundle.crm.renewal_date:
            try:
                date_val = bundle.crm.renewal_date
                if isinstance(date_val, str):
                    if date_val.endswith("Z"):
                        date_val = date_val[:-1] + "+00:00"
                    dt = datetime.fromisoformat(date_val)
                else:
                    dt = date_val
                
                now = datetime.now(timezone.utc) if dt.tzinfo else datetime.now()
                days_until = (dt - now).days
            except Exception:
                pass

        # Calculate DAU/MAU adoption ratio
        dau_mau_ratio = None
        if bundle.crm.usage_dau is not None and bundle.crm.usage_mau is not None and bundle.crm.usage_mau > 0:
            dau_mau_ratio = float(bundle.crm.usage_dau) / float(bundle.crm.usage_mau)

        return NormalizedHealthSignals(
            sentiment_score=score,
            days_until_renewal=days_until,
            dau_mau_ratio=dau_mau_ratio,
            contract_active=bundle.crm.contract_active if bundle.crm.contract_active is not None else True,
            acv_usd=bundle.crm.contract_acv or 0.0,
            open_tickets_count=bundle.crm.support_open_tickets,
            escalated_support=bundle.crm.support_escalated,
            api_calls_last_30_days=bundle.crm.usage_api_calls or 0,
            renewal_likelihood=bundle.crm.renewal_likelihood if bundle.crm.renewal_likelihood is not None else 1.0
        )


class HealthIndicators(BaseModel):
    """
    Deterministic health evaluation flags and rule-based score.
    """
    renewal_approaching: bool
    repeated_negative_sentiment: bool
    high_support_load: bool
    declining_product_usage: bool
    known_product_limitations: bool
    rule_health_score: float
    critical_triggers: list[str] = Field(default_factory=list)


class HealthRuleEngine:
    """
    Evaluates deterministic business rules based on normalized metrics.
    """
    def evaluate(self, norm: NormalizedHealthSignals, bundle: HealthSignalBundle) -> HealthIndicators:
        critical_triggers = []
        score = 100.0

        # Rule 1: Renewal Timing and Risk
        renewal_approaching = False
        if norm.days_until_renewal is not None:
            if norm.days_until_renewal <= 90:
                renewal_approaching = True
                score -= 10.0
                if norm.renewal_likelihood < 0.6:
                    critical_triggers.append("URGENT_RENEWAL_RISK")
                    score -= 15.0

        # Rule 2: Customer Sentiment
        repeated_neg = norm.sentiment_score < -0.15
        if repeated_neg:
            score -= 15.0
            if norm.sentiment_score < -0.5:
                critical_triggers.append("SEVERE_NEGATIVE_SENTIMENT")
                score -= 15.0

        # Rule 3: Support Load
        high_support = norm.open_tickets_count >= 2 or norm.escalated_support
        if high_support:
            score -= 10.0
            if norm.escalated_support:
                critical_triggers.append("ESCALATED_SUPPORT_TICKET")
                score -= 15.0

        # Rule 4: Usage Decline
        declining_usage = False
        if norm.dau_mau_ratio is not None and norm.dau_mau_ratio < 0.15:
            declining_usage = True
            score -= 15.0
            critical_triggers.append("LOW_PRODUCT_ADOPTION")

        # Rule 5: Platform Constraints
        has_limitations = len(bundle.knowledge.limitations) > 0
        if has_limitations:
            score -= 5.0

        score = max(0.0, min(100.0, score))

        return HealthIndicators(
            renewal_approaching=renewal_approaching,
            repeated_negative_sentiment=repeated_neg,
            high_support_load=high_support,
            declining_product_usage=declining_usage,
            known_product_limitations=has_limitations,
            rule_health_score=score,
            critical_triggers=critical_triggers
        )


class HealthPromptBuilder:
    """
    Formats the context for the LLM qualitative analysis.
    """
    def __init__(self, prompt_template: str) -> None:
        self._template = prompt_template

    def build(self, bundle: HealthSignalBundle, indicators: HealthIndicators, norm: NormalizedHealthSignals) -> str:
        interaction_text = bundle.interaction.summary or "No interaction summary available."
        knowledge_text = bundle.knowledge.summary or "No knowledge context available."

        return self._template.format(
            company=bundle.customer.company or "Unknown",
            region=bundle.customer.region or "Unknown",
            industry=bundle.customer.industry or "Unknown",
            account_type=bundle.customer.account_type or "Standard",
            acv_usd=norm.acv_usd,
            contract_active=norm.contract_active,
            rule_health_score=indicators.rule_health_score,
            renewal_approaching=indicators.renewal_approaching,
            declining_product_usage=indicators.declining_product_usage,
            high_support_load=indicators.high_support_load,
            known_product_limitations=indicators.known_product_limitations,
            critical_triggers=", ".join(indicators.critical_triggers) if indicators.critical_triggers else "None",
            usage_dau=bundle.crm.usage_dau if bundle.crm.usage_dau is not None else 0,
            usage_mau=bundle.crm.usage_mau if bundle.crm.usage_mau is not None else 0,
            usage_api_calls=bundle.crm.usage_api_calls if bundle.crm.usage_api_calls is not None else 0,
            support_open=bundle.crm.support_open_tickets,
            support_avg_time=bundle.crm.support_avg_resolution_time if bundle.crm.support_avg_resolution_time is not None else 0.0,
            opp_pipeline=bundle.crm.opportunities_pipeline_value,
            interaction_summary=interaction_text,
            knowledge_summary=knowledge_text
        )

# =============================================================================
# Section 3: Prompts
# =============================================================================

_HEALTH_ANALYSIS_PROMPT = """You are an expert Customer Success Analyst.
Your task is to analyze a customer account's health situation and provide a qualitative health synthesis report in **strict JSON** format.

## Input Data

### Customer Profile & Contract details
- Company Name: {company}
- Region: {region}
- Industry: {industry}
- Account Tier: {account_type}
- ACV (Annual Contract Value): ${acv_usd:,.2f}
- Active Contract: {contract_active}

### Deterministic Health Indicators (Rule Engine Outputs)
- Baseline Rule Score: {rule_health_score}/100
- Renewal Approaching: {renewal_approaching}
- Low Product Adoption: {declining_product_usage}
- High Support Load / Escalations: {high_support_load}
- Related Product/Platform Limitations: {known_product_limitations}
- Critical Triggers: {critical_triggers}

### CRM Details
- Usage Stats: Daily Active Users = {usage_dau}, Monthly Active Users = {usage_mau}, API Calls (30d) = {usage_api_calls}
- Support Stats: Open tickets = {support_open}, Average resolution time = {support_avg_time} hrs
- Opportunity Pipeline: Active pipeline value = ${opp_pipeline:,.2f}

### Interaction Summary (What happened in conversations)
{interaction_summary}

### Knowledge Context (Playbooks, known constraints, best practices)
{knowledge_summary}

## Output Format
Return ONLY a single, valid JSON object with the following fields. Do not include markdown formatting code fences or conversational prose.

{{
  "score": <integer from 0 to 100 reflecting the customer's health status (0 is absolute critical risk, 100 is perfectly healthy)>,
  "status": "<healthy | fair | poor | at_risk | critical>",
  "trend": "<improving | stable | declining>",
  "drivers": [
    "<key driver 1 (positive or negative impact factor)>",
    "<key driver 2>",
    ...
  ],
  "confidence": <float from 0.0 to 1.0 reflecting your assessment confidence>,
  "summary": "<concise 3-5 sentence narrative explaining the qualitative reason for this score and status>"
}}

## Groundedness & Evaluation Rules:
1. Ground your assessment ONLY in the provided input. Do not assume outside details.
2. The qualitative assessment must align with the input data. For example, if there are critical triggers like ESCALATED_SUPPORT_TICKET or SEVERE_NEGATIVE_SENTIMENT, status should reflect risk, and drivers must call out these issues.
3. Do NOT predict churn or recommend business actions (e.g. "We should contact them" or "They will churn in 30 days"). Limit the response to the health assessment itself.
4. Output STRICT JSON format.
"""

_SYSTEM_PROMPT = (
    "You are a customer relationship health scoring system. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

# =============================================================================
# Section 4: The Agent
# =============================================================================

class HealthAgent(BaseAgent):
    """
    HealthAgent evaluates the health of a customer relationship using interaction,
    knowledge, and CRM context.
    """
    agent_name: ClassVar[str] = "HealthAgent"

    description: ClassVar[str] = (
        "Evaluates customer relationship health using interaction, knowledge, and CRM intelligence."
    )

    required_inputs: ClassVar[list[str]] = [
        "analysis.interaction_analysis",
        "context.knowledge_context",
        "context.crm_context"
    ]

    produced_outputs: ClassVar[list[str]] = [
        "analysis.health_assessment"
    ]

    supported_execution_modes: ClassVar[list[str]] = [
        "LIVE",
        "DEBUG",
        "DRY_RUN",
        "SIMULATION"
    ]

    priority: ClassVar[int] = 80

    def __init__(
        self,
        llm_service=None,
        prompt_manager=None,
        state_validator=None,
        response_parser: ResponseParser | None = None,
        collector: HealthSignalCollector | None = None,
        normalizer: HealthSignalNormalizer | None = None,
        rule_engine: HealthRuleEngine | None = None,
        prompt_builder: HealthPromptBuilder | None = None
    ) -> None:
        super().__init__(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator
        )
        self._parser = response_parser or ResponseParser()
        self._collector = collector or HealthSignalCollector()
        self._normalizer = normalizer or HealthSignalNormalizer()
        self._rule_engine = rule_engine or HealthRuleEngine()
        self._prompt_builder = prompt_builder or HealthPromptBuilder(
            prompt_template=_HEALTH_ANALYSIS_PROMPT
        )

    async def validate_input(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> None:
        """
        Ensures that either interaction analysis or CRM data is available to prevent empty runs.
        """
        has_interaction = bool(state.analysis.interaction_analysis)
        has_crm = bool(state.context.crm_context)
        if not has_interaction and not has_crm:
            raise ValueError(
                "HealthAgent requires either analysis.interaction_analysis or context.crm_context to run."
            )

    async def execute(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> AgentResult:
        self._logger.info("[HealthAgent] HealthAgent Started")
        start_time = time.monotonic()

        # 1. Collect
        bundle = self._collector.collect(state)
        self._logger.info(
            "[HealthAgent] Signals Collected | Customer: %s, Sentiment: %s, ACV: %s",
            bundle.customer.company,
            bundle.interaction.sentiment,
            bundle.crm.contract_acv
        )
        self._record_metric("signals_collected", 20)  # Standard signal checklist count

        # 2. Normalize
        norm = self._normalizer.normalize(bundle)
        self._logger.info(
            "[HealthAgent] Signals Normalized | Sentiment: %.2f, Renewal Days: %s, DAU/MAU: %s",
            norm.sentiment_score,
            norm.days_until_renewal,
            f"{norm.dau_mau_ratio:.2f}" if norm.dau_mau_ratio is not None else "None"
        )

        # 3. Apply Rules
        indicators = self._rule_engine.evaluate(norm, bundle)
        self._logger.info(
            "[HealthAgent] Rules Evaluated | Base Score: %.1f, Critical Triggers: %d",
            indicators.rule_health_score,
            len(indicators.critical_triggers)
        )
        self._record_metric("rules_evaluated", 5)

        # 4. Build Prompt
        prompt = self._prompt_builder.build(bundle, indicators, norm)
        self._logger.info("[HealthAgent] Prompt Built | Length: %d", len(prompt))

        # 5. Call LLM
        self._logger.info("[HealthAgent] Invoking LLM for health synthesis evaluation.")
        llm_start = time.monotonic()
        response = await self.llm.generate_text(
            raw_prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=2048,
            cache_enabled=True
        )
        llm_latency = (time.monotonic() - llm_start) * 1000.0
        self._record_llm_call()
        self._record_metric("llm_latency_ms", round(llm_latency, 2))
        self._logger.info("[HealthAgent] LLM Completed | Latency: %.2fms", llm_latency)

        # 6. Parse and Validate
        try:
            assessment = self._parser.parse_json_as(response.text, HealthAssessment)
            self._logger.info(
                "[HealthAgent] Response Parsed | Score: %d, Status: %s, Trend: %s",
                assessment.score,
                assessment.status,
                assessment.trend
            )
            self._record_metric("health_confidence", assessment.confidence)
        except Exception as exc:
            self._logger.error("[HealthAgent] JSON Parse / Validation failed: %s", exc)
            self._add_warning(f"Fallback recovery applied due to parsing/validation exception: {exc}")
            
            # Formulate fallback assessment to prevent workflow crashing
            assessment = HealthAssessment(
                score=int(indicators.rule_health_score),
                status="at_risk" if indicators.critical_triggers else "fair",
                trend="stable",
                drivers=indicators.critical_triggers or ["Deterministic baseline fallback"],
                confidence=0.0,
                summary="[HealthAgent failed to parse LLM response — baseline deterministic values used as fallback]"
            )

        # Confirm score validation boundaries
        assessment = self._sanitize_assessment(assessment)
        self._logger.info("[HealthAgent] Validation Passed")

        # 7. Write State
        self._write_state(state, assessment)
        self._logger.info("[HealthAgent] Workflow Updated")

        output_data = assessment.model_dump(mode="json")
        duration_ms = (time.monotonic() - start_time) * 1000.0

        self._logger.info(
            "[HealthAgent] HealthAgent Finished | score=%d status=%s confidence=%.2f execution_time=%.2fms",
            assessment.score,
            assessment.status,
            assessment.confidence,
            duration_ms
        )

        return AgentResult.success_result(
            agent_name=self.agent_name,
            execution_time_ms=0.0,  # Overwritten by BaseAgent
            output_data=output_data,
            confidence=assessment.confidence,
            message=(
                f"Health assessment complete. Score: {assessment.score} ({assessment.status}). "
                f"Trend: {assessment.trend}."
            )
        )

    def _sanitize_assessment(self, assessment: HealthAssessment) -> HealthAssessment:
        score = max(0, min(100, assessment.score))
        confidence = max(0.0, min(1.0, assessment.confidence))
        if score != assessment.score or confidence != assessment.confidence:
            return assessment.model_copy(update={"score": score, "confidence": confidence})
        return assessment

    def _write_state(self, state: WorkflowState, assessment: HealthAssessment) -> None:
        payload = assessment.model_dump(mode="json")
        # Write ONLY to the canonical field 'health_assessment' (no dynamic health_analysis duplicates)
        state.analysis.health_assessment = payload

    async def handle_error(
        self,
        exc: Exception,
        state: WorkflowState,
        context: ExecutionContext
    ) -> AgentResult | None:
        """
        Fallback failure handler in case of severe runtime crashes.
        """
        if isinstance(exc, (LLMBaseError, LLMJSONParseError)):
            self._logger.warning("[HealthAgent] Handling LLM parsing error. Constructing stub fallback.")
            stub = HealthAssessment(
                score=50,
                status="fair",
                trend="stable",
                drivers=["LLM execution failure recovery"],
                confidence=0.0,
                summary="[HealthAgent encountered LLM error — partial data fallback applied]"
            )
            self._write_state(state, stub)
            return AgentResult.success_result(
                agent_name=self.agent_name,
                execution_time_ms=0.0,
                output_data=stub.model_dump(mode="json"),
                confidence=0.0,
                message="HealthAgent recovered from severe error using fallback stub."
            )
        return None
