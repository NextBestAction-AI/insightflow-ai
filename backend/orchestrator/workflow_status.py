"""
backend/orchestrator/workflow_status.py
========================================
Enumerations representing the lifecycle status of a workflow execution
and individual agent invocations within the InsightFlow AI platform.

These enums are used throughout the orchestrator to drive routing logic,
surface state to operators, and enable audit-log filtering — without
coupling any business rules to the state layer itself.

Design notes
------------
- All enums extend ``str`` so they serialise transparently with JSON /
  Pydantic without custom encoders.
- ``WorkflowStatus`` models coarse-grained workflow lifecycle.
- ``AgentStatus`` models fine-grained per-agent execution lifecycle.
- Terminal states (COMPLETED, FAILED, CANCELLED) are grouped via the
  ``TERMINAL_STATUSES`` / ``AGENT_TERMINAL_STATUSES`` sentinel sets to
  avoid ad-hoc string comparisons in routing code.
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# WorkflowStatus
# ---------------------------------------------------------------------------


class WorkflowStatus(str, Enum):
    """
    Coarse-grained lifecycle status for an entire workflow run.

    Transitions
    -----------
    ::

        CREATED
          │
          ▼
        RUNNING ──────────────────────────────────────────────────────┐
          │                                                            │
          ▼                                                            │
        WAITING_FOR_APPROVAL  ──► (reviewer acts) ──► RUNNING        │
          │                                                            │
          ▼                                                            ▼
        COMPLETED                                                   FAILED
                                                                       │
                                                           (operator)  ▼
                                                                  CANCELLED

    Notes
    -----
    - ``WAITING_FOR_APPROVAL`` suspends the workflow until a human
      reviewer approves or rejects the pending recommendation set.
    - ``CANCELLED`` is an operator-initiated hard stop and is distinct
      from ``FAILED`` (system-initiated error termination).
    """

    CREATED = "CREATED"
    """Workflow record has been persisted; no agent has been invoked yet."""

    RUNNING = "RUNNING"
    """At least one agent is actively executing or has been scheduled."""

    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    """
    Workflow is suspended, awaiting human-in-the-loop approval before
    proceeding to downstream agents (e.g. Recommendation -> Explanation).
    """

    COMPLETED = "COMPLETED"
    """All required agents finished successfully; output is ready."""

    FAILED = "FAILED"
    """
    One or more agents encountered an unrecoverable error.
    The ``ExecutionState.failed_agents`` list carries per-agent details.
    """

    CANCELLED = "CANCELLED"
    """Workflow was explicitly cancelled by an operator or system policy."""

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` if the workflow has reached a terminal state."""
        return self in TERMINAL_STATUSES

    @property
    def is_active(self) -> bool:
        """Return ``True`` if the workflow can still accept agent updates."""
        return self in ACTIVE_STATUSES

    def __str__(self) -> str:  # noqa: D105
        return self.value


# Sentinel sets — use these instead of raw string comparisons.
TERMINAL_STATUSES: frozenset[WorkflowStatus] = frozenset(
    {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    }
)
"""Statuses from which no further transitions are permitted."""

ACTIVE_STATUSES: frozenset[WorkflowStatus] = frozenset(
    {
        WorkflowStatus.RUNNING,
        WorkflowStatus.WAITING_FOR_APPROVAL,
    }
)
"""Statuses in which agent invocations may still update the workflow."""


# ---------------------------------------------------------------------------
# AgentStatus
# ---------------------------------------------------------------------------


class AgentStatus(str, Enum):
    """
    Fine-grained lifecycle status for a single agent invocation.

    Transitions
    -----------
    ::

        PENDING -> RUNNING -> COMPLETED
                      |
                      |-> FAILED
                      |
                      -> SKIPPED

    Notes
    -----
    - ``SKIPPED`` indicates the agent was intentionally bypassed by the
      planner (e.g. due to a routing condition), not that it errored.
    - ``RETRYING`` is set by the workflow engine when a transient failure
      triggers a retry attempt; it reverts to ``RUNNING`` on the next try.
    """

    PENDING = "PENDING"
    """Agent is registered in the execution plan but has not started."""

    RUNNING = "RUNNING"
    """Agent is currently executing."""

    RETRYING = "RETRYING"
    """Agent encountered a transient error and is scheduled for retry."""

    COMPLETED = "COMPLETED"
    """Agent finished successfully and wrote results to WorkflowState."""

    FAILED = "FAILED"
    """Agent terminated with an unrecoverable error."""

    SKIPPED = "SKIPPED"
    """Agent was intentionally bypassed by the workflow planner."""

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` if the agent invocation has reached a terminal state."""
        return self in AGENT_TERMINAL_STATUSES

    def __str__(self) -> str:  # noqa: D105
        return self.value


AGENT_TERMINAL_STATUSES: frozenset[AgentStatus] = frozenset(
    {
        AgentStatus.COMPLETED,
        AgentStatus.FAILED,
        AgentStatus.SKIPPED,
    }
)
"""Agent statuses from which no further transitions are permitted."""


# ---------------------------------------------------------------------------
# ExecutionMode  (used by ExecutionContext)
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):
    """
    Controls the runtime behaviour of the workflow engine.

    Modes
    -----
    ``LIVE``
        Full production run — all agents execute against real data sources.
    ``DRY_RUN``
        Agents execute but external side-effects (CRM writes, notifications)
        are suppressed.  Useful for pre-flight validation.
    ``SIMULATION``
        All external I/O is stubbed; the engine uses fixture data.
        Intended for integration tests and demos.
    ``DEBUG``
        Identical to ``LIVE`` but verbose tracing is enabled and every
        intermediate state snapshot is persisted for inspection.
    """

    LIVE = "LIVE"
    DRY_RUN = "DRY_RUN"
    SIMULATION = "SIMULATION"
    DEBUG = "DEBUG"

    def __str__(self) -> str:  # noqa: D105
        return self.value
