"""
backend/orchestrator/workflow_state.py
========================================
Central shared state object for the InsightFlow AI multi-agent workflow.

Every specialised agent receives the same ``WorkflowState`` instance,
reads only the sections it needs, writes its output into its own section,
and returns the updated state.  Agents NEVER communicate directly.

Architecture
------------

::

    WorkflowState
    │
    ├── CustomerState        – customer profile & account metadata
    ├── InputState           – raw inputs (transcript, emails, query, …)
    ├── ContextState         – retrieved enterprise context (CRM, KB, …)
    ├── AnalysisState        – analytical agent outputs (health, risks, …)
    ├── RecommendationState  – post-reasoning outputs & explanations
    ├── HumanReviewState     – human-in-the-loop approval tracking
    ├── ExecutionState       – runtime bookkeeping (agents, timestamps, …)
    └── MetadataState        – system metadata, tags, debug info

Design notes
------------
- Sub-models are **not** frozen so agents can mutate their own section
  in place; the parent ``WorkflowState`` is also mutable by design.
- ``ExecutionState`` exposes the only stateful helper methods (agent
  tracking); all other models are plain data containers.
- ``WorkflowState`` delegates to ``ExecutionState`` for bookkeeping and
  exposes a minimal surface of workflow-level helpers.
- ``Optional`` fields default to ``None`` to model information that may
  not yet be available at workflow creation time.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from backend.orchestrator.workflow_status import AgentStatus, WorkflowStatus


# ===========================================================================
# Sub-models
# ===========================================================================


# ---------------------------------------------------------------------------
# CustomerState
# ---------------------------------------------------------------------------


class CustomerState(BaseModel):
    """
    Customer profile information passed into the workflow.

    This section is populated once at workflow creation (typically from
    CRM data or the inbound API request) and treated as effectively
    immutable by downstream agents.

    Attributes
    ----------
    customer_id : str | None
        Primary key from the CRM system.
    customer_name : str | None
        Display name of the customer contact.
    company : str | None
        Legal entity / organisation name.
    industry : str | None
        Industry vertical (e.g. ``"Financial Services"``).
    account_type : str | None
        Account tier (e.g. ``"Enterprise"``, ``"SMB"``).
    region : str | None
        Geographic region (e.g. ``"EMEA"``, ``"APAC"``).
    segment : str | None
        Commercial segment or go-to-market motion.
    annual_revenue_usd : float | None
        Customer's reported annual revenue in USD.
    employee_count : int | None
        Approximate headcount.
    extra : dict[str, Any]
        Extensible bag for future CRM attributes without breaking the model.
    """

    customer_id: str | None = Field(
        default=None,
        description="Primary key from the CRM system.",
    )
    customer_name: str | None = Field(
        default=None,
        description="Display name of the customer contact.",
    )
    company: str | None = Field(
        default=None,
        description="Legal entity / organisation name.",
    )
    industry: str | None = Field(
        default=None,
        description="Industry vertical (e.g. 'Financial Services').",
    )
    account_type: str | None = Field(
        default=None,
        description="Account tier (e.g. 'Enterprise', 'SMB', 'Startup').",
    )
    region: str | None = Field(
        default=None,
        description="Geographic region (e.g. 'EMEA', 'APAC', 'AMER').",
    )
    segment: str | None = Field(
        default=None,
        description="Commercial segment or go-to-market motion.",
    )
    annual_revenue_usd: float | None = Field(
        default=None,
        ge=0.0,
        description="Customer's reported annual revenue in USD.",
    )
    employee_count: int | None = Field(
        default=None,
        ge=0,
        description="Approximate employee headcount.",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible bag for future CRM attributes.",
    )


# ---------------------------------------------------------------------------
# InputState
# ---------------------------------------------------------------------------


class InputState(BaseModel):
    """
    Raw inputs received by the platform for this workflow run.

    Populated at workflow creation; treated as read-only by all agents.
    Agents work with the processed outputs in ``ContextState`` and
    ``AnalysisState`` rather than re-parsing raw inputs.

    Attributes
    ----------
    user_query : str | None
        Natural-language query or instruction from the end user.
    transcript : str | None
        Full call / meeting transcript text.
    emails : list[str]
        Raw email bodies submitted for analysis.
    meeting_notes : str | None
        Unstructured notes from a meeting or review session.
    attachments : list[dict[str, Any]]
        File references or inline attachment payloads.
    source_channel : str | None
        Originating channel (e.g. ``"api"``, ``"slack"``, ``"email"``).
    language : str
        BCP-47 language tag of the primary input text (default: ``"en"``).
    """

    user_query: str | None = Field(
        default=None,
        description="Natural-language query or instruction from the end user.",
    )
    transcript: str | None = Field(
        default=None,
        description="Full call / meeting transcript text.",
    )
    emails: list[str] = Field(
        default_factory=list,
        description="Raw email bodies submitted for analysis.",
    )
    meeting_notes: str | None = Field(
        default=None,
        description="Unstructured notes from a meeting or review session.",
    )
    attachments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="File references or inline attachment payloads.",
    )
    source_channel: str | None = Field(
        default=None,
        description="Originating channel (e.g. 'api', 'slack', 'email').",
    )
    language: str = Field(
        default="en",
        min_length=2,
        description="BCP-47 language tag of the primary input text.",
    )


# ---------------------------------------------------------------------------
# ContextState
# ---------------------------------------------------------------------------


class ContextState(BaseModel):
    """
    Enterprise context retrieved from external systems.

    Populated by the ``KnowledgeAgent`` and ``CRMAgent``.  Downstream
    analytical agents read from this section rather than calling external
    systems directly.

    Attributes
    ----------
    crm_context : dict[str, Any]
        Structured data fetched from the CRM (opportunities, contacts, …).
    knowledge_context : list[dict[str, Any]]
        Relevant knowledge base articles, FAQs, or product documentation.
    historical_interactions : list[dict[str, Any]]
        Previous interaction records for this customer.
    usage_metrics : dict[str, Any]
        Product usage telemetry (DAU, feature adoption, health scores, …).
    competitive_intelligence : list[dict[str, Any]]
        Competitive intel retrieved from internal battlecards or KB.
    retrieval_sources : list[str]
        Ordered list of system/document names that contributed context.
    context_retrieved_at : datetime | None
        UTC timestamp when context retrieval completed.
    """

    crm_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data fetched from the CRM.",
    )
    knowledge_context: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Relevant knowledge base articles or product documentation.",
    )
    historical_interactions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Previous interaction records for this customer.",
    )
    usage_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Product usage telemetry (DAU, feature adoption, health scores).",
    )
    competitive_intelligence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Competitive intel from internal battlecards or KB.",
    )
    retrieval_sources: list[str] = Field(
        default_factory=list,
        description="Ordered list of system/document names that contributed context.",
    )
    context_retrieved_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when context retrieval completed.",
    )


# ---------------------------------------------------------------------------
# AnalysisState
# ---------------------------------------------------------------------------


class AnalysisState(BaseModel):
    """
    Outputs generated by the analytical agents.

    Written by ``InteractionAgent``, ``KnowledgeAgent``, and ``RiskAgent``.
    ``ReasoningAgent`` reads this section to synthesise business insights.

    Attributes
    ----------
    interaction_analysis : dict[str, Any]
        Structured analysis of the customer interaction (sentiment,
        topics, action items, …).
    health_assessment : dict[str, Any]
        Customer health score breakdown (usage, engagement, renewal risk).
    risk_assessment : dict[str, Any]
        Risk assessment containing overall level and identified risks.
    business_reasoning : dict[str, Any]
        Higher-order synthesis produced by the ReasoningAgent.
    sentiment_score : float | None
        Aggregate sentiment score in [-1.0, 1.0]; None if not computed.
    key_topics : list[str]
        Salient topics / themes extracted from the interaction.
    action_items : list[dict[str, Any]]
        Explicit action items extracted from the interaction.
    recommendations : dict[str, Any]
        Recommendation plan containing recommendations, overall priority, confidence, and summary.
    """

    interaction_analysis: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured analysis of the customer interaction.",
    )
    health_assessment: dict[str, Any] = Field(
        default_factory=dict,
        description="Customer health score breakdown.",
    )
    risk_assessment: dict[str, Any] = Field(
        default_factory=dict,
        description="Risk assessment containing overall level and identified risks.",
    )
    business_reasoning: dict[str, Any] = Field(
        default_factory=dict,
        description="Higher-order synthesis produced by the ReasoningAgent.",
    )
    sentiment_score: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Aggregate sentiment score in [-1.0, 1.0].",
    )
    key_topics: list[str] = Field(
        default_factory=list,
        description="Salient topics / themes extracted from the interaction.",
    )
    action_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Explicit action items extracted from the interaction.",
    )
    recommendations: dict[str, Any] = Field(
        default_factory=dict,
        description="Recommendation plan containing recommendations, overall priority, confidence, and summary.",
    )


# ---------------------------------------------------------------------------
# RecommendationState
# ---------------------------------------------------------------------------


class RecommendationState(BaseModel):
    """
    Outputs generated by the ``RecommendationAgent`` and ``ExplanationAgent``.

    This is the primary output section consumed by the API response layer
    and human reviewers.

    Attributes
    ----------
    explanations : list[str]
        Natural-language explanations for each recommendation.
    next_best_actions : list[str]
        Concise, prioritised next-best-actions for the sales / CS rep.
    generated_at : datetime | None
        UTC timestamp when recommendations were finalised.
    """

    explanations: list[str] = Field(
        default_factory=list,
        description="Natural-language explanations for each recommendation.",
    )
    next_best_actions: list[str] = Field(
        default_factory=list,
        description="Concise, prioritised next-best-actions for the sales / CS rep.",
    )
    generated_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when recommendations were finalised.",
    )


# ---------------------------------------------------------------------------
# HumanReviewState
# ---------------------------------------------------------------------------


class HumanReviewState(BaseModel):
    """
    Tracks human-in-the-loop review and approval for a workflow run.

    Populated when ``WorkflowStatus`` transitions to
    ``WAITING_FOR_APPROVAL``; updated by the review service when a
    decision is recorded.

    Attributes
    ----------
    required : bool
        Whether human review is required before proceeding.
    approved : bool | None
        ``True`` if approved, ``False`` if rejected, ``None`` if pending.
    reviewer_id : str | None
        User ID of the human reviewer.
    reviewer_name : str | None
        Display name of the human reviewer.
    feedback : str | None
        Free-text feedback from the reviewer.
    review_timestamp : datetime | None
        UTC timestamp when the review decision was recorded.
    review_requested_at : datetime | None
        UTC timestamp when review was first requested.
    """

    required: bool = Field(
        default=False,
        description="Whether human review is required before workflow proceeds.",
    )
    approved: bool | None = Field(
        default=None,
        description=(
            "True if approved, False if rejected, None if pending review."
        ),
    )
    reviewer_id: str | None = Field(
        default=None,
        description="User ID of the human reviewer.",
    )
    reviewer_name: str | None = Field(
        default=None,
        description="Display name of the human reviewer.",
    )
    feedback: str | None = Field(
        default=None,
        description="Free-text feedback provided by the reviewer.",
    )
    review_timestamp: datetime | None = Field(
        default=None,
        description="UTC timestamp when the review decision was recorded.",
    )
    review_requested_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when human review was first requested.",
    )

    @property
    def is_pending(self) -> bool:
        """Return ``True`` if review has been requested but no decision made."""
        return self.required and self.approved is None

    @property
    def is_decided(self) -> bool:
        """Return ``True`` if a review decision (approve or reject) has been recorded."""
        return self.required and self.approved is not None


# ---------------------------------------------------------------------------
# ExecutionState
# ---------------------------------------------------------------------------


class AgentExecutionRecord(BaseModel):
    """
    Tracks a single agent's execution status within a workflow run.

    Stored inside ``ExecutionState.agent_records`` keyed by agent name.

    Attributes
    ----------
    agent_name : str
        Canonical agent identifier.
    status : AgentStatus
        Current lifecycle status of this agent invocation.
    started_at : datetime | None
        UTC timestamp when the agent began execution.
    completed_at : datetime | None
        UTC timestamp when the agent finished (success or failure).
    execution_time_ms : float | None
        Wall-clock time in milliseconds; set on completion.
    error_message : str | None
        Primary error description if the agent failed.
    retry_count : int
        Number of retries attempted for this agent.
    """

    agent_name: str = Field(description="Canonical agent identifier.")
    status: AgentStatus = Field(
        default=AgentStatus.PENDING,
        description="Current lifecycle status of this agent invocation.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the agent began execution.",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the agent finished.",
    )
    execution_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Wall-clock time in milliseconds; set on completion.",
    )
    error_message: str | None = Field(
        default=None,
        description="Primary error description if the agent failed.",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retries attempted for this agent.",
    )


class ExecutionState(BaseModel):
    """
    Tracks the runtime bookkeeping for a workflow execution.

    This section is managed exclusively by the workflow engine; agents
    should treat it as read-only (they may read ``current_agent`` to
    identify themselves, but must not write to other fields).

    Attributes
    ----------
    workflow_id : str
        Globally unique identifier for this workflow run.
    current_agent : str | None
        Name of the agent currently executing; ``None`` between agents.
    completed_agents : list[str]
        Names of agents that have completed successfully, in order.
    failed_agents : list[str]
        Names of agents that have failed, in order of failure.
    skipped_agents : list[str]
        Names of agents intentionally bypassed by the planner.
    agent_records : dict[str, AgentExecutionRecord]
        Detailed per-agent execution records keyed by agent name.
    execution_status : WorkflowStatus
        Current coarse-grained status of the overall workflow.
    started_at : datetime | None
        UTC timestamp when the first agent began executing.
    updated_at : datetime
        UTC timestamp of the most recent state mutation.
    completed_at : datetime | None
        UTC timestamp when the workflow reached a terminal state.
    total_execution_time_ms : float | None
        Cumulative wall-clock time across all agents; set on completion.
    checkpoint_key : str | None
        External storage key for the last persisted state checkpoint.
    """

    workflow_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique identifier for this workflow run.",
    )
    current_agent: str | None = Field(
        default=None,
        description="Name of the agent currently executing.",
    )
    completed_agents: list[str] = Field(
        default_factory=list,
        description="Names of agents that completed successfully, in order.",
    )
    failed_agents: list[str] = Field(
        default_factory=list,
        description="Names of agents that failed, in order of failure.",
    )
    skipped_agents: list[str] = Field(
        default_factory=list,
        description="Names of agents intentionally bypassed by the planner.",
    )
    agent_records: dict[str, AgentExecutionRecord] = Field(
        default_factory=dict,
        description="Detailed per-agent execution records keyed by agent name.",
    )
    execution_status: WorkflowStatus = Field(
        default=WorkflowStatus.CREATED,
        description="Current coarse-grained status of the overall workflow.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the first agent began executing.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="UTC timestamp of the most recent state mutation.",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the workflow reached a terminal state.",
    )
    total_execution_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Cumulative wall-clock time across all agents (set on completion).",
    )
    checkpoint_key: str | None = Field(
        default=None,
        description="External storage key for the last persisted state checkpoint.",
    )

    # ── Helper methods ───────────────────────────────────────────────────────

    def set_current_agent(self, agent_name: str) -> None:
        """
        Register ``agent_name`` as the currently executing agent.

        Also ensures an ``AgentExecutionRecord`` exists for the agent
        and transitions it to ``RUNNING``, recording the start timestamp.

        Parameters
        ----------
        agent_name:
            Canonical name of the agent about to execute.
        """
        self.current_agent = agent_name
        now = datetime.now(tz=timezone.utc)

        if agent_name not in self.agent_records:
            self.agent_records[agent_name] = AgentExecutionRecord(
                agent_name=agent_name
            )

        record = self.agent_records[agent_name]
        record.status = AgentStatus.RUNNING
        record.started_at = now

        if self.started_at is None:
            self.started_at = now
            self.execution_status = WorkflowStatus.RUNNING

        self.update_timestamp()

    def mark_agent_completed(
        self,
        agent_name: str,
        execution_time_ms: float | None = None,
    ) -> None:
        """
        Mark ``agent_name`` as successfully completed.

        Adds it to ``completed_agents``, updates its record, and clears
        ``current_agent`` if it matches.

        Parameters
        ----------
        agent_name:
            Canonical name of the agent that finished successfully.
        execution_time_ms:
            Optional wall-clock time to record; sourced from ``AgentResult``.
        """
        now = datetime.now(tz=timezone.utc)

        if agent_name not in self.agent_records:
            self.agent_records[agent_name] = AgentExecutionRecord(
                agent_name=agent_name
            )

        record = self.agent_records[agent_name]
        record.status = AgentStatus.COMPLETED
        record.completed_at = now
        if execution_time_ms is not None:
            record.execution_time_ms = execution_time_ms

        if agent_name not in self.completed_agents:
            self.completed_agents.append(agent_name)

        if self.current_agent == agent_name:
            self.current_agent = None

        self.update_timestamp()

    def mark_agent_failed(
        self,
        agent_name: str,
        error_message: str = "",
        execution_time_ms: float | None = None,
    ) -> None:
        """
        Mark ``agent_name`` as having failed.

        Adds it to ``failed_agents``, records the error message, and
        clears ``current_agent`` if it matches.

        Parameters
        ----------
        agent_name:
            Canonical name of the agent that failed.
        error_message:
            Primary error description for diagnostics.
        execution_time_ms:
            Optional wall-clock time to record (time until failure).
        """
        now = datetime.now(tz=timezone.utc)

        if agent_name not in self.agent_records:
            self.agent_records[agent_name] = AgentExecutionRecord(
                agent_name=agent_name
            )

        record = self.agent_records[agent_name]
        record.status = AgentStatus.FAILED
        record.completed_at = now
        record.error_message = error_message
        if execution_time_ms is not None:
            record.execution_time_ms = execution_time_ms

        if agent_name not in self.failed_agents:
            self.failed_agents.append(agent_name)

        if self.current_agent == agent_name:
            self.current_agent = None

        self.update_timestamp()

    def mark_agent_skipped(self, agent_name: str, reason: str = "") -> None:
        """
        Register ``agent_name`` as intentionally skipped by the planner.

        Parameters
        ----------
        agent_name:
            Canonical name of the bypassed agent.
        reason:
            Optional human-readable explanation for the skip decision.
        """
        record = AgentExecutionRecord(
            agent_name=agent_name,
            status=AgentStatus.SKIPPED,
            error_message=reason or None,
        )
        self.agent_records[agent_name] = record

        if agent_name not in self.skipped_agents:
            self.skipped_agents.append(agent_name)

        self.update_timestamp()

    def update_timestamp(self) -> None:
        """Refresh ``updated_at`` to the current UTC time."""
        self.updated_at = datetime.now(tz=timezone.utc)

    def finalise(self, status: WorkflowStatus) -> None:
        """
        Transition the workflow to a terminal state.

        Records ``completed_at`` and sets ``execution_status``.

        Parameters
        ----------
        status:
            Terminal status to assign (COMPLETED, FAILED, or CANCELLED).

        Raises
        ------
        ValueError
            If ``status`` is not a terminal ``WorkflowStatus``.
        """
        from backend.orchestrator.workflow_status import TERMINAL_STATUSES

        if status not in TERMINAL_STATUSES:
            raise ValueError(
                f"finalise() requires a terminal status; got {status!r}."
            )
        now = datetime.now(tz=timezone.utc)
        self.execution_status = status
        self.completed_at = now
        self.current_agent = None

        if self.started_at is not None:
            delta = (now - self.started_at).total_seconds() * 1000
            self.total_execution_time_ms = round(delta, 2)

        self.update_timestamp()

    # ── Computed properties ─────────────────────────────────────────────────

    @property
    def has_failures(self) -> bool:
        """Return ``True`` if any agent has failed in this workflow."""
        return bool(self.failed_agents)

    @property
    def all_agent_names(self) -> list[str]:
        """Return a combined list of all agent names seen in this run."""
        return list(self.agent_records.keys())


# ---------------------------------------------------------------------------
# MetadataState
# ---------------------------------------------------------------------------


class MetadataState(BaseModel):
    """
    System-level metadata for a workflow run.

    Consumed by audit-log pipelines, observability dashboards, and
    operator tooling.  Not used for business logic.

    Attributes
    ----------
    version : str
        Schema version of the ``WorkflowState`` model in use.
    tags : list[str]
        Arbitrary labels for filtering and querying (e.g. ``["churn-risk"]``).
    custom_attributes : dict[str, Any]
        Open-ended key/value store for client-specific metadata.
    debug_info : dict[str, Any]
        Verbose diagnostics emitted when the engine runs in DEBUG mode.
    source_system : str | None
        Identifier of the system or integration that created this workflow.
    priority : str | None
        Business priority label (e.g. ``"high"``, ``"critical"``).
    """

    version: str = Field(
        default="1.0.0",
        description="Schema version of the WorkflowState model in use.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Arbitrary labels for filtering and querying.",
    )
    custom_attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Open-ended key/value store for client-specific metadata.",
    )
    debug_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Verbose diagnostics emitted in DEBUG execution mode.",
    )
    source_system: str | None = Field(
        default=None,
        description="Identifier of the system/integration that created this workflow.",
    )
    priority: str | None = Field(
        default=None,
        description="Business priority label (e.g. 'high', 'critical').",
    )


# ===========================================================================
# WorkflowState  (root composition)
# ===========================================================================


class WorkflowState(BaseModel):
    """
    Root shared state object that flows through every agent in InsightFlow AI.

    ``WorkflowState`` composes all domain sub-models into a single
    coherent object.  The workflow engine passes this object to each agent
    in sequence; each agent reads its relevant sections, writes its outputs
    to its own section, and returns the updated state.

    Agents NEVER communicate directly — only through this shared state.

    Composition
    -----------
    customer   : CustomerState
    input      : InputState
    context    : ContextState
    analysis   : AnalysisState
    recommendation : RecommendationState
    human_review   : HumanReviewState
    execution  : ExecutionState
    metadata   : MetadataState

    Usage
    -----
    >>> state = WorkflowState(
    ...     customer=CustomerState(customer_id="C-001", company="Acme Corp"),
    ...     input=InputState(user_query="What are the expansion opportunities?"),
    ... )
    >>> state.execution.set_current_agent("InteractionAgent")
    >>> # ... agent does its work ...
    >>> state.execution.mark_agent_completed("InteractionAgent", execution_time_ms=320.5)
    """

    # ── Domain sections ─────────────────────────────────────────────────────

    customer: CustomerState = Field(
        default_factory=CustomerState,
        description="Customer profile information.",
    )
    input: InputState = Field(
        default_factory=InputState,
        description="Raw inputs received by the platform.",
    )
    context: ContextState = Field(
        default_factory=ContextState,
        description="Enterprise context retrieved from external systems.",
    )
    analysis: AnalysisState = Field(
        default_factory=AnalysisState,
        description="Outputs from the analytical agents.",
    )
    recommendation: RecommendationState = Field(
        default_factory=RecommendationState,
        description="Outputs from the recommendation and explanation agents.",
    )
    human_review: HumanReviewState = Field(
        default_factory=HumanReviewState,
        description="Human-in-the-loop review and approval state.",
    )

    # ── Infrastructure sections ─────────────────────────────────────────────

    execution: ExecutionState = Field(
        default_factory=ExecutionState,
        description="Runtime bookkeeping managed by the workflow engine.",
    )
    metadata: MetadataState = Field(
        default_factory=MetadataState,
        description="System-level metadata for audit and observability.",
    )

    # ── Workflow-level helpers ───────────────────────────────────────────────

    def request_human_review(self) -> None:
        """
        Transition the workflow to ``WAITING_FOR_APPROVAL``.

        Marks human review as required and records the request timestamp.
        The workflow engine will suspend execution until a reviewer acts.
        """
        self.human_review.required = True
        self.human_review.review_requested_at = datetime.now(tz=timezone.utc)
        self.execution.execution_status = WorkflowStatus.WAITING_FOR_APPROVAL
        self.execution.update_timestamp()

    def record_review_decision(
        self,
        *,
        approved: bool,
        reviewer_id: str,
        reviewer_name: str | None = None,
        feedback: str | None = None,
    ) -> None:
        """
        Record the outcome of a human review decision.

        After approval the caller is responsible for transitioning
        ``execution.execution_status`` back to ``RUNNING``; after rejection
        they should call ``execution.finalise(WorkflowStatus.CANCELLED)``.

        Parameters
        ----------
        approved:
            ``True`` if the reviewer approved; ``False`` if rejected.
        reviewer_id:
            User ID of the reviewer.
        reviewer_name:
            Display name of the reviewer (optional).
        feedback:
            Free-text feedback from the reviewer (optional).
        """
        now = datetime.now(tz=timezone.utc)
        self.human_review.approved = approved
        self.human_review.reviewer_id = reviewer_id
        self.human_review.reviewer_name = reviewer_name
        self.human_review.feedback = feedback
        self.human_review.review_timestamp = now
        self.execution.update_timestamp()

    def complete(self) -> None:
        """
        Finalise the workflow as ``COMPLETED``.

        Delegates to ``ExecutionState.finalise()`` which records
        ``completed_at`` and computes ``total_execution_time_ms``.
        """
        self.execution.finalise(WorkflowStatus.COMPLETED)

    def fail(self) -> None:
        """
        Finalise the workflow as ``FAILED``.

        Call this after the engine determines that the failure is
        unrecoverable (e.g. retries exhausted).
        """
        self.execution.finalise(WorkflowStatus.FAILED)

    def cancel(self) -> None:
        """
        Finalise the workflow as ``CANCELLED``.

        Intended for operator-initiated cancellation or rejection by a
        human reviewer.
        """
        self.execution.finalise(WorkflowStatus.CANCELLED)

    # ── Snapshot / serialisation helpers ────────────────────────────────────

    def to_snapshot(self) -> dict[str, Any]:
        """
        Return a fully-serialised JSON-compatible snapshot of the state.

        Suitable for persistence (checkpointing), streaming, or audit logs.
        Datetime objects are serialised to ISO-8601 strings.

        Returns
        -------
        dict[str, Any]
            JSON-serialisable representation of the complete workflow state.
        """
        return self.model_dump(mode="json")

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "WorkflowState":
        """
        Reconstruct a ``WorkflowState`` from a previously captured snapshot.

        Parameters
        ----------
        data:
            Dict produced by :meth:`to_snapshot`.

        Returns
        -------
        WorkflowState
            Fully hydrated workflow state.
        """
        return cls.model_validate(data)

    # ── Representation ──────────────────────────────────────────────────────

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"WorkflowState("
            f"workflow_id={self.execution.workflow_id!r} "
            f"status={self.execution.execution_status} "
            f"customer={self.customer.company!r})"
        )
