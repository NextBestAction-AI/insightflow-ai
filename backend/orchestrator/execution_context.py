"""
backend/orchestrator/execution_context.py
==========================================
Runtime execution context for a single request flowing through the
InsightFlow AI workflow engine.

``ExecutionContext`` is created once per inbound request at the API
boundary and then propagated — read-only — alongside the mutable
``WorkflowState``.  It carries correlation identifiers and runtime
control knobs that are orthogonal to domain state.

Design notes
------------
- The model is **frozen** (``frozen=True``): the context is established
  at request ingress and never mutated by agents.
- ``request_id`` is the globally unique identifier for a single HTTP
  request / event trigger.
- ``correlation_id`` groups related requests across service boundaries
  (e.g. a batch job that spawns multiple workflows shares one
  ``correlation_id``).
- ``session_id`` ties together multiple sequential requests within a
  user session.
- ``retry_count`` tracks how many times the workflow engine has
  re-attempted this execution after a transient failure.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.orchestrator.workflow_status import ExecutionMode


# ---------------------------------------------------------------------------
# ExecutionContext
# ---------------------------------------------------------------------------


class ExecutionContext(BaseModel):
    """
    Immutable runtime context for one workflow execution.

    This object is created at the API gateway / event source and injected
    into the workflow engine.  Agents receive it alongside ``WorkflowState``
    for correlation and mode-awareness, but they must **never** mutate it.

    Attributes
    ----------
    request_id : str
        Globally unique identifier for this specific request.
        Defaults to a fresh UUID4 string.
    correlation_id : str
        Groups logically related requests (e.g. all workflows spawned by
        a single batch job).  Defaults to ``request_id`` when not supplied,
        ensuring single requests are self-correlated.
    session_id : str | None
        Identifies the user session; ``None`` for machine-to-machine calls.
    user_id : str | None
        Authenticated user who initiated the request; ``None`` for
        system-triggered executions.
    tenant_id : str | None
        Enterprise tenant identifier for multi-tenant deployments.
        ``None`` in single-tenant configurations.
    execution_mode : ExecutionMode
        Controls whether side-effects and external I/O are live or stubbed.
    retry_count : int
        Number of execution retries attempted so far.  0 on the first try.
    max_retries : int
        Maximum retries the engine will attempt before declaring failure.
    created_at : datetime
        UTC timestamp when this context was created (i.e. request ingress).
    extra : dict[str, Any]
        Extension point for future context attributes (feature flags,
        A/B experiment IDs, etc.) without breaking the model contract.
    """

    model_config = {"frozen": True}

    # ── Correlation identifiers ─────────────────────────────────────────────

    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        min_length=1,
        description=(
            "Globally unique identifier for this specific request. "
            "Used as the primary key in distributed tracing systems."
        ),
    )

    correlation_id: str = Field(
        default="",
        description=(
            "Groups logically related requests across service boundaries. "
            "Defaults to request_id when not supplied."
        ),
    )

    session_id: str | None = Field(
        default=None,
        description=(
            "Identifies the authenticated user session. "
            "None for machine-to-machine or headless executions."
        ),
    )

    # ── Identity ────────────────────────────────────────────────────────────

    user_id: str | None = Field(
        default=None,
        description=(
            "Authenticated user who initiated the request. "
            "None for system-triggered or scheduled executions."
        ),
    )

    tenant_id: str | None = Field(
        default=None,
        description=(
            "Enterprise tenant identifier for multi-tenant deployments. "
            "None in single-tenant configurations."
        ),
    )

    # ── Runtime control ─────────────────────────────────────────────────────

    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.LIVE,
        description=(
            "Controls whether the engine runs agents against live data "
            "or uses stubs / simulation. See ExecutionMode for details."
        ),
    )

    retry_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of execution retries attempted so far. "
            "0 on the first (original) attempt."
        ),
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        description=(
            "Maximum number of retries the engine will attempt "
            "before declaring the workflow as FAILED."
        ),
    )

    # ── Provenance ──────────────────────────────────────────────────────────

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="UTC timestamp recorded at request ingress.",
    )

    # ── Extensibility ───────────────────────────────────────────────────────

    extra: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Open extension point for future context attributes "
            "(feature flags, A/B experiment IDs, custom tracing metadata)."
        ),
    )

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("correlation_id", mode="before")
    @classmethod
    def _default_correlation_to_request(cls, v: str, info) -> str:
        """
        Fall back to ``request_id`` when ``correlation_id`` is not supplied.

        This ensures every context is self-correlated even for isolated
        single requests, simplifying log aggregation queries.
        """
        if not v:
            # ``info.data`` is populated left-to-right; request_id is first.
            return info.data.get("request_id", str(uuid.uuid4()))
        return v

    # ── Convenience properties ───────────────────────────────────────────────

    @property
    def is_live(self) -> bool:
        """Return ``True`` if the engine is running against live data."""
        return self.execution_mode == ExecutionMode.LIVE

    @property
    def is_debug(self) -> bool:
        """Return ``True`` if debug-level tracing and snapshotting is active."""
        return self.execution_mode == ExecutionMode.DEBUG

    @property
    def has_retries_remaining(self) -> bool:
        """Return ``True`` if the engine may attempt another retry."""
        return self.retry_count < self.max_retries

    @property
    def incremented_retry(self) -> "ExecutionContext":
        """
        Return a new ``ExecutionContext`` with ``retry_count`` incremented by 1.

        Because the model is frozen, mutation is expressed as a copy-with-change,
        consistent with the immutable-value pattern.

        Returns
        -------
        ExecutionContext
            A new context instance with the retry counter advanced.

        Raises
        ------
        RuntimeError
            If no retries remain (guards against accidental over-increment).
        """
        if not self.has_retries_remaining:
            raise RuntimeError(
                f"Cannot increment retry_count: already at max_retries={self.max_retries}."
            )
        return self.model_copy(update={"retry_count": self.retry_count + 1})

    # ── Representation ──────────────────────────────────────────────────────

    def __repr__(self) -> str:  # noqa: D105
        return (
            f"ExecutionContext("
            f"request_id={self.request_id!r} "
            f"mode={self.execution_mode} "
            f"retry={self.retry_count}/{self.max_retries})"
        )
