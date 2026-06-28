"""
backend/agents/risk_agent.py
===========================
RiskAgent identifies, classifies, and prioritizes business risks affecting a customer relationship.

Single responsibility
---------------------
**Answer one question: "What business risks currently threaten this customer relationship?"**

This agent reads from the customer profile, interaction analysis, health assessment, 
knowledge context, and CRM context. It normalizes these signals, applies deterministic business rules, 
and uses the LLM to qualitatively evaluate and prioritize business risks.

It does NOT:
* Calculate customer health
* Retrieve CRM information
* Retrieve organizational knowledge
* Analyze conversations
* Recommend actions
* Explain recommendations
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

class RiskItem(BaseModel):
    """
    A specific identified business risk.
    """
    category: str = Field(description="Risk category: financial, product, support, sentiment, adoption, other.")
    severity: str = Field(description="Risk severity: low, medium, high, critical.")
    probability: float = Field(ge=0.0, le=1.0, description="Probability of risk occurrence [0.0, 1.0].")
    impact: float = Field(ge=0.0, le=1.0, description="Business impact of risk [0.0, 1.0].")
    evidence: str = Field(description="Grounding evidence for risk identification.")
    description: str = Field(description="Narrative description of the risk.")

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"financial", "product", "support", "sentiment", "adoption", "other"}
        if normalised in allowed:
            return normalised
        return "other"

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"low", "medium", "high", "critical"}
        if normalised in allowed:
            return normalised
        return "medium"


class RiskAssessment(BaseModel):
    """
    Strongly typed Pydantic model representing the output of RiskAgent.
    """
    overall_level: str = Field(description="Overall customer risk level: low, medium, high, critical.")
    identified_risks: list[RiskItem] = Field(default_factory=list, description="List of identified risk items.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this assessment [0.0, 1.0].")
    summary: str = Field(min_length=10, description="Concise qualitative summary of the risk situation.")

    @field_validator("overall_level")
    @classmethod
    def _validate_level(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"low", "medium", "high", "critical"}
        if normalised in allowed:
            return normalised
        return "medium"

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


class HealthSignals(BaseModel):
    """
    Grouped customer health signals from HealthAgent.
    """
    score: Optional[int] = None
    status: Optional[str] = None
    trend: Optional[str] = None
    drivers: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


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


class RiskSignalBundle(BaseModel):
    """
    Logical grouping of business signals collected from WorkflowState.
    """
    customer: CustomerSignals
    health: HealthSignals
    interaction: InteractionSignals
    knowledge: KnowledgeSignals
    crm: CRMSignals


class RiskSignalCollector:
    """
    Responsible for extracting all customer signals from WorkflowState.
    """
    def collect(self, state: WorkflowState) -> RiskSignalBundle:
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

        # Health Assessment
        ha = state.analysis.health_assessment or {}
        health_signals = HealthSignals(
            score=ha.get("score"),
            status=ha.get("status"),
            trend=ha.get("trend"),
            drivers=ha.get("drivers") or [],
            summary=ha.get("summary")
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

        return RiskSignalBundle(
            customer=customer_signals,
            health=health_signals,
            interaction=interaction_signals,
            knowledge=knowledge_signals,
            crm=crm_signals
        )


class NormalizedRiskSignals(BaseModel):
    """
    Cleaned, typed, and normalized risk metrics.
    """
    days_until_renewal: Optional[int] = None
    dau_mau_ratio: Optional[float] = None
    open_tickets_count: int
    escalated_support: bool
    acv_usd: float
    health_score: Optional[int] = None
    sentiment_score: float
    commitments_count: int


class RiskSignalNormalizer:
    """
    Normalizes collected signals into consistent formats.
    """
    def normalize(self, bundle: RiskSignalBundle) -> NormalizedRiskSignals:
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

        # Determine sentiment score
        score = bundle.interaction.sentiment_score
        if score is None:
            sentiment_map = {"positive": 0.5, "neutral": 0.0, "negative": -0.5, "mixed": -0.1}
            score = sentiment_map.get(str(bundle.interaction.sentiment).lower(), 0.0)
        else:
            score = max(-1.0, min(1.0, float(score)))

        return NormalizedRiskSignals(
            days_until_renewal=days_until,
            dau_mau_ratio=dau_mau_ratio,
            open_tickets_count=bundle.crm.support_open_tickets,
            escalated_support=bundle.crm.support_escalated,
            acv_usd=bundle.crm.contract_acv or 0.0,
            health_score=bundle.health.score,
            sentiment_score=score,
            commitments_count=bundle.interaction.commitments_count
        )


class RiskIndicators(BaseModel):
    """
    Deterministic risk evaluation flags computed by the rule engine.
    """
    renewal_approaching: bool
    declining_health: bool
    repeated_negative_sentiment: bool
    high_support_load: bool
    escalated_tickets: bool
    low_product_adoption: bool
    large_revenue_exposure: bool
    known_platform_limitations: bool


class RiskRuleEngine:
    """
    Evaluates deterministic business rules based on normalized metrics.
    """
    def evaluate(self, norm: NormalizedRiskSignals, bundle: RiskSignalBundle) -> RiskIndicators:
        renewal_approaching = False
        if norm.days_until_renewal is not None and norm.days_until_renewal <= 90:
            renewal_approaching = True

        declining_health = False
        if norm.health_score is not None and norm.health_score < 60:
            declining_health = True

        repeated_sentiment = norm.sentiment_score < -0.15
        high_support = norm.open_tickets_count >= 2
        low_adoption = norm.dau_mau_ratio is not None and norm.dau_mau_ratio < 0.15
        large_revenue = norm.acv_usd > 100000.0
        has_limitations = len(bundle.knowledge.limitations) > 0

        return RiskIndicators(
            renewal_approaching=renewal_approaching,
            declining_health=declining_health,
            repeated_negative_sentiment=repeated_sentiment,
            high_support_load=high_support,
            escalated_tickets=norm.escalated_support,
            low_product_adoption=low_adoption,
            large_revenue_exposure=large_revenue,
            known_platform_limitations=has_limitations
        )


class RiskPromptBuilder:
    """
    Formats the context for the LLM qualitative analysis.
    """
    def __init__(self, prompt_template: str) -> None:
        self._template = prompt_template

    def build(self, bundle: RiskSignalBundle, indicators: RiskIndicators, norm: NormalizedRiskSignals) -> str:
        interaction_text = bundle.interaction.summary or "No interaction summary available."
        knowledge_text = bundle.knowledge.summary or "No knowledge context available."

        return self._template.format(
            company=bundle.customer.company or "Unknown",
            region=bundle.customer.region or "Unknown",
            industry=bundle.customer.industry or "Unknown",
            account_type=bundle.customer.account_type or "Standard",
            acv_usd=norm.acv_usd,
            health_score=norm.health_score if norm.health_score is not None else "Unknown",
            health_status=bundle.health.status or "Unknown",
            health_trend=bundle.health.trend or "Unknown",
            health_drivers=", ".join(bundle.health.drivers) if bundle.health.drivers else "None",
            health_summary=bundle.health.summary or "None",
            renewal_approaching=indicators.renewal_approaching,
            declining_health=indicators.declining_health,
            repeated_negative_sentiment=indicators.repeated_negative_sentiment,
            high_support_load=indicators.high_support_load,
            escalated_tickets=indicators.escalated_tickets,
            low_product_adoption=indicators.low_product_adoption,
            large_revenue_exposure=indicators.large_revenue_exposure,
            known_platform_limitations=indicators.known_platform_limitations,
            usage_dau=bundle.crm.usage_dau if bundle.crm.usage_dau is not None else 0,
            usage_mau=bundle.crm.usage_mau if bundle.crm.usage_mau is not None else 0,
            usage_api_calls=bundle.crm.usage_api_calls if bundle.crm.usage_api_calls is not None else 0,
            support_open=bundle.crm.support_open_tickets,
            support_escalated=bundle.crm.support_escalated,
            opp_count=bundle.crm.opportunities_active_count,
            opp_val=bundle.crm.opportunities_pipeline_value,
            interaction_summary=interaction_text,
            knowledge_summary=knowledge_text
        )

# =============================================================================
# Section 3: Prompts
# =============================================================================

_RISK_ANALYSIS_PROMPT = """You are an expert Customer Success Risk Analyst.
Your task is to analyze a customer account's situation and identify, classify, and prioritize any business risks in **strict JSON** format.

