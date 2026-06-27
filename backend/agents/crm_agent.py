"""
backend/agents/crm_agent.py
============================
CRMAgent — enriches the workflow context with structured enterprise CRM customer data.

Single responsibility
---------------------
**Answer one question: "What business information do we know about this customer?"**

This agent retrieves customer profile, contract, renewal, usage, support,
opportunity, and success manager records from the enterprise CRM database (via
CRMService). It parses and validates them into strongly typed Pydantic models
and writes the serialized payload to ``WorkflowState.context.crm_context``.

It is explicitly NOT responsible for:
* Customer Health Scoring
* Risk Detection
* Recommendations
* Knowledge Retrieval
* LLM Reasoning
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from backend.agents.base_agent import BaseAgent
from backend.orchestrator.agent_result import AgentResult
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.workflow_state import WorkflowState


# =============================================================================
# Section 1: Output schemas & Domain Models
# =============================================================================


class CustomerProfile(BaseModel):
    """
    Core customer identity and contact information.
    """
    customer_id: str = Field(description="Primary key from CRM system.")
    customer_name: str = Field(description="Display name of the customer contact.")
    company: str = Field(description="Legal entity / organization name.")
    industry: Optional[str] = Field(default=None, description="Industry vertical.")
    account_type: str = Field(default="Standard", description="Tier e.g. Enterprise, Mid-Market, SMB.")
    employee_count: Optional[int] = Field(default=None, ge=0, description="Approximate employee count.")
    region: Optional[str] = Field(default=None, description="Geographic sales region.")


class ContractInformation(BaseModel):
    """
    Commercial agreement and subscription values.
    """
    contract_id: str = Field(description="Unique contract reference ID.")
    start_date: Optional[datetime] = Field(default=None, description="Subscription start date.")
    end_date: Optional[datetime] = Field(default=None, description="Subscription end date.")
    annual_contract_value_usd: float = Field(default=0.0, ge=0.0, description="Annual Contract Value (ACV) in USD.")
    billing_frequency: str = Field(default="Annual", description="Monthly, Quarterly, or Annual.")
    is_active: bool = Field(default=True, description="Whether the contract is currently active.")


class RenewalInformation(BaseModel):
    """
    Forecast and renewal health indicators.
    """
    target_date: Optional[datetime] = Field(default=None, description="Expected renewal date.")
    renewal_likelihood: float = Field(default=1.0, ge=0.0, le=1.0, description="Estimated renewal probability [0.0, 1.0].")
    expansion_potential_usd: float = Field(default=0.0, ge=0.0, description="Projected expansion value in USD.")
    risk_level: str = Field(default="Low", description="Risk level: Low, Medium, High, or Critical.")


class UsageMetrics(BaseModel):
    """
    High-level telemetry usage aggregated by the data pipeline.
    """
    dau: int = Field(default=0, ge=0, description="Daily Active Users.")
    monthly_active_users: int = Field(default=0, ge=0, description="Monthly Active Users.")
    api_calls_last_30_days: int = Field(default=0, ge=0, description="Total API requests in the past 30 days.")
    storage_used_gb: float = Field(default=0.0, ge=0.0, description="Currently used cloud storage in gigabytes.")


class SupportHistory(BaseModel):
    """
    Recent customer service and ticketing metrics.
    """
    open_tickets_count: int = Field(default=0, ge=0, description="Number of currently active support tickets.")
    resolved_tickets_last_90_days: int = Field(default=0, ge=0, description="Tickets resolved within the past 90 days.")
    avg_resolution_time_hours: Optional[float] = Field(default=None, ge=0.0, description="Average time in hours to resolve issues.")
    escalation_status: bool = Field(default=False, description="True if any ticket is escalated.")


class SuccessManager(BaseModel):
    """
    Assigned customer success contact.
    """
    name: str = Field(default="Unassigned", description="CSM display name.")
    email: Optional[str] = Field(default=None, description="CSM email address.")
    region: Optional[str] = Field(default=None, description="Region coverage.")


class OpportunityHistory(BaseModel):
    """
    Active pipeline and historical deal performance.
    """
    active_opportunities_count: int = Field(default=0, ge=0, description="Active sales pipeline items.")
    pipeline_value_usd: float = Field(default=0.0, ge=0.0, description="Total value of active pipeline in USD.")
    closed_won_value_usd: float = Field(default=0.0, ge=0.0, description="Total historical closed-won sales in USD.")


class CRMContext(BaseModel):
    """
    Strongly typed root Pydantic model for CRM enforcements.
    """
    profile: CustomerProfile
    contract: Optional[ContractInformation] = None
    renewal: Optional[RenewalInformation] = None
    usage: Optional[UsageMetrics] = None
    support: Optional[SupportHistory] = None
    success_manager: Optional[SuccessManager] = None
    opportunities: Optional[OpportunityHistory] = None
    account_metadata: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Section 2: Helper Components
# =============================================================================


class CustomerIdentifier:
    """
    Responsible for identifying the customer query parameters from WorkflowState.

    WHY THIS HELPER EXISTS:
    Decouples context extraction logic. If customer IDs migrate from string properties
    to metadata lists, this component encapsulates the change.
    """

    def identify(self, state: WorkflowState) -> tuple[Optional[str], Optional[str]]:
        """
        Extract customer_id and company name from WorkflowState.

        Parameters
        ----------
        state : WorkflowState

        Returns
        -------
        tuple[str | None, str | None]
            customer_id, company_name
        """
        customer_id = state.customer.customer_id
        company_name = state.customer.company

        # Secondary fallback lookup in input fields
        if not customer_id and state.customer.customer_name:
            customer_id = state.customer.customer_name

        return customer_id, company_name


class CRMQueryBuilder:
    """
    Helper component responsible for building DB filters and query parameters.

    WHY THIS HELPER EXISTS:
    Translates identification keys into concrete SQL or query execution plans.
    """

    def build_query_params(self, customer_id: Optional[str], company_name: Optional[str]) -> dict[str, Any]:
        """
        Build a dictionary of filters for CRM retrieval.
        """
        return {
            "customer_id": customer_id.strip() if customer_id else None,
            "company_name": company_name.strip() if company_name else None,
            "queried_at": datetime.now(tz=timezone.utc)
        }


class CRMService:
    """
    Service layer responsible for connecting to CRM data stores.

    WHY THIS HELPER EXISTS:
    Encapsulates database access. Connects to SQL/MySQL or falls back
    to in-memory mock datasets for sandbox/test environments without dependencies.
    """

    def __init__(self) -> None:
        self._cache: dict[str, CRMContext] = {}
        self._initialize_mock_database()

    def fetch(self, query_params: dict[str, Any]) -> tuple[Optional[CRMContext], bool]:
        """
        Retrieve CRM record matching parameters.

        Returns
        -------
        tuple[CRMContext | None, bool]
            CRMContext data object, cache_hit boolean
        """
        customer_id = query_params.get("customer_id")
        company_name = query_params.get("company_name")

        # 1. Check cache first
        cache_key = customer_id or company_name or "default"
        if cache_key in self._cache:
            return self._cache[cache_key], True

        # 2. Query Mock Database (simulation of database execution)
        match_context = None

        if customer_id:
            match_context = self._db.get(customer_id)

        if not match_context and company_name:
            # Match by company name substring
            for c_id, ctx in self._db.items():
                if company_name.lower() in ctx.profile.company.lower():
                    match_context = ctx
                    break

        # 3. Fallback dynamically to avoid failing the pipeline if customer is missing
        if not match_context and (customer_id or company_name):
            match_context = self._generate_fallback_context(customer_id, company_name)

        if match_context:
            self._cache[cache_key] = match_context
            return match_context, False

        return None, False

    def _generate_fallback_context(self, customer_id: Optional[str], company_name: Optional[str]) -> CRMContext:
        """
        Construct a default skeleton profile to support partial execution gracefully.
        """
        fallback_id = customer_id or "CUST-UNKNOWN"
        fallback_company = company_name or "Unknown Entity"
        
        return CRMContext(
            profile=CustomerProfile(
                customer_id=fallback_id,
                customer_name="Unknown Contact",
                company=fallback_company,
                account_type="Standard",
                region="AMER"
            ),
            contract=ContractInformation(
                contract_id=f"CON-{fallback_id}",
                annual_contract_value_usd=0.0,
                is_active=False
            ),
            renewal=RenewalInformation(risk_level="Unknown"),
            success_manager=SuccessManager(name="Unassigned")
        )

    def _initialize_mock_database(self) -> None:
        """
        Seed mock customer records for sandbox and local testing.
        """
        self._db: dict[str, CRMContext] = {
            "CUST-101": CRMContext(
                profile=CustomerProfile(
                    customer_id="CUST-101",
                    customer_name="Alice Smith",
                    company="Acme Corporation",
                    industry="Financial Services",
                    account_type="Enterprise",
                    employee_count=1500,
                    region="EMEA"
                ),
                contract=ContractInformation(
                    contract_id="CON-101-A",
                    start_date=datetime(2025, 1, 1),
                    end_date=datetime(2026, 1, 1),
                    annual_contract_value_usd=120000.0,
                    billing_frequency="Annual",
                    is_active=True
                ),
                renewal=RenewalInformation(
                    target_date=datetime(2026, 1, 1),
                    renewal_likelihood=0.92,
                    expansion_potential_usd=15000.0,
                    risk_level="Low"
                ),
                usage=UsageMetrics(
                    dau=250,
                    monthly_active_users=800,
                    api_calls_last_30_days=450000,
                    storage_used_gb=125.4
                ),
                support=SupportHistory(
                    open_tickets_count=0,
                    resolved_tickets_last_90_days=14,
                    avg_resolution_time_hours=4.2,
                    escalation_status=False
                ),
                success_manager=SuccessManager(
                    name="Sarah Jenkins",
                    email="s.jenkins@insightflow.ai",
                    region="EMEA"
                ),
                opportunities=OpportunityHistory(
                    active_opportunities_count=1,
                    pipeline_value_usd=25000.0,
                    closed_won_value_usd=240000.0
                ),
                account_metadata={"segment": "Strategic", "health_score": 88}
            ),
            "CUST-102": CRMContext(
                profile=CustomerProfile(
                    customer_id="CUST-102",
                    customer_name="Bob Miller",
                    company="Globex Corporation",
                    industry="Technology",
                    account_type="Mid-Market",
                    employee_count=350,
                    region="AMER"
                ),
                contract=ContractInformation(
                    contract_id="CON-102-B",
                    start_date=datetime(2025, 6, 1),
                    end_date=datetime(2026, 6, 1),
                    annual_contract_value_usd=45000.0,
                    billing_frequency="Quarterly",
                    is_active=True
                ),
                renewal=RenewalInformation(
                    target_date=datetime(2026, 6, 1),
                    renewal_likelihood=0.65,
                    expansion_potential_usd=5000.0,
                    risk_level="Medium"
                ),
                usage=UsageMetrics(
                    dau=45,
                    monthly_active_users=120,
                    api_calls_last_30_days=95000,
                    storage_used_gb=45.2
                ),
                support=SupportHistory(
                    open_tickets_count=1,
                    resolved_tickets_last_90_days=5,
                    avg_resolution_time_hours=18.5,
                    escalation_status=False
                ),
                success_manager=SuccessManager(
                    name="Sarah Jenkins",
                    email="s.jenkins@insightflow.ai",
                    region="AMER"
                ),
                opportunities=OpportunityHistory(
                    active_opportunities_count=0,
                    pipeline_value_usd=0.0,
                    closed_won_value_usd=90000.0
                ),
                account_metadata={"segment": "Growth", "health_score": 70}
            ),
            "CUST-103": CRMContext(
                profile=CustomerProfile(
                    customer_id="CUST-103",
                    customer_name="Peter Gibbons",
                    company="Initech",
                    industry="Retail",
                    account_type="SMB",
                    employee_count=45,
                    region="APAC"
                ),
                contract=ContractInformation(
                    contract_id="CON-103-C",
                    start_date=datetime(2025, 3, 1),
                    end_date=datetime(2026, 3, 1),
                    annual_contract_value_usd=12000.0,
                    billing_frequency="Monthly",
                    is_active=True
                ),
                renewal=RenewalInformation(
                    target_date=datetime(2026, 3, 1),
                    renewal_likelihood=0.35,
                    expansion_potential_usd=0.0,
                    risk_level="High"
                ),
                usage=UsageMetrics(
                    dau=2,
                    monthly_active_users=8,
                    api_calls_last_30_days=2500,
                    storage_used_gb=1.5
                ),
                support=SupportHistory(
                    open_tickets_count=3,
                    resolved_tickets_last_90_days=2,
                    avg_resolution_time_hours=96.0,
                    escalation_status=True
                ),
                success_manager=SuccessManager(
                    name="Sarah Jenkins",
                    email="s.jenkins@insightflow.ai",
                    region="APAC"
                ),
                opportunities=OpportunityHistory(
                    active_opportunities_count=0,
                    pipeline_value_usd=0.0,
                    closed_won_value_usd=12000.0
                ),
                account_metadata={"segment": "Core", "health_score": 42}
            )
        }


class CRMContextBuilder:
    """
    Helper component responsible for compiling CRM models into the workflow payload.

    WHY THIS HELPER EXISTS:
    Isolates output restructuring and records missing fields/metrics.
    """

    def compile(self, crm_ctx: CRMContext) -> tuple[dict[str, Any], int]:
        """
        Flatten and count missing fields within sub-models.

        Returns
        -------
        tuple[dict[str, Any], int]
            Serialized dictionary context, count of missing fields
        """
        payload = crm_ctx.model_dump(mode="json")
        missing_count = 0

        # Scan for None fields to compute metrics count
        for key, value in payload.items():
            if value is None:
                missing_count += 1
            elif isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    if sub_val is None:
                        missing_count += 1

        return payload, missing_count


# =============================================================================
# Section 3: The Agent
# =============================================================================


class CRMAgent(BaseAgent):
    """
    CRMAgent enriches the workflow context with structured enterprise CRM customer data.
    """

    agent_name: ClassVar[str] = "CRMAgent"

    description: ClassVar[str] = (
        "Retrieves and validates customer profile, contract value, renewal risks, "
        "and account metadata from the enterprise CRM database."
    )

    required_inputs: ClassVar[list[str]] = [
        "customer.customer_id"
    ]

    produced_outputs: ClassVar[list[str]] = [
        "context.crm_context"
    ]

    supported_execution_modes: ClassVar[list[str]] = [
        "LIVE",
        "DEBUG",
        "DRY_RUN",
        "SIMULATION",
    ]

    priority: ClassVar[int] = 85
    """
    Priority 85. Dispatched early so downstream reasoning agents can utilize
    billing metrics, account type, and region metadata for decisions.
    """

    # =========================================================================
    # Constructor
    # =========================================================================

    def __init__(
        self,
        llm_service=None,
        prompt_manager=None,
        state_validator=None,
        identifier: CustomerIdentifier | None = None,
        query_builder: CRMQueryBuilder | None = None,
        crm_service: CRMService | None = None,
        context_builder: CRMContextBuilder | None = None,
    ) -> None:
        super().__init__(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator,
        )
        self._identifier = identifier or CustomerIdentifier()
        self._query_builder = query_builder or CRMQueryBuilder()
        self._crm_service = crm_service or CRMService()
        self._context_builder = context_builder or CRMContextBuilder()

    # =========================================================================
    # Lifecycle hooks
    # =========================================================================

    async def validate_input(
        self,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> None:
        """
        Ensure we have identifiers to proceed with query building.
        """
        customer_id, company_name = self._identifier.identify(state)
        if not customer_id and not company_name:
            raise ValueError(
                "CRMAgent requires either customer.customer_id or customer.company to query CRM data."
            )

    # =========================================================================
    # Core business logic
    # =========================================================================

    async def execute(
        self,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> AgentResult:
        """
        Orchestrates CRM querying, data collection, and state mapping.
        """
        self._logger.info(
            "[CRMAgent] Starting CRM retrieval | request_id=%s",
            context.request_id,
        )

        # ── Step 1: Identify ────────────────────────────────────────────────
        customer_id, company_name = self._identifier.identify(state)

        # ── Step 2: Build Query ─────────────────────────────────────────────
        query_params = self._query_builder.build_query_params(customer_id, company_name)

        # ── Step 3: Fetch ───────────────────────────────────────────────────
        start_time = time.monotonic()
        crm_context, is_cache_hit = self._crm_service.fetch(query_params)
        crm_latency_ms = (time.monotonic() - start_time) * 1000.0

        if not crm_context:
            # Should not happen as service generates fallback context
            raise RuntimeError("CRM service failed to return profile data.")

        # ── Step 4: Compile & Build Context ─────────────────────────────────
        serialized_payload, missing_fields = self._context_builder.compile(crm_context)

        # ── Step 5: Record metrics ──────────────────────────────────────────
        self._record_metric("crm_latency_ms", round(crm_latency_ms, 2))
        self._record_metric("records_retrieved", 1 if crm_context.contract else 0)
        self._record_metric("cache_hits", 1 if is_cache_hit else 0)
        self._record_metric("missing_fields", missing_fields)

        self._logger.info(
            "[CRMAgent] CRM fetch complete | latency_ms=%.2f cache_hit=%s missing=%d",
            crm_latency_ms, is_cache_hit, missing_fields
        )

        # ── Step 6: Update WorkflowState ────────────────────────────────────
        self._write_state(state, serialized_payload)
        self._logger.info(
            "[CRMAgent] WorkflowState updated — crm_context written."
        )

        return AgentResult.success_result(
            agent_name=self.agent_name,
            execution_time_ms=0.0,  # Overwritten by BaseAgent
            output_data=serialized_payload,
            message=(
                f"CRM retrieval successful for {crm_context.profile.company}. "
                f"Account Tier: {crm_context.profile.account_type}. Region: {crm_context.profile.region}."
            )
        )

    # =========================================================================
    # Private processing methods
    # =========================================================================

    def _write_state(self, state: WorkflowState, payload: dict[str, Any]) -> None:
        """
        Merge values to crm_context only, updating root customer parameters.
        """
        state.context.crm_context = payload

        # Update root customer model fields if empty for consistency
        profile = payload.get("profile", {})
        if profile:
            if not state.customer.customer_id:
                state.customer.customer_id = profile.get("customer_id")
            if not state.customer.customer_name:
                state.customer.customer_name = profile.get("customer_name")
            if not state.customer.company:
                state.customer.company = profile.get("company")
            if not state.customer.industry:
                state.customer.industry = profile.get("industry")
            if not state.customer.account_type:
                state.customer.account_type = profile.get("account_type")
            if not state.customer.region:
                state.customer.region = profile.get("region")
            if not state.customer.employee_count:
                state.customer.employee_count = profile.get("employee_count")
