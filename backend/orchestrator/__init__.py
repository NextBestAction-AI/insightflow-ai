"""
backend/orchestrator/__init__.py
==================================
Public surface of the InsightFlow AI orchestrator state infrastructure.

Import from here instead of individual modules to insulate call sites
from internal refactors.

Quick-start
-----------
>>> from backend.orchestrator import (
...     WorkflowState,
...     ExecutionContext,
...     WorkflowStatus,
...     AgentResult,
...     StateValidator,
... )
>>> state = WorkflowState()
>>> ctx   = ExecutionContext(user_id="usr-001")
>>> validator = StateValidator()
>>> report = validator.check_preconditions(state, "InteractionAgent")
"""

from __future__ import annotations

# ── Enumerations ─────────────────────────────────────────────────────────────
from backend.orchestrator.workflow_status import (
    ACTIVE_STATUSES,
    AGENT_TERMINAL_STATUSES,
    TERMINAL_STATUSES,
    AgentStatus,
    ExecutionMode,
    WorkflowStatus,
)

# ── Agent return contract ─────────────────────────────────────────────────────
from backend.orchestrator.agent_result import AgentResult

# ── Runtime context ───────────────────────────────────────────────────────────
from backend.orchestrator.execution_context import ExecutionContext

# ── Workflow state (root + sub-models) ────────────────────────────────────────
from backend.orchestrator.workflow_state import (
    AgentExecutionRecord,
    AnalysisState,
    ContextState,
    CustomerState,
    ExecutionState,
    HumanReviewState,
    InputState,
    MetadataState,
    RecommendationState,
    WorkflowState,
)

# ── Validation layer ──────────────────────────────────────────────────────────
from backend.orchestrator.state_validator import (
    AGENT_POSTCONDITIONS,
    AGENT_PRECONDITIONS,
    CheckFn,
    StateValidationError,
    StateValidator,
    ValidationIssue,
    ValidationReport,
)

__all__: list[str] = [
    # Enumerations
    "WorkflowStatus",
    "AgentStatus",
    "ExecutionMode",
    "TERMINAL_STATUSES",
    "ACTIVE_STATUSES",
    "AGENT_TERMINAL_STATUSES",
    # Agent contract
    "AgentResult",
    # Runtime context
    "ExecutionContext",
    # Workflow state — root
    "WorkflowState",
    # Workflow state — sub-models
    "CustomerState",
    "InputState",
    "ContextState",
    "AnalysisState",
    "RecommendationState",
    "HumanReviewState",
    "ExecutionState",
    "AgentExecutionRecord",
    "MetadataState",
    # Validation
    "StateValidator",
    "ValidationReport",
    "ValidationIssue",
    "StateValidationError",
    "CheckFn",
    "AGENT_PRECONDITIONS",
    "AGENT_POSTCONDITIONS",
]