## Input Data

### Customer Profile
- Company Name: {company}
- Region: {region}
- Industry: {industry}
- Account Tier: {account_type}
- ACV: ${acv_usd:,.2f}

### Health Assessment (from HealthAgent)
- Health Score: {health_score}/100
- Health Status: {health_status}
- Health Trend: {health_trend}
- Health Drivers: {health_drivers}
- Health Summary: {health_summary}

### Deterministic Risk Indicators (Rule Engine Outputs)
- Renewal Approaching: {renewal_approaching}
- Declining Health: {declining_health}
- Repeated Negative Sentiment: {repeated_negative_sentiment}
- High Support Load: {high_support_load}
- Escalated Tickets: {escalated_tickets}
- Low Product Adoption: {low_product_adoption}
- Large Revenue Exposure: {large_revenue_exposure}
- Related Platform Limitations: {known_platform_limitations}

### CRM Details
- Usage Stats: Daily Active Users = {usage_dau}, Monthly Active Users = {usage_mau}, API Calls (30d) = {usage_api_calls}
- Support Stats: Open tickets = {support_open}, Escalated tickets = {support_escalated}
- Opportunities: Pipeline opportunities count = {opp_count}, Value = ${opp_val:,.2f}

### Interaction Summary (Recent conversation highlights)
{interaction_summary}

