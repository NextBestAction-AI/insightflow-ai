"""
backend/agents/recommendation_agent.py
======================================
RecommendationAgent enriches the workflow by generating prioritized, evidence-backed 
business recommendations (next-best actions).

Single responsibility
---------------------
**Answer one question: "Given everything we know, what should we do next?"**

This agent reads from the customer profile, interaction analysis, health assessment, 
risk assessment, business reasoning, knowledge context, and CRM context. It leverages 
an OpportunityAnalyzer to identify key opportunity types, constructs a unified prompt, 
submits it to the LLM, validates the structured JSON plan, and writes it to 
``WorkflowState.analysis.recommendations``.

It does NOT:
* Analyze interactions
* Retrieve CRM information
* Retrieve organizational knowledge
* Calculate customer health
* Detect business risks
* Explain the customer's current business situation
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

class Recommendation(BaseModel):
    """
    A single prioritized, evidence-backed actionable recommendation.
    """
    title: str = Field(description="Actionable title for the recommendation.")
    description: str = Field(description="Detailed narrative of what needs to be done.")
    priority: str = Field(description="Priority: critical, high, medium, low.")
    category: str = Field(description="Category: Renewal, Customer Success, Product Adoption, Support, Expansion, Executive Engagement, Risk Mitigation, Operational, Other.")
    expected_impact: str = Field(description="Anticipated business outcome of taking this action.")
    success_probability: float = Field(ge=0.0, le=1.0, description="Estimated probability of action success [0.0, 1.0].")
    reasoning: str = Field(description="Strategic justification for this action.")
    supporting_evidence: list[str] = Field(default_factory=list, description="Grounding facts/metrics cited from prior agents.")

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"critical", "high", "medium", "low"}
        if normalised in allowed:
            return normalised
        return "medium"

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: Any) -> str:
        normalised = str(v).strip().title()
        allowed = {
            "Renewal", "Customer Success", "Product Adoption", "Support", 
            "Expansion", "Executive Engagement", "Risk Mitigation", 
            "Operational", "Other"
        }
        if normalised in allowed:
            return normalised
        # Coerce casing/variations
        coerced_map = {
            "Customer_Success": "Customer Success",
            "Product_Adoption": "Product Adoption",
            "Executive_Engagement": "Executive Engagement",
            "Risk_Mitigation": "Risk Mitigation"
        }
        for k, val in coerced_map.items():
            if k.lower() in normalised.lower():
                return val
        return "Other"


class RecommendationPlan(BaseModel):
    """
    Strongly typed Pydantic model representing the output of RecommendationAgent.
    """
    recommendations: list[Recommendation] = Field(default_factory=list, description="List of generated recommendations.")
    overall_priority: str = Field(description="Overall priority level: critical, high, medium, low.")
    confidence: float = Field(ge=0.0, le=1.0, description="LLM's confidence score in the plan [0.0, 1.0].")
    summary: str = Field(min_length=10, description="Narrative summary outlining the prioritized plan.")

    @field_validator("overall_priority")
    @classmethod
    def _validate_priority(cls, v: Any) -> str:
        normalised = str(v).lower().strip()
        allowed = {"critical", "high", "medium", "low"}
        if normalised in allowed:
            return normalised
        return "medium"

# =============================================================================
# Section 2: Helper Data Structures & Components
# =============================================================================

class CustomerContext(BaseModel):
    """
    Grouped customer profile variables.
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
    Grouped interaction context variables.
    """
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    urgency: Optional[str] = None
    commitments_count: int = 0
    issues: list[dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None


class KnowledgeContext(BaseModel):
    """
    Grouped search documentation context variables.
    """
    summary: Optional[str] = None
    citations: list[str] = Field(default_factory=list)
    best_practices: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CRMContext(BaseModel):
    """
    Grouped crm details context variables.
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
    Grouped health assessment context variables.
    """
    score: Optional[int] = None
    status: Optional[str] = None
    trend: Optional[str] = None
    drivers: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


class RiskContext(BaseModel):
    """
    Grouped risk assessment context variables.
    """
    overall_level: Optional[str] = None
    identified_risks: list[dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    confidence: Optional[float] = None


class ReasoningContext(BaseModel):
    """
    Grouped business reasoning context variables.
    """
    overall_assessment: Optional[str] = None
    key_findings: list[dict[str, Any]] = Field(default_factory=list)
    supporting_facts: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


class RecommendationContextBundle(BaseModel):
    """
    Structured context bundle feeding the OpportunityAnalyzer and prompt.
    """
    customer: CustomerContext
    interaction: InteractionContext
    knowledge: KnowledgeContext
    crm: CRMContext
    health: HealthContext
    risk: RiskContext
    reasoning: ReasoningContext


class RecommendationContextCollector:
    """
    Responsible for extracting all preceding agent context from WorkflowState.
    """
    def collect(self, state: WorkflowState) -> RecommendationContextBundle:
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

        # Reasoning
        re = state.analysis.business_reasoning or {}
        reasoning = ReasoningContext(
            overall_assessment=re.get("overall_assessment"),
            key_findings=re.get("key_findings") or [],
            supporting_facts=re.get("supporting_facts") or [],
            summary=re.get("summary")
        )

        return RecommendationContextBundle(
            customer=customer,
            interaction=interaction,
            knowledge=knowledge,
            crm=crm,
            health=health,
            risk=risk,
            reasoning=reasoning
        )


class RecommendationOpportunity(BaseModel):
    """
    A single categorized business opportunity.
    """
    category: str
    description: str
    urgency: str


class OpportunityBundle(BaseModel):
    """
    A list of identified business opportunities.
    """
    opportunities: list[RecommendationOpportunity] = Field(default_factory=list)


class OpportunityAnalyzer:
    """
    Identifies customer opportunities from context without evaluating final recommendations.
    """
    def analyze(self, bundle: RecommendationContextBundle) -> OpportunityBundle:
        opps = []

        # 1. Renewal focus opportunity
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
                if days_until <= 90:
                    opps.append(RecommendationOpportunity(
                        category="Renewal",
                        description=f"Active renewal opportunity approaching in {days_until} days.",
                        urgency="critical" if bundle.crm.renewal_likelihood is not None and bundle.crm.renewal_likelihood < 0.6 else "high"
                    ))
            except Exception:
                pass

        # 2. Risk Mitigation opportunity
        if bundle.risk.overall_level in {"high", "critical"}:
            opps.append(RecommendationOpportunity(
                category="Risk Mitigation",
                description=f"Address identified risks (overall risk is '{bundle.risk.overall_level}').",
                urgency="critical" if bundle.risk.overall_level == "critical" else "high"
            ))

        # 3. Product Adoption opportunity
        if bundle.crm.usage_dau is not None and bundle.crm.usage_mau is not None and bundle.crm.usage_mau > 0:
            ratio = float(bundle.crm.usage_dau) / float(bundle.crm.usage_mau)
            if ratio < 0.15:
                opps.append(RecommendationOpportunity(
                    category="Product Adoption",
                    description=f"Improve low customer product adoption (DAU/MAU is {ratio*100:.0f}%).",
                    urgency="high"
                ))

        # 4. Support opportunity
        if bundle.crm.support_open_tickets > 0 or bundle.crm.support_escalated:
            opps.append(RecommendationOpportunity(
                category="Support",
                description=f"Resolve active open support ticket load ({bundle.crm.support_open_tickets} ticket(s) / escalated: {bundle.crm.support_escalated}).",
                urgency="high" if bundle.crm.support_escalated else "medium"
            ))

        # 5. Executive Engagement opportunity
        has_escalation_theme = False
        re_summary = str(bundle.reasoning.summary or "").lower()
        if "executive" in re_summary or "escalation" in re_summary:
            has_escalation_theme = True
        for f in bundle.reasoning.key_findings:
            if "executive" in f.get("title", "").lower() or "executive" in f.get("reasoning", "").lower():
                has_escalation_theme = True
        if has_escalation_theme:
            opps.append(RecommendationOpportunity(
                category="Executive Engagement",
                description="Trigger executive sponsorship alignment due to critical client escalations.",
                urgency="high"
            ))

        return OpportunityBundle(opportunities=opps)


class RecommendationPromptBuilder:
    """
    Formats the context prompt for next-best action generation.
    """
    def __init__(self, prompt_template: str) -> None:
        self._template = prompt_template

    def build(
        self, 
        bundle: RecommendationContextBundle, 
        opp_bundle: OpportunityBundle
    ) -> str:
        interaction_text = bundle.interaction.summary or "No interaction summary available."
        knowledge_text = bundle.knowledge.summary or "No knowledge context available."
        health_drivers = ", ".join(bundle.health.drivers) if bundle.health.drivers else "None"
        health_summary = bundle.health.summary or "None"
        risk_summary = bundle.risk.summary or "None"
        reasoning_summary = bundle.reasoning.summary or "None"

        # Format risk list
        risk_items_list = []
        for r in bundle.risk.identified_risks:
            risk_items_list.append(
                f"- Category: {r.get('category')}, Severity: {r.get('severity')}, Prob: {r.get('probability')}, "
                f"Impact: {r.get('impact')}, Evidence: '{r.get('evidence')}', Desc: {r.get('description')}"
            )
        risk_items_text = "\n".join(risk_items_list) if risk_items_list else "No risks identified."

        # Format reasoning findings
        findings_list = []
        for f in bundle.reasoning.key_findings:
            findings_list.append(
                f"- Finding: {f.get('title')}, Reasoning: {f.get('reasoning')}, Evidence: '{f.get('evidence')}'"
            )
        findings_text = "\n".join(findings_list) if findings_list else "No key findings synthesized."

        # Format identified opportunities
        opps_list = []
        for o in opp_bundle.opportunities:
            opps_list.append(f"- Category: {o.category}, Description: '{o.description}', Urgency: {o.urgency}")
        opps_text = "\n".join(opps_list) if opps_list else "No specific opportunities flagged."

        return self._template.format(
            company=bundle.customer.company or "Unknown",
            region=bundle.customer.region or "Unknown",
            industry=bundle.customer.industry or "Unknown",
            account_type=bundle.customer.account_type or "Standard",
            acv_usd=bundle.crm.contract_acv or 0.0,
            contract_active="Active" if bundle.crm.contract_active else "Inactive",
            renewal_date=bundle.crm.renewal_date or "Unknown",
            renewal_likelihood=bundle.crm.renewal_likelihood if bundle.crm.renewal_likelihood is not None else "Unknown",
            support_open=bundle.crm.support_open_tickets,
            support_escalated=bundle.crm.support_escalated,
            usage_dau=bundle.crm.usage_dau if bundle.crm.usage_dau is not None else 0,
            usage_mau=bundle.crm.usage_mau if bundle.crm.usage_mau is not None else 0,
            health_score=bundle.health.score if bundle.health.score is not None else "Unknown",
            health_status=bundle.health.status or "Unknown",
            health_trend=bundle.health.trend or "Unknown",
            health_drivers=health_drivers,
            health_summary=health_summary,
            risk_level=bundle.risk.overall_level or "Unknown",
            risk_summary=risk_summary,
            risk_items=risk_items_text,
            reasoning_summary=reasoning_summary,
            key_findings=findings_text,
            interaction_summary=interaction_text,
            knowledge_summary=knowledge_text,
            identified_opportunities=opps_text
        )

# =============================================================================
# Section 3: Prompts
# =============================================================================

_RECOMMENDATION_PROMPT = """You are an expert Customer Success Executive.
Your task is to analyze all business intelligence context and generate a prioritized, evidence-backed next-best action recommendation plan in **strict JSON** format.

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

