"""
backend/orchestrator/state_validator.py
=========================================
Cross-cutting validation layer for ``WorkflowState`` objects.

``StateValidator`` enforces invariants that span multiple sub-models and
cannot be expressed purely at the Pydantic field level.  It is designed
to be called:

1. **Before agent execution** — to assert the state is coherent enough
   for the target agent to run (pre-condition checks).
2. **After agent execution** — to assert the agent fulfilled its contract
   by populating the expected output sections (post-condition checks).
3. **At workflow entry / exit** — for holistic structural health checks.

Design notes
------------
- ``StateValidator`` contains **only** validation logic; it produces no
  side-effects and does not mutate the state it receives.
- All results are returned as :class:`ValidationReport` objects rather
  than raising exceptions directly, giving callers full control over
  error-handling policy.
- Validators are composed from small, single-responsibility check
  functions so new rules can be added without touching existing logic
  (Open/Closed Principle).
- The ``AGENT_PRECONDITIONS`` and ``AGENT_POSTCONDITIONS`` registries map
  canonical agent names to their respective check functions, making it
  trivial to add agents in the future.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from backend.orchestrator.workflow_state import WorkflowState
from backend.orchestrator.workflow_status import WorkflowStatus

logger = logging.getLogger(__name__)


# ===========================================================================
# ValidationIssue & ValidationReport
# ===========================================================================


@dataclass(frozen=True)
class ValidationIssue:
    """
    A single validation finding — either a blocking error or a warning.

    Attributes
    ----------
    code : str
        Machine-readable issue code (e.g. ``"MISSING_CUSTOMER_ID"``).
    message : str
        Human-readable description of the issue.
    severity : str
        ``"ERROR"`` for blocking issues, ``"WARNING"`` for non-blocking.
    field_path : str | None
        Dotted path to the field that triggered the issue
        (e.g. ``"customer.customer_id"``).
    """

    code: str
    message: str
    severity: str  # "ERROR" | "WARNING"
    field_path: str | None = None

    def __str__(self) -> str:  # noqa: D105
        loc = f" [{self.field_path}]" if self.field_path else ""
        return f"[{self.severity}] {self.code}{loc}: {self.message}"


@dataclass
class ValidationReport:
    """
    Aggregated result of one or more validation checks.

    Attributes
    ----------
    is_valid : bool
        ``True`` if no ERROR-severity issues were found.
    issues : list[ValidationIssue]
        All findings (errors and warnings) produced by the validation run.
    checked_at : datetime
        UTC timestamp when the report was generated.
    context : str
        Human-readable label describing what was validated
        (e.g. ``"pre-condition:InteractionAgent"``).
    """

    issues: list[ValidationIssue] = field(default_factory=list)
    checked_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    context: str = ""

    @property
    def is_valid(self) -> bool:
        """Return ``True`` if no ERROR-severity issues are present."""
        return not any(i.severity == "ERROR" for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Return only ERROR-severity issues."""
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Return only WARNING-severity issues."""
        return [i for i in self.issues if i.severity == "WARNING"]

    def add_error(
        self,
        code: str,
        message: str,
        field_path: str | None = None,
    ) -> None:
        """Append a blocking ERROR issue to the report."""
        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
                severity="ERROR",
                field_path=field_path,
            )
        )

    def add_warning(
        self,
        code: str,
        message: str,
        field_path: str | None = None,
    ) -> None:
        """Append a non-blocking WARNING issue to the report."""
        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
                severity="WARNING",
                field_path=field_path,
            )
        )

    def merge(self, other: "ValidationReport") -> None:
        """Merge the issues from another report into this one."""
        self.issues.extend(other.issues)

    def raise_if_invalid(self) -> None:
        """
        Raise a :class:`StateValidationError` if any ERROR issues exist.

        Intended for call sites that treat validation errors as fatal.

        Raises
        ------
        StateValidationError
            When ``is_valid`` is ``False``.
        """
        if not self.is_valid:
            raise StateValidationError(self)

    def __str__(self) -> str:  # noqa: D105
        status = "VALID" if self.is_valid else "INVALID"
        return (
            f"ValidationReport({status} "
            f"context={self.context!r} "
            f"errors={len(self.errors)} "
            f"warnings={len(self.warnings)})"
        )


# ===========================================================================
# StateValidationError
# ===========================================================================


class StateValidationError(Exception):
    """
    Raised when a ``ValidationReport`` contains blocking ERROR issues.

    Attributes
    ----------
    report : ValidationReport
        The full report that triggered the exception.
    """

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        error_lines = "\n  ".join(str(i) for i in report.errors)
        super().__init__(
            f"WorkflowState validation failed ({len(report.errors)} error(s)):\n"
            f"  {error_lines}"
        )


# ===========================================================================
# Primitive check helpers
# ===========================================================================
# Each function accepts a WorkflowState and a ValidationReport, appends
# findings, and returns nothing.  Compose them freely in higher-level checks.

CheckFn = Callable[[WorkflowState, ValidationReport], None]


def _check_customer_id_present(state: WorkflowState, report: ValidationReport) -> None:
    if not state.customer.customer_id:
        report.add_error(
            code="MISSING_CUSTOMER_ID",
            message="customer.customer_id must be set before agents execute.",
            field_path="customer.customer_id",
        )


def _check_customer_company_present(
    state: WorkflowState, report: ValidationReport
) -> None:
    if not state.customer.company:
        report.add_warning(
            code="MISSING_CUSTOMER_COMPANY",
            message="customer.company is empty; recommendations may lack context.",
            field_path="customer.company",
        )


def _check_input_has_content(state: WorkflowState, report: ValidationReport) -> None:
    has_content = any(
        [
            state.input.user_query,
            state.input.transcript,
            state.input.emails,
            state.input.meeting_notes,
            state.input.attachments,
        ]
    )
    if not has_content:
        report.add_error(
            code="EMPTY_INPUT",
            message=(
                "InputState has no content: at least one of user_query, "
                "transcript, emails, meeting_notes, or attachments must be provided."
            ),
            field_path="input",
        )


def _check_workflow_not_terminal(
    state: WorkflowState, report: ValidationReport
) -> None:
    if state.execution.execution_status.is_terminal:
        report.add_error(
            code="WORKFLOW_TERMINAL",
            message=(
                f"Workflow is in terminal status "
                f"'{state.execution.execution_status}'; "
                "no further agents may be invoked."
            ),
            field_path="execution.execution_status",
        )


def _check_context_populated(state: WorkflowState, report: ValidationReport) -> None:
    if not state.context.crm_context and not state.context.knowledge_context:
        report.add_warning(
            code="EMPTY_CONTEXT",
            message=(
                "ContextState has no CRM or knowledge content. "
                "Analysis quality may be degraded."
            ),
            field_path="context",
        )


def _check_interaction_analysis_populated(
    state: WorkflowState, report: ValidationReport
) -> None:
    if not state.analysis.interaction_analysis:
        report.add_error(
            code="MISSING_INTERACTION_ANALYSIS",
            message=(
                "AnalysisState.interaction_analysis is empty. "
                "InteractionAgent must run before this agent."
            ),
            field_path="analysis.interaction_analysis",
        )


def _check_analysis_populated_for_recommendation(
    state: WorkflowState, report: ValidationReport
) -> None:
    missing: list[str] = []
    if not state.analysis.interaction_analysis:
        missing.append("interaction_analysis")
    if not state.analysis.health_assessment:
        missing.append("health_assessment")
    if not state.analysis.business_reasoning:
        missing.append("business_reasoning")
    if missing:
        report.add_error(
            code="INCOMPLETE_ANALYSIS_FOR_RECOMMENDATION",
            message=(
                f"RecommendationAgent requires the following AnalysisState fields "
                f"to be populated: {', '.join(missing)}."
            ),
            field_path="analysis",
        )


def _check_recommendations_present(
    state: WorkflowState, report: ValidationReport
) -> None:
    if not state.analysis.recommendations:
        report.add_error(
            code="MISSING_RECOMMENDATIONS",
            message=(
                "AnalysisState.recommendations is empty. "
                "RecommendationAgent must run before ExplanationAgent."
            ),
            field_path="analysis.recommendations",
        )


def _check_human_review_pending(
    state: WorkflowState, report: ValidationReport
) -> None:
    if (
        state.execution.execution_status == WorkflowStatus.WAITING_FOR_APPROVAL
        and state.human_review.is_pending
        and not state.human_review.is_decided
    ):
        report.add_warning(
            code="HUMAN_REVIEW_PENDING",
            message=(
                "Workflow is WAITING_FOR_APPROVAL but no review decision "
                "has been recorded. Downstream agents are blocked."
            ),
            field_path="human_review",
        )




def _check_failed_agents_without_errors(
    state: WorkflowState, report: ValidationReport
) -> None:
    for agent_name in state.execution.failed_agents:
        record = state.execution.agent_records.get(agent_name)
        if record and not record.error_message:
            report.add_warning(
                code="FAILED_AGENT_MISSING_ERROR",
                message=(
                    f"Agent '{agent_name}' is listed in failed_agents but "
                    "has no error_message in its execution record."
                ),
                field_path=f"execution.agent_records.{agent_name}.error_message",
            )


# ===========================================================================
# Per-agent precondition / postcondition registries
# ===========================================================================

#: Maps agent name -> list of pre-condition check functions.
AGENT_PRECONDITIONS: dict[str, list[CheckFn]] = {
    "InteractionAgent": [
        _check_customer_id_present,
        _check_input_has_content,
        _check_workflow_not_terminal,
    ],
    "KnowledgeAgent": [
        _check_customer_id_present,
        _check_workflow_not_terminal,
    ],
    "CRMAgent": [
        _check_customer_id_present,
        _check_workflow_not_terminal,
    ],
    "RiskAgent": [
        _check_customer_id_present,
        _check_interaction_analysis_populated,
        _check_workflow_not_terminal,
    ],
    "ReasoningAgent": [
        _check_customer_id_present,
        _check_context_populated,
        _check_interaction_analysis_populated,
        _check_workflow_not_terminal,
    ],
    "RecommendationAgent": [
        _check_analysis_populated_for_recommendation,
        _check_workflow_not_terminal,
    ],
    "ExplanationAgent": [
        _check_recommendations_present,
        _check_workflow_not_terminal,
    ],
}

#: Maps agent name -> list of post-condition check functions.
AGENT_POSTCONDITIONS: dict[str, list[CheckFn]] = {
    "InteractionAgent": [
        _check_interaction_analysis_populated,
    ],
    "RecommendationAgent": [
        _check_recommendations_present,
    ],
}


# ===========================================================================
# StateValidator
# ===========================================================================


class StateValidator:
    """
    Cross-cutting validator for :class:`~backend.orchestrator.workflow_state.WorkflowState`.

    All methods are **pure** (no side-effects, no mutations).  Validation
    results are returned as :class:`ValidationReport` objects.

    Typical usage
    -------------
    >>> validator = StateValidator()
    >>> # Before running InteractionAgent:
    >>> report = validator.check_preconditions(state, "InteractionAgent")
    >>> report.raise_if_invalid()
    >>> # After running RecommendationAgent:
    >>> post_report = validator.check_postconditions(state, "RecommendationAgent")
    >>> if not post_report.is_valid:
    ...     logger.error("Post-condition violated: %s", post_report)
    """

    # ── Structural health check ─────────────────────────────────────────────

    def check_structural_integrity(self, state: WorkflowState) -> ValidationReport:
        """
        Run a holistic set of cross-model invariant checks.

        This is suitable for use at workflow entry, checkpoint restore,
        or whenever a "full health check" is needed.

        Parameters
        ----------
        state:
            The ``WorkflowState`` to validate.

        Returns
        -------
        ValidationReport
            Aggregated findings across all structural checks.
        """
        report = ValidationReport(context="structural_integrity")

        checks: list[CheckFn] = [
            _check_customer_id_present,
            _check_customer_company_present,
            _check_workflow_not_terminal,
            _check_context_populated,
            _check_failed_agents_without_errors,
            _check_human_review_pending,
        ]

        for check in checks:
            try:
                check(state, report)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected error in structural check %s", check.__name__)
                report.add_error(
                    code="VALIDATOR_INTERNAL_ERROR",
                    message=f"Validator '{check.__name__}' raised: {exc}",
                )

        self._log_report(report)
        return report

    # ── Per-agent pre-condition check ───────────────────────────────────────

    def check_preconditions(
        self,
        state: WorkflowState,
        agent_name: str,
    ) -> ValidationReport:
        """
        Verify that ``state`` satisfies all pre-conditions for ``agent_name``.

        Parameters
        ----------
        state:
            Current workflow state before the agent runs.
        agent_name:
            Canonical agent name (must match a key in ``AGENT_PRECONDITIONS``).

        Returns
        -------
        ValidationReport
            Findings; check ``is_valid`` before allowing the agent to run.
        """
        report = ValidationReport(context=f"pre-condition:{agent_name}")

        checks = AGENT_PRECONDITIONS.get(agent_name, [])
        if not checks:
            report.add_warning(
                code="NO_PRECONDITIONS_REGISTERED",
                message=(
                    f"No pre-condition checks registered for agent '{agent_name}'. "
                    "Consider registering checks in AGENT_PRECONDITIONS."
                ),
            )
            return report

        for check in checks:
            try:
                check(state, report)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Unexpected error in precondition check %s for agent %s",
                    check.__name__,
                    agent_name,
                )
                report.add_error(
                    code="PRECONDITION_INTERNAL_ERROR",
                    message=f"Check '{check.__name__}' raised: {exc}",
                )

        self._log_report(report)
        return report

    # ── Per-agent post-condition check ──────────────────────────────────────

    def check_postconditions(
        self,
        state: WorkflowState,
        agent_name: str,
    ) -> ValidationReport:
        """
        Verify that ``agent_name`` fulfilled its output contract.

        Parameters
        ----------
        state:
            Workflow state after the agent has run.
        agent_name:
            Canonical agent name (must match a key in ``AGENT_POSTCONDITIONS``).

        Returns
        -------
        ValidationReport
            Findings; check ``is_valid`` to confirm the contract was met.
        """
        report = ValidationReport(context=f"post-condition:{agent_name}")

        checks = AGENT_POSTCONDITIONS.get(agent_name, [])
        if not checks:
            # Not all agents have registered post-conditions; that is fine.
            return report

        for check in checks:
            try:
                check(state, report)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Unexpected error in postcondition check %s for agent %s",
                    check.__name__,
                    agent_name,
                )
                report.add_error(
                    code="POSTCONDITION_INTERNAL_ERROR",
                    message=f"Check '{check.__name__}' raised: {exc}",
                )

        self._log_report(report)
        return report

    # ── Custom check runner ─────────────────────────────────────────────────

    def run_checks(
        self,
        state: WorkflowState,
        checks: list[CheckFn],
        context: str = "custom",
    ) -> ValidationReport:
        """
        Execute an arbitrary list of check functions against ``state``.

        Use this for composing one-off or agent-specific validation
        suites without modifying the global registries.

        Parameters
        ----------
        state:
            The ``WorkflowState`` to validate.
        checks:
            A list of :data:`CheckFn` callables.
        context:
            Human-readable label for the report context.

        Returns
        -------
        ValidationReport
            Aggregated findings from all provided checks.
        """
        report = ValidationReport(context=context)
        for check in checks:
            try:
                check(state, report)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected error in custom check %s", check.__name__)
                report.add_error(
                    code="CUSTOM_CHECK_INTERNAL_ERROR",
                    message=f"Check '{check.__name__}' raised: {exc}",
                )
        self._log_report(report)
        return report

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _log_report(report: ValidationReport) -> None:
        """Emit a structured log line summarising the validation outcome."""
        if report.is_valid:
            if report.warnings:
                logger.warning(
                    "State validation passed with warnings | context=%s warnings=%d",
                    report.context,
                    len(report.warnings),
                )
            else:
                logger.debug(
                    "State validation passed | context=%s",
                    report.context,
                )
        else:
            logger.error(
                "State validation FAILED | context=%s errors=%d warnings=%d",
                report.context,
                len(report.errors),
                len(report.warnings),
            )
