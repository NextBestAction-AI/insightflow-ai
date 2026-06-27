"""
backend/agents/reasoning_agent.py
=================================
ReasoningAgent synthesizes all previously generated business intelligence into a coherent 
explanation of the customer's current business situation.

Single responsibility
---------------------
**Answer one question: "Given everything we know, what is the complete business situation for this customer?"**

This agent reads from the customer profile, interaction analysis, health assessment, 
risk assessment, knowledge context, and CRM context. It compiles these inputs, 
builds a structured narrative outline, and uses the LLM to qualitatively explain 
the connections between customer behavior and business indicators.

It does NOT:
* Retrieve CRM information
* Retrieve organizational knowledge
* Analyze conversations
* Calculate customer health
* Detect business risks
* Recommend actions
* Generate customer communications
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

class KeyFinding(BaseModel):
    """
    A synthesized key finding connecting multiple facts.
    """
    title: str = Field(description="Finding title (e.g. 'Adoption Drop aligned with Renewal').")
    reasoning: str = Field(description="Synthesized reasoning explaining the connection.")
    evidence: str = Field(description="Specific evidence / metrics supporting the finding.")


class BusinessContext(BaseModel):
    """
    Structured categories classifying the customer's current business situation.
    """
    customer_stage: str = Field(description="onboarding, adoption, renewal, expansion, other.")
    relationship_status: str = Field(description="stable, at_risk, escalated, critical.")
    product_adoption: str = Field(description="high, medium, low, declining.")
    support_state: str = Field(description="stable, normal, high_load, escalated, critical.")

    @field_validator("customer_stage")
    @classmethod
    def _validate_stage(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"onboarding", "adoption", "renewal", "expansion", "other"}
        if normalised in allowed:
            return normalised
        return "other"

    @field_validator("relationship_status")
    @classmethod
    def _validate_status(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"stable", "at_risk", "escalated", "critical"}
        if normalised in allowed:
            return normalised
        return "stable"

    @field_validator("product_adoption")
    @classmethod
    def _validate_adoption(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"high", "medium", "low", "declining"}
        if normalised in allowed:
            return normalised
        return "medium"

    @field_validator("support_state")
    @classmethod
    def _validate_support(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"stable", "normal", "high_load", "escalated", "critical"}
        if normalised in allowed:
            return normalised
        return "normal"


class BusinessReasoning(BaseModel):
    """
    Strongly typed Pydantic model representing the output of ReasoningAgent.
    """
    overall_assessment: str = Field(description="Qualitative assessment level (e.g. stable, review_needed, critical_escalation).")
    business_context: BusinessContext = Field(description="Categorical status indicators.")
    key_findings: list[KeyFinding] = Field(default_factory=list, description="Synthesized analytical findings.")
    supporting_facts: list[str] = Field(default_factory=list, description="Verifiable evidence facts.")
    confidence: float = Field(ge=0.0, le=1.0, description="LLM's confidence score [0.0, 1.0].")
    summary: str = Field(min_length=10, description="narrative summary of the customer's business situation.")

    @field_validator("overall_assessment")
    @classmethod
    def _validate_assessment(cls, v: Any) -> str:
        normalised = str(v).lower().strip().replace(" ", "_")
        allowed = {"healthy", "stable", "at_risk", "critical_escalation", "review_needed"}
        if normalised in allowed:
            return normalised
        return "review_needed"

# =============================================================================
# Section 2: Helper Data Structures & Components
# =============================================================================

class CustomerContext(BaseModel):
    """
    Grouped customer demographic context.
    """
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    account_type: Optional[str] = None
    region: Optional[str] = None
    annual_revenue_usd: Optional[float] = None
    employee_count: Optional[int] = None


class InteractionContext(BaseModel):
    """
    Grouped conversational interaction context.
    """
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    urgency: Optional[str] = None
    commitments_count: int = 0
    issues: list[dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None


class KnowledgeContext(BaseModel):
    """
    Grouped vector documentation search context.
    """
    summary: Optional[str] = None
    citations: list[str] = Field(default_factory=list)
    best_practices: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CRMContext(BaseModel):
    """
    Grouped enterprise CRM parameters.
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


class HealthContext(BaseModel):
    """
    Grouped customer health score assessment context.
    """
    score: Optional[int] = None
    status: Optional[str] = None
    trend: Optional[str] = None
    drivers: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


