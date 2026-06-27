"""
backend/orchestrator/agent_result.py
======================================
Standard contract returned by every agent in the InsightFlow AI platform.

Every specialised agent (InteractionAgent, KnowledgeAgent, CRMAgent, …)
**must** return an ``AgentResult`` instance.  This enforces a uniform
handshake between agents and the workflow engine regardless of the
agent's internal implementation.

Design notes
------------
- ``AgentResult`` is **immutable** (``frozen=True``) once produced; the
  engine creates a new instance for each invocation.
- ``output_data`` is typed as ``dict[str, Any]`` to remain agnostic of
  the concrete payload — each agent documents what keys it emits.
- ``confidence`` is bounded [0.0, 1.0]; ``None`` signals the agent does
  not produce a calibrated confidence estimate (e.g. deterministic agents).
- ``warnings`` and ``errors`` carry structured diagnostic context separate
  from the boolean ``success`` flag, enabling partial-success reporting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class AgentResult(BaseModel):
    """
    Standardised return value for every agent invocation.

    The workflow engine inspects ``success`` to determine whether to
    advance the workflow or trigger error-handling logic.  All other
    fields are written into the shared ``WorkflowState`` for downstream
    agents and audit consumers.

    Attributes
    ----------
    success : bool
        ``True`` if the agent completed its task without a blocking error.
        A result can be ``success=True`` and still carry ``warnings``.
    agent_name : str
        Canonical agent identifier (e.g. ``"InteractionAgent"``).
        Must be non-empty.
    execution_time_ms : float
        Wall-clock execution time in milliseconds.  Used for latency
        dashboards and SLA monitoring.
    confidence : float | None
        Agent's self-reported confidence in its output, in [0.0, 1.0].
        ``None`` if the agent does not emit a confidence score.
    message : str
        Human-readable summary of the result (success description or
        primary error message).
    warnings : list[str]
        Non-blocking diagnostic messages.  The workflow continues even
        when warnings are present.
    errors : list[str]
        Blocking error descriptions.  When ``success=False`` this list
        MUST be non-empty so operators can diagnose failures.
    output_data : dict[str, Any]
        Structured payload produced by the agent.  The engine writes
        this into the corresponding section of ``WorkflowState``.
    produced_at : datetime
        UTC timestamp recorded when this result was instantiated.
    """

    model_config = {"frozen": True}

    # ── Core result fields ──────────────────────────────────────────────────

    success: bool = Field(
        description=(
            "True if the agent completed its task without a blocking error. "
            "A successful result may still carry warnings."
        ),
    )

    agent_name: str = Field(
        min_length=1,
        description="Canonical agent identifier (e.g. 'InteractionAgent').",
    )

    execution_time_ms: float = Field(
        ge=0.0,
        description="Wall-clock execution time in milliseconds.",
    )

    # ── Confidence ──────────────────────────────────────────────────────────

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Agent's self-reported confidence in its output [0.0, 1.0]. "
            "None if the agent does not emit a calibrated confidence score."
        ),
    )

    # ── Diagnostics ─────────────────────────────────────────────────────────

    message: str = Field(
        default="",
        description=(
            "Human-readable summary of the result — a success description "
            "or the primary error message when success=False."
        ),
    )

    warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Non-blocking diagnostic messages. The workflow continues "
            "even when warnings are present."
        ),
    )

    errors: list[str] = Field(
        default_factory=list,
        description=(
            "Blocking error descriptions. Must be non-empty when "
            "success=False to enable operator diagnosis."
        ),
    )

    # ── Payload ─────────────────────────────────────────────────────────────

    output_data: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured payload produced by the agent. "
            "The engine writes this into the corresponding section of WorkflowState."
        ),
    )

    # ── Provenance ──────────────────────────────────────────────────────────

    produced_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="UTC timestamp recorded when this AgentResult was instantiated.",
    )

    # ── Validators ──────────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_failure_has_errors(self) -> "AgentResult":
        """
        Enforce that a failed result always carries at least one error message.

        This prevents silent failures where ``success=False`` but ``errors``
        is empty, making operator diagnosis impossible.
        """
        if not self.success and not self.errors:
            raise ValueError(
                f"AgentResult for '{self.agent_name}' has success=False "
                "but no entries in 'errors'. Provide at least one error message."
            )
        return self

    @field_validator("agent_name")
    @classmethod
    def _strip_agent_name(cls, v: str) -> str:
        """Strip surrounding whitespace from the agent name."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("agent_name must not be blank or whitespace-only.")
        return stripped

    # ── Factory helpers ─────────────────────────────────────────────────────

    @classmethod
    def success_result(
        cls,
        *,
        agent_name: str,
        execution_time_ms: float,
        output_data: dict[str, Any] | None = None,
        confidence: float | None = None,
        message: str = "",
        warnings: list[str] | None = None,
    ) -> "AgentResult":
        """
        Convenience factory for successful agent outcomes.

        Parameters
        ----------
        agent_name:
            Canonical name of the agent producing this result.
        execution_time_ms:
            Wall-clock runtime in milliseconds.
        output_data:
            Structured payload to merge into WorkflowState.
        confidence:
            Optional self-reported confidence score [0.0, 1.0].
        message:
            Human-readable success summary.
        warnings:
            Optional list of non-blocking diagnostic messages.

        Returns
        -------
        AgentResult
            Immutable result with ``success=True``.
        """
        return cls(
            success=True,
            agent_name=agent_name,
            execution_time_ms=execution_time_ms,
            output_data=output_data or {},
            confidence=confidence,
            message=message,
            warnings=warnings or [],
            errors=[],
        )

    @classmethod
    def failure_result(
        cls,
        *,
        agent_name: str,
        execution_time_ms: float,
        errors: list[str],
        message: str = "",
        warnings: list[str] | None = None,
        output_data: dict[str, Any] | None = None,
    ) -> "AgentResult":
        """
        Convenience factory for failed agent outcomes.

        Parameters
        ----------
        agent_name:
            Canonical name of the agent that failed.
        execution_time_ms:
            Wall-clock runtime in milliseconds (before failure).
        errors:
            One or more error descriptions explaining the failure.
        message:
            Human-readable failure summary (defaults to first error).
        warnings:
            Optional list of non-blocking diagnostic messages emitted
            before the failure occurred.
        output_data:
            Any partial output produced before the failure.

        Returns
        -------
        AgentResult
            Immutable result with ``success=False``.
        """
        if not errors:
            raise ValueError(
                "failure_result requires at least one entry in 'errors'."
            )
        return cls(
            success=False,
            agent_name=agent_name,
            execution_time_ms=execution_time_ms,
            output_data=output_data or {},
            confidence=None,
            message=message or errors[0],
            warnings=warnings or [],
            errors=errors,
        )

    # ── Representation ──────────────────────────────────────────────────────

    def __repr__(self) -> str:  # noqa: D105
        status = "SUCCESS" if self.success else "FAILURE"
        conf = f" conf={self.confidence:.2f}" if self.confidence is not None else ""
        return (
            f"AgentResult({status} agent={self.agent_name!r}"
            f" time={self.execution_time_ms:.1f}ms{conf})"
        )