### Business Reasoning Synthesis (from ReasoningAgent)
- Reasoning Summary: {reasoning_summary}
- Key Findings:
{key_findings}

### CRM & Interaction Highlights
- Active Contract: {contract_active}, ACV: ${acv_usd:,.2f}
- Renewal date: {renewal_date}, Renewal likelihood: {renewal_likelihood}
- Open tickets: {support_open}, Escalation: {support_escalated}
- Telemetry usage DAU: {usage_dau}, MAU: {usage_mau}
- Recent conversation highlights: {interaction_summary}

### Knowledge Context (Related SLA policies or playbooks)
{knowledge_summary}

### Identified Opportunities (from OpportunityAnalyzer)
{identified_opportunities}

## Output Format
Return ONLY a single, valid JSON object with the following fields. Do not include markdown code blocks or conversational prose.

{{
  "recommendations": [
    {{
      "title": "<descriptive title (e.g. 'Schedule Executive Renewal Review')>",
      "description": "<actionable description explaining what to do>",
      "priority": "<critical | high | medium | low>",
      "category": "<Renewal | Customer Success | Product Adoption | Support | Expansion | Executive Engagement | Risk Mitigation | Operational | Other>",
      "expected_impact": "<qualitative business outcome expectation>",
      "success_probability": <float from 0.0 to 1.0 representing likelihood of successful execution outcome>,
      "reasoning": "<strategic justification connecting inputs to this action>",
      "supporting_evidence": [
        "<evidence quote or metric fact 1>",
        "<evidence quote or metric fact 2>",
        ...
      ]
    }}
  ],
  "overall_priority": "<critical | high | medium | low>",
  "confidence": <float from 0.0 to 1.0 representing your recommendation confidence>,
  "summary": "<concise 3-5 sentence narrative summarizing the prioritized recommendation plan>"
}}