### Knowledge Context (Related limitations or best practices)
{knowledge_summary}

## Output Format
Return ONLY a single, valid JSON object with the following fields. Do not include markdown code blocks or conversational prose.

{{
  "overall_level": "<low | medium | high | critical>",
  "identified_risks": [
    {{
      "category": "<financial | product | support | sentiment | adoption | other>",
      "severity": "<low | medium | high | critical>",
      "probability": <float from 0.0 to 1.0 representing the likelihood of risk occurring>,
      "impact": <float from 0.0 to 1.0 representing the customer relationship impact of this risk>,
      "evidence": "<the specific text snippet, metric, or event from inputs confirming this risk>",
      "description": "<detailed explanation of what the risk is and how it threatens the account>"
    }}
  ],
  "confidence": <float from 0.0 to 1.0 representing your evaluation confidence>,
  "summary": "<concise 3-5 sentence narrative of the overall risk assessment>"
}}

## Groundedness & Evaluation Rules:
1. Ground every identified risk ONLY in the provided input. Do not assume outside details.
2. Every risk item must have concrete evidence cited from the input text or indicators.
3. Prioritize risks in the "identified_risks" list from highest severity/impact to lowest.
4. Do NOT recommend actions (e.g. "We should run a QBR"). Limit response to risk identification and classification.
5. Do NOT predict future business outcomes beyond the current risk assessment (e.g. do not state "They will definitely churn next week").
6. Output STRICT JSON only. Do not include markdown code blocks (e.g. ```json ... ```) or any surrounding conversational filler text. Your entire response must be the JSON object and nothing else.
"""

_SYSTEM_PROMPT = (
    "You are a customer relationship risk scoring system. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

# =============================================================================
# Section 4: The Agent
# =============================================================================

class RiskAgent(BaseAgent):
    """
    RiskAgent identifies, classifies, and prioritizes business risks affecting customer relationships.
    """
    agent_name: ClassVar[str] = "RiskAgent"

    description: ClassVar[str] = (
        "Identifies, classifies, and prioritizes business risks affecting customer relationships."
    )

    required_inputs: ClassVar[list[str]] = [
        "analysis.interaction_analysis",
        "analysis.health_assessment",
        "context.knowledge_context",
        "context.crm_context"
    ]

    produced_outputs: ClassVar[list[str]] = [
        "analysis.risk_assessment"
    ]

    supported_execution_modes: ClassVar[list[str]] = [
        "LIVE",
        "DEBUG",
        "DRY_RUN",
        "SIMULATION"
    ]

    priority: ClassVar[int] = 75

    def __init__(
        self,
        llm_service=None,
        prompt_manager=None,
        state_validator=None,
        response_parser: ResponseParser | None = None,
        collector: RiskSignalCollector | None = None,
        normalizer: RiskSignalNormalizer | None = None,
        rule_engine: RiskRuleEngine | None = None,
        prompt_builder: RiskPromptBuilder | None = None
    ) -> None:
        super().__init__(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator
        )
        self._parser = response_parser or ResponseParser()
        self._collector = collector or RiskSignalCollector()
        self._normalizer = normalizer or RiskSignalNormalizer()
        self._rule_engine = rule_engine or RiskRuleEngine()
        self._prompt_builder = prompt_builder or RiskPromptBuilder(
            prompt_template=_RISK_ANALYSIS_PROMPT
        )

    async def validate_input(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> None:
        """
        Ensures that interaction analysis or health assessment is available to prevent running on empty data.
        """
        has_interaction = bool(state.analysis.interaction_analysis)
        has_health = bool(state.analysis.health_assessment)
        if not has_interaction and not has_health:
            raise ValueError(
                "RiskAgent requires either analysis.interaction_analysis or analysis.health_assessment to run."
            )

    async def execute(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> AgentResult:
        self._logger.info("[RiskAgent] RiskAgent Started")
        start_time = time.monotonic()

        # 1. Collect
        bundle = self._collector.collect(state)
        self._logger.info(
            "[RiskAgent] Signals Collected | Customer: %s, Sentiment: %s, Health status: %s",
            bundle.customer.company,
            bundle.interaction.sentiment,
            bundle.health.status
        )
        self._record_metric("signals_collected", 25)

        # 2. Normalize
        norm = self._normalizer.normalize(bundle)
        self._logger.info(
            "[RiskAgent] Signals Normalized | Sentiment: %.2f, Open tickets: %d, ACV: %.2f",
            norm.sentiment_score,
            norm.open_tickets_count,
            norm.acv_usd
        )

        # 3. Apply Rules
        indicators = self._rule_engine.evaluate(norm, bundle)
        self._logger.info(
            "[RiskAgent] Rules Evaluated | Renewal approach: %s, Declining health: %s, Low adoption: %s",
            indicators.renewal_approaching,
            indicators.declining_health,
            indicators.low_product_adoption
        )
        self._record_metric("rules_evaluated", 8)

        # 4. Build Prompt
        prompt = self._prompt_builder.build(bundle, indicators, norm)
        self._logger.info("[RiskAgent] Prompt Built | Length: %d", len(prompt))

        # 5. Call LLM
        self._logger.info("[RiskAgent] Invoking LLM for qualitative risk evaluation.")
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
        self._logger.info("[RiskAgent] LLM Completed | Latency: %.2fms", llm_latency)

        # 6. Parse and Validate
        self._logger.debug("[RiskAgent] Raw LLM response (len=%d): %s", len(response.text), response.text[:800])
        try:
            assessment = self._parser.parse_json_as(response.text, RiskAssessment)
            self._logger.info(
                "[RiskAgent] Response Parsed | Level: %s, Confidence: %.2f, Risks: %d",
                assessment.overall_level,
                assessment.confidence,
                len(assessment.identified_risks)
            )
            self._record_metric("confidence", assessment.confidence)
        except Exception as exc:
            self._logger.error("[RiskAgent] JSON Parse / Validation failed: %s", exc)
            self._add_warning(f"Fallback recovery applied due to parsing/validation exception: {exc}")
            
            # Formulate fallback assessment to prevent workflow crashing
            fallback_risks = []
            if indicators.renewal_approaching:
                fallback_risks.append(RiskItem(
                    category="financial",
                    severity="high",
                    probability=0.8,
                    impact=0.7,
                    evidence="CRM renewal target date is approaching.",
                    description="Upcoming renewal under high risk scenario."
                ))
            if indicators.declining_health or indicators.low_product_adoption:
                fallback_risks.append(RiskItem(
                    category="adoption",
                    severity="high",
                    probability=0.7,
                    impact=0.8,
                    evidence="Low DAU/MAU adoption or declining health score.",
                    description="Low product adoption threatens the account value."
                ))
                
            assessment = RiskAssessment(
                overall_level="high" if fallback_risks else "medium",
                identified_risks=fallback_risks,
                confidence=0.0,
                summary="[RiskAgent failed to parse LLM response — deterministic rules used as fallback]"
            )

        # Sanitize boundaries
        assessment = self._sanitize_assessment(assessment)
        self._logger.info("[RiskAgent] Validation Passed")

        # Log specific risk metrics
        high_risks = sum(1 for r in assessment.identified_risks if r.severity == "high")
        critical_risks = sum(1 for r in assessment.identified_risks if r.severity == "critical")
        self._record_metric("risk_indicators_generated", len(assessment.identified_risks))
        self._record_metric("high_risks_detected", high_risks)
        self._record_metric("critical_risks_detected", critical_risks)

        # 7. Write State
        self._write_state(state, assessment)
        self._logger.info("[RiskAgent] Workflow Updated")

        output_data = assessment.model_dump(mode="json")
        duration_ms = (time.monotonic() - start_time) * 1000.0

        self._logger.info(
            "[RiskAgent] RiskAgent Finished | overall_level=%s risks=%d confidence=%.2f execution_time=%.2fms",
            assessment.overall_level,
            len(assessment.identified_risks),
            assessment.confidence,
            duration_ms
        )

        return AgentResult.success_result(
            agent_name=self.agent_name,
            execution_time_ms=0.0,  # Overwritten by BaseAgent
            output_data=output_data,
            confidence=assessment.confidence,
            message=(
                f"Risk assessment complete. Overall Risk Level: {assessment.overall_level}. "
                f"Identified {len(assessment.identified_risks)} risk(s)."
            )
        )

    def _sanitize_assessment(self, assessment: RiskAssessment) -> RiskAssessment:
        confidence = max(0.0, min(1.0, assessment.confidence))
        sanitized_risks = []
        for risk in assessment.identified_risks:
            prob = max(0.0, min(1.0, risk.probability))
            imp = max(0.0, min(1.0, risk.impact))
            if prob != risk.probability or imp != risk.impact:
                sanitized_risks.append(risk.model_copy(update={"probability": prob, "impact": imp}))
            else:
                sanitized_risks.append(risk)
                
        if confidence != assessment.confidence or len(sanitized_risks) != len(assessment.identified_risks):
            return assessment.model_copy(update={"confidence": confidence, "identified_risks": sanitized_risks})
        return assessment

    def _write_state(self, state: WorkflowState, assessment: RiskAssessment) -> None:
        # Write ONLY to risk_assessment field as the single canonical source of truth
        state.analysis.risk_assessment = assessment.model_dump(mode="json")

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
            self._logger.warning("[RiskAgent] Handling LLM parsing error. Constructing stub fallback.")
            stub = RiskAssessment(
                overall_level="medium",
                identified_risks=[],
                confidence=0.0,
                summary="[RiskAgent encountered LLM error — partial data fallback applied]"
            )
            self._write_state(state, stub)
            return AgentResult.success_result(
                agent_name=self.agent_name,
                execution_time_ms=0.0,
                output_data=stub.model_dump(mode="json"),
                confidence=0.0,
                message="RiskAgent recovered from severe error using fallback stub."
            )
        return None