class RiskContext(BaseModel):
    """
    Grouped risk evaluation factors from RiskAgent.
    """
    overall_level: Optional[str] = None
    identified_risks: list[dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    confidence: Optional[float] = None


class ReasoningContextBundle(BaseModel):
    """
    Structured bundle of all context categories feeding the narrative and prompt.
    """
    customer: CustomerContext
    interaction: InteractionContext
    knowledge: KnowledgeContext
    crm: CRMContext
    health: HealthContext
    risk: RiskContext


class ReasoningContextCollector:
    """
    Responsible for extracting all synthesized inputs from WorkflowState.
    """
    def collect(self, state: WorkflowState) -> ReasoningContextBundle:
        # Customer
        customer = CustomerContext(
            customer_id=state.customer.customer_id,
            customer_name=state.customer.customer_name,
            company=state.customer.company,
            industry=state.customer.industry,
            account_type=state.customer.account_type,
            region=state.customer.region,
            annual_revenue_usd=state.customer.annual_revenue_usd,
            employee_count=state.customer.employee_count
        )

        # Interaction
        ia = state.analysis.interaction_analysis or {}
        sentiment_score = state.analysis.sentiment_score
        if sentiment_score is None:
            sentiment_score = ia.get("sentiment_score")

        interaction = InteractionContext(
            sentiment=ia.get("sentiment"),
            sentiment_score=sentiment_score,
            urgency=ia.get("urgency"),
            commitments_count=len(ia.get("commitments") or []),
            issues=ia.get("issues") or [],
            summary=ia.get("summary")
        )

        # Knowledge
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

        knowledge = KnowledgeContext(
            summary=knowledge_summary,
            citations=knowledge_citations,
            best_practices=knowledge_best_practices,
            limitations=knowledge_limitations
        )

        # CRM
        crm_ctx = state.context.crm_context or {}
        profile = crm_ctx.get("profile") or {}
        contract = crm_ctx.get("contract") or {}
        renewal = crm_ctx.get("renewal") or {}
        usage = crm_ctx.get("usage") or {}
        support = crm_ctx.get("support") or {}
        opp = crm_ctx.get("opportunities") or {}

        # Merge profile parameters if missing
        if not customer.industry:
            customer.industry = profile.get("industry")
        if not customer.account_type:
            customer.account_type = profile.get("account_type")
        if not customer.region:
            customer.region = profile.get("region")
        if not customer.employee_count:
            customer.employee_count = profile.get("employee_count")

        crm = CRMContext(
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

        # Health
        ha = state.analysis.health_assessment or {}
        health = HealthContext(
            score=ha.get("score"),
            status=ha.get("status"),
            trend=ha.get("trend"),
            drivers=ha.get("drivers") or [],
            summary=ha.get("summary")
        )

        # Risk
        ra = state.analysis.risk_assessment or {}
        risk = RiskContext(
            overall_level=ra.get("overall_level"),
            identified_risks=ra.get("identified_risks") or [],
            summary=ra.get("summary"),
            confidence=ra.get("confidence")
        )

        return ReasoningContextBundle(
            customer=customer,
            interaction=interaction,
            knowledge=knowledge,
            crm=crm,
            health=health,
            risk=risk
        )


class BusinessNarrativeBuilder:
    """
    Organizes facts and structures inputs for qualitative reasoning.
    """
    def build_narrative_context(self, bundle: ReasoningContextBundle) -> str:
        lines = []

        # Customer demographics overview
        company = bundle.customer.company or "the customer"
        tier = bundle.customer.account_type or "Standard"
        lines.append(
            f"Account: {company} is a {tier} tier customer operating in region {bundle.customer.region or 'Unknown'}."
        )

        # Health / Risk Overview
        h_score = f"{bundle.health.score}/100" if bundle.health.score is not None else "Unknown"
        r_level = bundle.risk.overall_level or "Unknown"
        lines.append(
            f"Status: Current Health Score is {h_score} ({bundle.health.status or 'Unknown'} / trend: {bundle.health.trend or 'stable'}), "
            f"aligned with a Risk Profile level of '{r_level}'."
        )

        # Renewal Context
        if bundle.crm.renewal_date:
            likelihood = f"{bundle.crm.renewal_likelihood * 100:.0f}%" if bundle.crm.renewal_likelihood is not None else "Unknown"
            lines.append(
                f"Commercial Risk Exposure: ACV is ${bundle.crm.contract_acv or 0.0:,.2f} with renewal scheduled for {bundle.crm.renewal_date} "
                f"(Renewal likelihood currently estimated at {likelihood})."
            )

        # Support tickets vs Customer Urgency
        open_tickets = bundle.crm.support_open_tickets
        escalated_str = "escalated" if bundle.crm.support_escalated else "normal"
        lines.append(
            f"Operational Support: There are {open_tickets} active support ticket(s) in {escalated_str} state. "
            f"Conversation analysis notes customer urgency is '{bundle.interaction.urgency or 'normal'}' "
            f"with a sentiment score of {bundle.interaction.sentiment_score or 0.0:.2f}."
        )

        # Telemetry usage
        dau = bundle.crm.usage_dau or 0
        mau = bundle.crm.usage_mau or 0
        ratio = (dau / mau) if mau > 0 else 0.0
        lines.append(
            f"Product Usage Telemetry: Daily active users = {dau}, Monthly active users = {mau} "
            f"(DAU/MAU adoption ratio = {ratio:.2f}). Total API calls in the past 30 days = {bundle.crm.usage_api_calls or 0}."
        )

        return "\n".join(lines)


class ReasoningPromptBuilder:
    """
    Formats prompt inputs for the LLM business reasoning.
    """
    def __init__(self, prompt_template: str) -> None:
        self._template = prompt_template

    def build(
        self, 
        bundle: ReasoningContextBundle, 
        narrative: str
    ) -> str:
        interaction_text = bundle.interaction.summary or "No interaction summary available."
        knowledge_text = bundle.knowledge.summary or "No knowledge context available."
        health_drivers = ", ".join(bundle.health.drivers) if bundle.health.drivers else "None"
        health_summary = bundle.health.summary or "None"
        risk_summary = bundle.risk.summary or "None"
        
        # Format risk items for LLM review
        risk_items_list = []
        for r in bundle.risk.identified_risks:
            risk_items_list.append(
                f"- Category: {r.get('category')}, Severity: {r.get('severity')}, Prob: {r.get('probability')}, "
                f"Impact: {r.get('impact')}, Evidence: '{r.get('evidence')}', Desc: {r.get('description')}"
            )
        risk_items_text = "\n".join(risk_items_list) if risk_items_list else "No risks identified."

        return self._template.format(
            company=bundle.customer.company or "Unknown",
            region=bundle.customer.region or "Unknown",
            industry=bundle.customer.industry or "Unknown",
            account_type=bundle.customer.account_type or "Standard",
            health_score=bundle.health.score if bundle.health.score is not None else "Unknown",
            health_status=bundle.health.status or "Unknown",
            health_trend=bundle.health.trend or "Unknown",
            health_drivers=health_drivers,
            health_summary=health_summary,
            risk_level=bundle.risk.overall_level or "Unknown",
            risk_summary=risk_summary,
            risk_items=risk_items_text,
            contract_active="Active" if bundle.crm.contract_active else "Inactive",
            acv_usd=bundle.crm.contract_acv or 0.0,
            renewal_date=bundle.crm.renewal_date or "Unknown",
            renewal_likelihood=bundle.crm.renewal_likelihood if bundle.crm.renewal_likelihood is not None else "Unknown",
            support_open=bundle.crm.support_open_tickets,
            support_escalated=bundle.crm.support_escalated,
            usage_dau=bundle.crm.usage_dau if bundle.crm.usage_dau is not None else 0,
            usage_mau=bundle.crm.usage_mau if bundle.crm.usage_mau is not None else 0,
            interaction_summary=interaction_text,
            knowledge_summary=knowledge_text,
            prepared_narrative=narrative
        )

# =============================================================================
# Section 3: Prompts
# =============================================================================

_REASONING_PROMPT = """You are an expert Customer Success Director and Lead Business Strategist.
Your task is to analyze all currently available business intelligence for a customer account and synthesize it into a coherent business reasoning report in **strict JSON** format.

## Input Data

### Customer Profile
- Company Name: {company}
- Region: {region}
- Industry: {industry}
- Account Tier: {account_type}

### Health Assessment (from HealthAgent)
- Health Score: {health_score}/100
- Health Status: {health_status}
- Health Trend: {health_trend}
- Health Drivers: {health_drivers}
- Health Summary: {health_summary}

### Risk Assessment (from RiskAgent)
- Overall Risk Level: {risk_level}
- Risk Assessment Summary: {risk_summary}
- Identified Risk Items:
{risk_items}

### CRM Context
- Contract active: {contract_active}
- Contract ACV: ${acv_usd:,.2f}
- Renewal date: {renewal_date}
- Renewal likelihood: {renewal_likelihood}
- Open support tickets: {support_open}
- Support escalation status: {support_escalated}
- Product usage DAU: {usage_dau}, MAU: {usage_mau}

### Interaction Summary (Recent conversation highlights)
{interaction_summary}

### Knowledge Context (Related limitations or best practices)
{knowledge_summary}

### Prepared Narrative Evidence Outline
{prepared_narrative}

## Output Format
Return ONLY a single, valid JSON object with the following fields. Do not include markdown code blocks or conversational prose.

{{
  "overall_assessment": "<healthy | stable | at_risk | critical_escalation | review_needed>",
  "business_context": {{
    "customer_stage": "<onboarding | adoption | renewal | expansion | other>",
    "relationship_status": "<stable | at_risk | escalated | critical>",
    "product_adoption": "<high | medium | low | declining>",
    "support_state": "<stable | normal | high_load | escalated | critical>"
  }},
  "key_findings": [
    {{
      "title": "<descriptive title (e.g. 'Adoption Drop aligned with upcoming Renewal')>",
      "reasoning": "<synthesized reasoning explaining why this finding exists by connecting customer behavior, CRM metrics, and risks>",
      "evidence": "<the specific evidence and metrics from the inputs that support this finding>"
    }}
  ],
  "supporting_facts": [
    "<concrete fact 1 (e.g. 'Open support escalation on API downtime since June 25th')>",
    "<concrete fact 2>",
    ...
  ],
  "confidence": <float from 0.0 to 1.0 representing your evaluation confidence>,
  "summary": "<concise 3-5 sentence narrative summarizing the complete business situation of this customer>"
}}

## Groundedness & Reasoning Rules:
1. Connect customer behavior (Interaction sentiment/urgency/issues) with business metrics (CRM usage telemetry/contracts/renewals), health scores, and risk classifications.
2. Explain *why* the customer is in their current state based on these relationships (e.g., how support escalations or product limitations correlate with declining usage and low renewal likelihood).
3. Do NOT recommend actions (e.g., do not say "We should schedule a meeting"). Only explain the situation.
4. Do NOT calculate new scores or invent new facts. Use only the provided information.
5. Output STRICT JSON format.
"""

_SYSTEM_PROMPT = (
    "You are a customer relationship business reasoning system. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

# =============================================================================
# Section 4: The Agent
# =============================================================================

class ReasoningAgent(BaseAgent):
    """
    ReasoningAgent builds a coherent business understanding by synthesizing interaction,
    CRM, health, risk, and knowledge intelligence.
    """
    agent_name: ClassVar[str] = "ReasoningAgent"

    description: ClassVar[str] = (
        "Builds a coherent business understanding by synthesizing interaction, CRM, health, risk, and knowledge intelligence."
    )

    required_inputs: ClassVar[list[str]] = [
        "analysis.interaction_analysis",
        "analysis.health_assessment",
        "analysis.risk_assessment",
        "context.knowledge_context",
        "context.crm_context"
    ]

    produced_outputs: ClassVar[list[str]] = [
        "analysis.business_reasoning"
    ]

    supported_execution_modes: ClassVar[list[str]] = [
        "LIVE",
        "DEBUG",
        "DRY_RUN",
        "SIMULATION"
    ]

    priority: ClassVar[int] = 70

    def __init__(
        self,
        llm_service=None,
        prompt_manager=None,
        state_validator=None,
        response_parser: ResponseParser | None = None,
        collector: ReasoningContextCollector | None = None,
        narrative_builder: BusinessNarrativeBuilder | None = None,
        prompt_builder: ReasoningPromptBuilder | None = None
    ) -> None:
        super().__init__(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator
        )
        self._parser = response_parser or ResponseParser()
        self._collector = collector or ReasoningContextCollector()
        self._narrative_builder = narrative_builder or BusinessNarrativeBuilder()
        self._prompt_builder = prompt_builder or ReasoningPromptBuilder(
            prompt_template=_REASONING_PROMPT
        )

    async def validate_input(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> None:
        """
        Ensure that key preceding agents have written outputs to WorkflowState.
        """
        has_health = bool(state.analysis.health_assessment)
        has_risk = bool(state.analysis.risk_assessment)
        if not has_health and not has_risk:
            raise ValueError(
                "ReasoningAgent requires either health_assessment or risk_assessment to run."
            )

    async def execute(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> AgentResult:
        self._logger.info("[ReasoningAgent] ReasoningAgent Started")
        start_time = time.monotonic()

        # 1. Collect
        bundle = self._collector.collect(state)
        self._logger.info("[ReasoningAgent] Context Collected")
        self._record_metric("contexts_collected", 6)

        # 2. Build Business Narrative context outline
        narrative = self._narrative_builder.build_narrative_context(bundle)
        self._logger.info("[ReasoningAgent] Narrative Prepared")

        # 3. Build Prompt
        prompt = self._prompt_builder.build(bundle, narrative)
        self._logger.info("[ReasoningAgent] Prompt Built")

        # 4. Call LLM
        self._logger.info("[ReasoningAgent] Invoking LLM for business reasoning synthesis.")
        llm_start = time.monotonic()
        response = await self.llm.generate_text(
            raw_prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=2560,
            cache_enabled=True
        )
        llm_latency = (time.monotonic() - llm_start) * 1000.0
        self._record_llm_call()
        self._record_metric("llm_latency_ms", round(llm_latency, 2))
        self._logger.info("[ReasoningAgent] LLM Completed")

        # 5. Parse and Validate
        try:
            reasoning = self._parser.parse_json_as(response.text, BusinessReasoning)
            self._logger.info("[ReasoningAgent] Response Parsed")
            self._record_metric("confidence", reasoning.confidence)
        except Exception as exc:
            self._logger.error("[ReasoningAgent] JSON Parse / Validation failed: %s", exc)
            self._add_warning(f"Fallback recovery applied due to parsing/validation exception: {exc}")
            
            # Formulate fallback reasoning to prevent workflow crashing
            overall = "review_needed"
            if bundle.risk.overall_level in {"high", "critical"}:
                overall = "at_risk"
            
            reasoning = BusinessReasoning(
                overall_assessment=overall,
                business_context=BusinessContext(
                    customer_stage="adoption" if bundle.crm.renewal_date else "other",
                    relationship_status="at_risk" if bundle.risk.overall_level in {"high", "critical"} else "stable",
                    product_adoption="low" if (bundle.crm.usage_mau or 0) < 15 else "medium",
                    support_state="escalated" if bundle.crm.support_escalated else "normal"
                ),
                key_findings=[
                    KeyFinding(
                        title="Fallback baseline reasoning",
                        reasoning="Deterministic fallback reasoning loaded due to LLM exception.",
                        evidence="CRM profile usage or risk assessment levels."
                    )
                ],
                supporting_facts=["CRM telemetry active", "Risk assessment level check complete"],
                confidence=0.0,
                summary="[ReasoningAgent failed to parse LLM response — deterministic fallback outline generated]"
            )

        # Confirm validation clamping
        reasoning = self._sanitize_reasoning(reasoning)
        self._logger.info("[ReasoningAgent] Validation Passed")
        self._record_metric("key_findings_generated", len(reasoning.key_findings))
        self._record_metric("evidence_items", len(reasoning.supporting_facts))

        # 6. Write State
        self._write_state(state, reasoning)
        self._logger.info("[ReasoningAgent] Workflow Updated")

        output_data = reasoning.model_dump(mode="json")
        duration_ms = (time.monotonic() - start_time) * 1000.0

        self._logger.info(
            "[ReasoningAgent] ReasoningAgent Finished | overall_assessment=%s findings=%d confidence=%.2f execution_time=%.2fms",
            reasoning.overall_assessment,
            len(reasoning.key_findings),
            reasoning.confidence,
            duration_ms
        )

        return AgentResult.success_result(
            agent_name=self.agent_name,
            execution_time_ms=0.0,  # Overwritten by BaseAgent
            output_data=output_data,
            confidence=reasoning.confidence,
            message=(
                f"Business reasoning complete. Overall assessment: {reasoning.overall_assessment}. "
                f"Synthesized {len(reasoning.key_findings)} key finding(s)."
            )
        )

    def _sanitize_reasoning(self, reasoning: BusinessReasoning) -> BusinessReasoning:
        confidence = max(0.0, min(1.0, reasoning.confidence))
        if confidence != reasoning.confidence:
            return reasoning.model_copy(update={"confidence": confidence})
        return reasoning

    def _write_state(self, state: WorkflowState, reasoning: BusinessReasoning) -> None:
        state.analysis.business_reasoning = reasoning.model_dump(mode="json")

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
            self._logger.warning("[ReasoningAgent] Handling LLM parsing error. Constructing stub fallback.")
            stub = BusinessReasoning(
                overall_assessment="review_needed",
                business_context=BusinessContext(
                    customer_stage="other",
                    relationship_status="stable",
                    product_adoption="medium",
                    support_state="normal"
                ),
                key_findings=[],
                supporting_facts=[],
                confidence=0.0,
                summary="[ReasoningAgent encountered LLM error — partial data fallback applied]"
            )
            self._write_state(state, stub)
            return AgentResult.success_result(
                agent_name=self.agent_name,
                execution_time_ms=0.0,
                output_data=stub.model_dump(mode="json"),
                confidence=0.0,
                message="ReasoningAgent recovered from severe error using fallback stub."
            )
        return None