## Groundedness & Actionability Rules:
1. Ground every recommendation and evidence item ONLY in the provided input. Do not invent outside facts.
2. Never contradict previous agent outputs (e.g. if RiskAgent flagged high renewal risk, do not state renewal is stable).
3. Do NOT calculate new health scores or risks.
4. Prioritize the recommendations list from highest priority (e.g. Critical/High) to lowest.
5. Every recommendation must cite at least one concrete piece of supporting evidence from the input data.
6. Output STRICT JSON only. Do not include markdown code blocks (e.g. ```json ... ```) or any surrounding conversational filler text. Your entire response must be the JSON object and nothing else.
"""

_SYSTEM_PROMPT = (
    "You are a customer relationship next-best action recommendation system. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

# =============================================================================
# Section 4: The Agent
# =============================================================================

class RecommendationAgent(BaseAgent):
    """
    RecommendationAgent generates prioritized, evidence-backed next-best actions.
    """
    agent_name: ClassVar[str] = "RecommendationAgent"

    description: ClassVar[str] = (
        "Generates prioritized, evidence-backed next-best actions using synthesized business intelligence."
    )

    required_inputs: ClassVar[list[str]] = [
        "analysis.interaction_analysis",
        "analysis.health_assessment",
        "analysis.risk_assessment",
        "analysis.business_reasoning",
        "context.knowledge_context",
        "context.crm_context"
    ]

    produced_outputs: ClassVar[list[str]] = [
        "analysis.recommendations"
    ]

    supported_execution_modes: ClassVar[list[str]] = [
        "LIVE",
        "DEBUG",
        "DRY_RUN",
        "SIMULATION"
    ]

    priority: ClassVar[int] = 60

    def __init__(
        self,
        llm_service=None,
        prompt_manager=None,
        state_validator=None,
        response_parser: ResponseParser | None = None,
        collector: RecommendationContextCollector | None = None,
        opportunity_analyzer: OpportunityAnalyzer | None = None,
        prompt_builder: RecommendationPromptBuilder | None = None
    ) -> None:
        super().__init__(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator
        )
        self._parser = response_parser or ResponseParser()
        self._collector = collector or RecommendationContextCollector()
        self._opportunity_analyzer = opportunity_analyzer or OpportunityAnalyzer()
        self._prompt_builder = prompt_builder or RecommendationPromptBuilder(
            prompt_template=_RECOMMENDATION_PROMPT
        )

    async def validate_input(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> None:
        """
        Ensures that preceding business reasoning analysis is available to build recommendations.
        """
        if not state.analysis.business_reasoning:
            raise ValueError(
                "RecommendationAgent requires analysis.business_reasoning to run."
            )

    async def execute(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> AgentResult:
        self._logger.info("[RecommendationAgent] RecommendationAgent Started")
        start_time = time.monotonic()

        # 1. Collect
        bundle = self._collector.collect(state)
        self._logger.info("[RecommendationAgent] Context Collected")
        self._record_metric("contexts_collected", 7)

        # 2. Identify Opportunities
        opp_bundle = self._opportunity_analyzer.analyze(bundle)
        self._logger.info(
            "[RecommendationAgent] Opportunities Identified | Count: %d",
            len(opp_bundle.opportunities)
        )
        self._record_metric("opportunities_identified", len(opp_bundle.opportunities))

        # 3. Build Prompt
        prompt = self._prompt_builder.build(bundle, opp_bundle)
        self._logger.info("[RecommendationAgent] Prompt Built")

        # 4. Call LLM
        self._logger.info("[RecommendationAgent] Invoking LLM for recommendation synthesis.")
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
        self._logger.info("[RecommendationAgent] LLM Completed")

        # 5. Parse and Validate
        self._logger.debug("[RecommendationAgent] Raw LLM response (len=%d): %s", len(response.text), response.text[:800])
        try:
            plan = self._parser.parse_json_as(response.text, RecommendationPlan)
            self._logger.info(
                "[RecommendationAgent] Recommendations Parsed | Count: %d, Priority: %s",
                len(plan.recommendations),
                plan.overall_priority
            )
            self._record_metric("confidence", plan.confidence)
        except Exception as exc:
            self._logger.error("[RecommendationAgent] JSON Parse / Validation failed: %s", exc)
            self._add_warning(f"Fallback recovery applied due to parsing/validation exception: {exc}")
            
            # Formulate fallback recommendations plan to prevent workflow crashing
            fallback_recs = []
            highest_pri = "medium"
            
            for opp in opp_bundle.opportunities:
                priority_val = opp.urgency
                if priority_val == "critical" or highest_pri == "critical":
                    highest_pri = "critical"
                elif priority_val == "high" and highest_pri != "critical":
                    highest_pri = "high"
                    
                fallback_recs.append(Recommendation(
                    title=f"Address {opp.category} Opportunity",
                    description=opp.description,
                    priority=opp.urgency,
                    category=opp.category,
                    expected_impact=f"Mitigate customer friction related to {opp.category.lower()}.",
                    success_probability=0.8,
                    reasoning=f"Identified deterministic opportunity for {opp.category.lower()}.",
                    supporting_evidence=[opp.description]
                ))
                
            if not fallback_recs:
                fallback_recs.append(Recommendation(
                    title="Conduct Account Health Check",
                    description="Standard proactive customer review.",
                    priority="low",
                    category="Operational",
                    expected_impact="Maintain client engagement.",
                    success_probability=0.9,
                    reasoning="Default baseline fallback review action.",
                    supporting_evidence=["Standard pipeline baseline execution"]
                ))
                highest_pri = "low"
                
            plan = RecommendationPlan(
                recommendations=fallback_recs,
                overall_priority=highest_pri,
                confidence=0.0,
                summary="[RecommendationAgent failed to parse LLM response — deterministic fallback recommendations generated]"
            )

        # Confirm validation boundaries
        plan = self._sanitize_plan(plan)
        self._logger.info("[RecommendationAgent] Validation Passed")

        critical_recs = sum(1 for r in plan.recommendations if r.priority == "critical")
        high_recs = sum(1 for r in plan.recommendations if r.priority == "high")
        self._record_metric("recommendations_generated", len(plan.recommendations))
        self._record_metric("critical_recommendations", critical_recs)
        self._record_metric("high_priority_recommendations", high_recs)

        # 6. Write State
        self._write_state(state, plan)
        self._logger.info("[RecommendationAgent] Workflow Updated")

        output_data = plan.model_dump(mode="json")
        duration_ms = (time.monotonic() - start_time) * 1000.0

        self._logger.info(
            "[RecommendationAgent] RecommendationAgent Finished | recommendations=%d highest_priority=%s confidence=%.2f execution_time=%.2fms",
            len(plan.recommendations),
            plan.overall_priority,
            plan.confidence,
            duration_ms
        )

        return AgentResult.success_result(
            agent_name=self.agent_name,
            execution_time_ms=0.0,  # Overwritten by BaseAgent
            output_data=output_data,
            confidence=plan.confidence,
            message=(
                f"Generated {len(plan.recommendations)} recommendation(s) with overall priority: {plan.overall_priority}."
            )
        )

    def _sanitize_plan(self, plan: RecommendationPlan) -> RecommendationPlan:
        confidence = max(0.0, min(1.0, plan.confidence))
        sanitized_recs = []
        for rec in plan.recommendations:
            sp = max(0.0, min(1.0, rec.success_probability))
            if sp != rec.success_probability:
                sanitized_recs.append(rec.model_copy(update={"success_probability": sp}))
            else:
                sanitized_recs.append(rec)
                
        if confidence != plan.confidence or len(sanitized_recs) != len(plan.recommendations):
            return plan.model_copy(update={"confidence": confidence, "recommendations": sanitized_recs})
        return plan

    def _write_state(self, state: WorkflowState, plan: RecommendationPlan) -> None:
        # Write ONLY to the canonical AnalysisState field as the single source of truth
        state.analysis.recommendations = plan.model_dump(mode="json")

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
            self._logger.warning("[RecommendationAgent] Handling LLM parsing error. Constructing stub fallback.")
            stub = RecommendationPlan(
                recommendations=[],
                overall_priority="medium",
                confidence=0.0,
                summary="[RecommendationAgent encountered LLM error — partial data fallback applied]"
            )
            self._write_state(state, stub)
            return AgentResult.success_result(
                agent_name=self.agent_name,
                execution_time_ms=0.0,
                output_data=stub.model_dump(mode="json"),
                confidence=0.0,
                message="RecommendationAgent recovered from severe error using fallback stub."
            )
        return None
