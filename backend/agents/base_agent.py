# -*- coding: utf-8 -*-
"""
backend/agents/base_agent.py
==============================
Abstract base class for every agent in the InsightFlow AI platform.
"""


from __future__ import annotations

import logging
import time
import traceback
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from backend.orchestrator.agent_result import AgentResult
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.state_validator import StateValidator
from backend.orchestrator.workflow_state import WorkflowState
from backend.orchestrator.workflow_status import WorkflowStatus
from backend.services.llm.exceptions import LLMBaseError
from backend.services.llm.llm_service import LLMService, create_llm_service
from backend.services.llm.prompt_manager import PromptManager


# ---------------------------------------------------------------------------
# AgentMetrics
# ---------------------------------------------------------------------------


class AgentMetrics:
    """
    Lightweight, per-invocation metrics collector.

    Collected by :class:`BaseAgent` during each ``run()`` call and
    attached to the ``AgentResult`` via ``output_data["_metrics"]``.
    Consumers (dashboards, audit logs) can strip or promote this key as
    needed.

    Core fields (always present)
    ----------------------------
    agent_name : str
        Canonical agent identifier.
    started_at : float
        ``time.monotonic()`` value at execution start.
    ended_at : float | None
        ``time.monotonic()`` value at execution end; ``None`` until set.
    success : bool | None
        Outcome; ``None`` until the execution completes.
    retry_count : int
        Retry count read from :class:`ExecutionContext`.
    llm_calls : int
        Number of times :attr:`BaseAgent.llm` was invoked (must be
        incremented manually by child agents via
        :meth:`BaseAgent._record_llm_call`).
    warnings : list[str]
        Diagnostic warnings accumulated during the lifecycle.

    Extensibility
    -------------
    The ``_extra`` dict provides an open-ended extension point for
    domain-specific counters, latency breakdowns, token counts, or any
    other metric a future agent needs to track - without modifying this
    class or ``BaseAgent``.

    Child agents write to it via :meth:`BaseAgent._record_metric`::

        self._record_metric("tokens_used", 1024)
        self._record_metric("knowledge_articles_fetched", 3)

    All extra metrics are serialised alongside core fields in
    :meth:`to_dict` under the key ``"extra"``.
    """

    # Core slots keep memory layout compact for the common case.
    # _extra lives outside __slots__ intentionally so subclasses can
    # add metrics without touching this class.
    __slots__ = (
        "agent_name",
        "started_at",
        "ended_at",
        "success",
        "retry_count",
        "llm_calls",
        "warnings",
        "_extra",
    )

    def __init__(self, agent_name: str, retry_count: int = 0) -> None:
        self.agent_name: str = agent_name
        self.started_at: float = time.monotonic()
        self.ended_at: float | None = None
        self.success: bool | None = None
        self.retry_count: int = retry_count
        self.llm_calls: int = 0
        self.warnings: list[str] = []
        # Open-ended extension point: any key/value a future agent needs.
        self._extra: dict[str, Any] = {}

    def stop(self, *, success: bool) -> None:
        """Mark execution as finished and record the outcome."""
        self.ended_at = time.monotonic()
        self.success = success

    def record_extra(self, key: str, value: Any) -> None:
        """
        Store an arbitrary metric under ``key``.

        Intended for use by child agents (via
        :meth:`BaseAgent._record_metric`) to capture domain-specific
        counters or latency breakdowns without modifying this class.

        If ``key`` already exists and both the existing value and
        ``value`` are numeric, the new value is **added** to the existing
        one (accumulator semantics).  Otherwise the value is overwritten.

        Parameters
        ----------
        key:
            Metric name (e.g. ``"tokens_used"``, ``"kb_articles_fetched"``).
        value:
            Metric value - any JSON-serialisable type.
        """
        existing = self._extra.get(key)
        if existing is not None and isinstance(existing, (int, float)) and isinstance(value, (int, float)):
            self._extra[key] = existing + value
        else:
            self._extra[key] = value

    @property
    def elapsed_ms(self) -> float:
        """
        Wall-clock time from ``started_at`` to ``ended_at`` (or now).

        Returns
        -------
        float
            Elapsed milliseconds.
        """
        end = self.ended_at if self.ended_at is not None else time.monotonic()
        return (end - self.started_at) * 1000.0

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise all metrics to a JSON-safe dict for inclusion in ``AgentResult``.

        Core fields are always present at the top level.  Agent-specific
        metrics registered via :meth:`record_extra` appear under ``"extra"``.
        """
        return {
            "agent_name": self.agent_name,
            "execution_time_ms": round(self.elapsed_ms, 2),
            "success": self.success,
            "retry_count": self.retry_count,
            "llm_calls": self.llm_calls,
            "warnings": list(self.warnings),
            "extra": dict(self._extra),
        }


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------


class BaseAgent(ABC):
    """
    Abstract execution framework for all InsightFlow AI agents.

    Every specialised agent (``InteractionAgent``, ``KnowledgeAgent``, ...)
    **must** inherit from this class.  The class encapsulates:

    * Structured per-agent logging.
    * Execution timing and metrics collection.
    * Lifecycle management via the Template Method Pattern.
    * Automatic :class:`~backend.orchestrator.state_validator.StateValidator`
      integration - pre- and post-conditions are validated around ``execute``
      without any boilerplate in child agents.
    * Observability lifecycle events (``on_start``, ``on_success``,
      ``on_failure``) for future monitoring integrations.
    * Centralised error handling that never propagates raw exceptions to
      the workflow engine - failures are captured and returned as an
      ``AgentResult`` with ``success=False``.
    * Dependency-injected access to ``LLMService`` and ``PromptManager``
      so child agents never construct their own service instances.

    Parameters
    ----------
    llm_service : LLMService | None
        Pre-wired ``LLMService`` instance.  When ``None``, the class
        calls :func:`~backend.services.llm.llm_service.create_llm_service`
        to build a default instance.  Inject a mock in tests.
    prompt_manager : PromptManager | None
        Pre-built ``PromptManager`` instance.  When ``None``, a default
        instance pointing at the standard ``prompts/`` directory is created.
    state_validator : StateValidator | None
        Pre-built :class:`~backend.orchestrator.state_validator.StateValidator`
        instance.  When ``None``, a default instance is created.  Override
        in tests to inject a stub that always passes.

    Declarative Class Attributes
    ----------------------------
    Subclasses declare metadata as ``ClassVar`` attributes.  The Planner
    reads these via :meth:`get_agent_metadata` to build execution DAGs
    **without** instantiating agents.

    agent_name : str
        **Required.**  Canonical identifier used in logs, ``AgentResult``,
        and ``WorkflowState`` tracking.
    description : str
        Human-readable summary of what this agent does.
    required_inputs : list[str]
        Dotted-path keys the agent reads from ``WorkflowState``
        (e.g. ``["input.transcript", "context.crm_context"]``).
        The Planner uses this to check whether prerequisites are satisfied
        before scheduling this agent.
    produced_outputs : list[str]
        Dotted-path keys the agent writes to ``WorkflowState``
        (e.g. ``["analysis.interaction_analysis"]``).
        The Planner uses this to determine which downstream agents become
        unblocked once this agent completes.
    supported_execution_modes : list[str]
        Execution modes in which this agent may run
        (e.g. ``["LIVE", "DEBUG", "DRY_RUN"]``).
        Agents not supporting the current mode are skipped by the Planner.
        An empty list means **all** modes are supported (default behaviour).
    priority : int
        Relative scheduling priority for parallel branches.
        Higher values are scheduled first.  Default is ``0`` (no preference).

    Notes
    -----
    * ``run()`` is **not** marked ``final`` at runtime (Python does not
      enforce ``@final`` on abstract classes), but child agents must treat
      it as sealed.  Override the hook methods instead.
    * Hooks that return ``None`` (all except ``execute``) signal success by
      not raising.  Any exception raised inside a hook propagates to
      ``run()``'s error handler, which records it as a failure.
    * :class:`StateValidator` validation warnings are non-fatal; they are
      appended to ``AgentResult.warnings`` and do not fail the run.
      Validation errors ARE fatal and cause a failure result.
    """

    # -- Required class variable - subclasses MUST override -------------------
    agent_name: ClassVar[str] = "BaseAgent"

    # -- Optional declarative metadata - subclasses SHOULD override -----------
    # These are introspected by the Planner via get_agent_metadata() without
    # instantiating the agent, so they must be ClassVars, not instance attrs.

    description: ClassVar[str] = ""
    """
    Human-readable description of what this agent does.
    Used by the Planner for logging, operator dashboards, and documentation
    generation.  Keep to 1-2 sentences.
    """

    required_inputs: ClassVar[list[str]] = []
    """
    Dotted-path keys this agent reads from ``WorkflowState``.

    Format: ``"<sub-model>.<field>"``  e.g. ``"input.transcript"``.

    The Planner evaluates these paths to decide whether the state is
    ready for this agent.  An empty list means the agent has no
    data-level prerequisites (it may still depend on execution order).
    """

    produced_outputs: ClassVar[list[str]] = []
    """
    Dotted-path keys this agent writes to ``WorkflowState``.

    Format: ``"<sub-model>.<field>"``  e.g. ``"analysis.interaction_analysis"``.

    The Planner cross-references these against ``required_inputs`` of
    downstream agents to determine scheduling order and detect missing
    dependencies at plan-time rather than at runtime.
    """

    supported_execution_modes: ClassVar[list[str]] = []
    """
    Execution modes in which this agent is permitted to run.

    Values should match :class:`~backend.orchestrator.workflow_status.ExecutionMode`
    string values (e.g. ``"LIVE"``, ``"DEBUG"``, ``"DRY_RUN"``,
    ``"SIMULATION"``).

    An empty list (the default) means the agent supports **all** modes.
    The Planner uses this to skip agents that are not compatible with the
    current :class:`~backend.orchestrator.execution_context.ExecutionContext`.
    """

    priority: ClassVar[int] = 0
    """
    Relative scheduling priority for parallel agent branches.

    Higher values are dispatched first within a parallel group.
    Agents in a strict sequential chain ignore this value.
    Default is ``0`` (no scheduling preference).
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        prompt_manager: PromptManager | None = None,
        state_validator: StateValidator | None = None,
    ) -> None:
        # Validate that the subclass has set agent_name properly.
        # We compare against the base-class default to catch omissions.
        if type(self).agent_name == BaseAgent.agent_name and type(self) is not BaseAgent:
            raise TypeError(
                f"{type(self).__name__} must define the class variable "
                f"'agent_name' with a unique, non-empty string."
            )

        # -- Injected collaborators -------------------------------------------
        # Prefer injected instances to support test-time mocking.
        # Fall back to factory construction for production use.
        self._llm: LLMService = llm_service or create_llm_service()
        self._prompt_manager: PromptManager = prompt_manager or PromptManager()
        # StateValidator is injected so tests can supply a no-op stub.
        self._state_validator: StateValidator = state_validator or StateValidator()

        # -- Per-instance logger scoped to the concrete agent name ------------
        # Using a hierarchical name keeps log configuration clean:
        # ``logging.getLogger("backend.agents")`` captures all agents at once.
        self._logger: logging.Logger = logging.getLogger(
            f"backend.agents.{self.agent_name}"
        )

        # Metrics for the current invocation; reset at the start of each run().
        self._metrics: AgentMetrics | None = None

        self._logger.debug("%s initialised.", self.agent_name)

    # =========================================================================
    # Public API - callers use only this method
    # =========================================================================

    async def run(
        self,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> AgentResult:
        """
        Execute the full agent lifecycle and return a standardised result.

        This method is the **only** entry point that the workflow engine
        should call.  It:

        1. Records the start timestamp and initialises metrics.
        2. Fires the ``on_start()`` observability event.
        3. Logs structured entry information.
        4. Delegates to each hook in the defined order.
        5. Runs :class:`StateValidator` pre-conditions after ``validate_input``
           and post-conditions after ``validate_output``.
        6. Constructs and returns an :class:`AgentResult`.
        7. Fires ``on_success()`` or ``on_failure()`` depending on outcome.
        8. Handles any unexpected exception, ensuring the workflow is never
           crashed by an agent bug - it always returns an ``AgentResult``.
        9. Calls ``cleanup()`` unconditionally (even after failures).

        Parameters
        ----------
        state:
            The shared :class:`~backend.orchestrator.workflow_state.WorkflowState`.
            Read the sections relevant to this agent; write only to your
            own section.
        context:
            Immutable :class:`~backend.orchestrator.execution_context.ExecutionContext`
            carrying correlation IDs, execution mode, and retry information.

        Returns
        -------
        AgentResult
            Always returned - never raises.  Check ``AgentResult.success``
            to determine whether to advance or halt the workflow.
        """
        # -- Initialise per-run metrics ----------------------------------------
        self._metrics = AgentMetrics(
            agent_name=self.agent_name,
            retry_count=context.retry_count,
        )

        # -- Observability: on_start -------------------------------------------
        # Fired before any lifecycle hook so external monitors see the event
        # even if initialize() raises.
        await self._fire_event("on_start", state, context)

        # -- Structured entry log ----------------------------------------------
        self._logger.info(
            "[%s] Started execution | request_id=%s mode=%s retry=%d/%d",
            self.agent_name,
            context.request_id,
            context.execution_mode,
            context.retry_count,
            context.max_retries,
        )

        result: AgentResult | None = None
        exec_exception: Exception | None = None

        try:
            # -- Lifecycle: initialize -----------------------------------------
            await self._run_hook("initialize", state, context)

            # -- Lifecycle: validate_input -------------------------------------
            await self._run_hook("validate_input", state, context)

            # -- StateValidator: pre-conditions --------------------------------
            # Runs automatically so every agent gets structural checks without
            # boilerplate.  Warnings are surfaced; errors abort the run.
            await self._run_precondition_validation(state)

            # -- Lifecycle: before_execute -------------------------------------
            await self._run_hook("before_execute", state, context)

            # -- Lifecycle: execute (ABSTRACT) ---------------------------------
            self._logger.debug("[%s] Calling execute().", self.agent_name)
            raw_result: AgentResult = await self.execute(state, context)

            # -- Lifecycle: after_execute --------------------------------------
            await self._run_hook("after_execute", state, context)

            # -- Lifecycle: validate_output ------------------------------------
            await self._run_hook("validate_output", state, context)

            # -- StateValidator: post-conditions -------------------------------
            # Verifies the agent fulfilled its output contract.  Warnings are
            # surfaced; errors cause a failure result.
            await self._run_postcondition_validation(state)

            # -- Stop timer, annotate metrics ----------------------------------
            self._metrics.stop(success=True)
            elapsed = self._metrics.elapsed_ms

            # Rebuild the result with the authoritative execution_time_ms so
            # child agents never need to measure their own wall-clock time.
            result = self._enrich_result(raw_result, elapsed)

            # -- Observability: on_success -------------------------------------
            await self._fire_event("on_success", state, context)

        except Exception as exc:  # noqa: BLE001
            exec_exception = exc
            self._metrics.stop(success=False)
            elapsed = self._metrics.elapsed_ms

            # -- Observability: on_failure -------------------------------------
            await self._fire_event("on_failure", state, context)

            # Delegate to the overridable error handler.
            result = await self._handle_error_internal(exc, state, context, elapsed)

        finally:
            # cleanup() must run regardless of success or failure.
            try:
                await self.cleanup(state, context)
            except Exception as cleanup_exc:  # noqa: BLE001
                # A cleanup failure is non-fatal but must be logged.
                self._logger.error(
                    "[%s] cleanup() raised an unexpected exception: %s",
                    self.agent_name,
                    cleanup_exc,
                    exc_info=True,
                )
                if result is not None and self._metrics is not None:
                    self._metrics.warnings.append(
                        f"cleanup() raised: {type(cleanup_exc).__name__}: {cleanup_exc}"
                    )

            # -- Structured exit log -------------------------------------------
            status_label = "SUCCESS" if (result and result.success) else "FAILURE"
            elapsed_final = self._metrics.elapsed_ms if self._metrics else 0.0
            self._logger.info(
                "[%s] Finished in %.1fms | status=%s request_id=%s",
                self.agent_name,
                elapsed_final,
                status_label,
                context.request_id,
            )

        # result is always set at this point - either from the success
        # branch or from _handle_error_internal.
        assert result is not None, "BaseAgent.run() must always produce an AgentResult."
        return result

    # =========================================================================
    # Planner introspection - classmethod, no instance required
    # =========================================================================

    @classmethod
    def get_agent_metadata(cls) -> dict[str, Any]:
        """
        Return the declarative metadata for this agent class.

        This is the **primary integration point for the Planner**.  It can
        be called on the class itself - no instantiation required - so the
        Planner can inspect all registered agents cheaply at startup or
        plan-time:

        .. code-block:: python

            for agent_cls in AGENT_REGISTRY:
                meta = agent_cls.get_agent_metadata()
                print(meta["agent_name"], meta["required_inputs"])

        Planner use-cases
        -----------------
        * **DAG construction** - cross-reference ``required_inputs`` against
          ``produced_outputs`` of other agents to derive scheduling order.
        * **Pre-flight validation** - detect missing dependencies (no agent
          produces what another requires) before any agent runs.
        * **Mode filtering** - skip agents whose
          ``supported_execution_modes`` does not include the current mode.
          An empty list means the agent supports all modes.
        * **Priority scheduling** - within a parallel group, dispatch agents
          with higher ``priority`` values first.
        * **Documentation / operator UIs** - surface ``description`` without
          requiring a running instance.

        Returns
        -------
        dict[str, Any]
            Keys:

            ``agent_name`` : str
                Canonical agent identifier.
            ``description`` : str
                Human-readable summary.
            ``required_inputs`` : list[str]
                Dotted-path state keys this agent reads.
            ``produced_outputs`` : list[str]
                Dotted-path state keys this agent writes.
            ``supported_execution_modes`` : list[str]
                Execution modes this agent supports (empty = all).
            ``priority`` : int
                Scheduling priority within parallel branches.
        """
        return {
            "agent_name": cls.agent_name,
            "description": cls.description,
            "required_inputs": list(cls.required_inputs),
            "produced_outputs": list(cls.produced_outputs),
            "supported_execution_modes": list(cls.supported_execution_modes),
            "priority": cls.priority,
        }

    # =========================================================================
    # Abstract method - child agents implement ONLY this
    # =========================================================================

    @abstractmethod
    async def execute(
        self,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> AgentResult:
        """
        Core business logic for this agent.

        This is the **only** method child agents are required to implement.
        The ``execution_time_ms`` field in the returned ``AgentResult`` will
        be overwritten by :meth:`run` with the authoritative wall-clock time,
        so child agents may pass ``0.0`` as a placeholder.

        Parameters
        ----------
        state:
            Shared workflow state.  Read from context / analysis sections;
            write only to the section owned by this agent.
        context:
            Immutable runtime context (correlation IDs, execution mode, ...).

        Returns
        -------
        AgentResult
            The agent's output.  Use
            :meth:`~backend.orchestrator.agent_result.AgentResult.success_result`
            or
            :meth:`~backend.orchestrator.agent_result.AgentResult.failure_result`
            factory methods for convenience.

        Raises
        ------
        Exception
            Any unhandled exception is caught by :meth:`run` and converted
            to a failure ``AgentResult``; the workflow engine is never crashed.
        """
        ...  # pragma: no cover

    # =========================================================================
    # Hook methods - override in child agents as needed
    # =========================================================================

    async def initialize(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,  # noqa: ARG002
    ) -> None:
        """
        Agent-level setup executed once before any processing begins.

        Override to perform one-time initialisation that should not be in
        ``__init__`` because it requires the live ``state`` or ``context``
        (e.g. loading customer-specific configuration, opening a DB cursor).

        The default implementation is a no-op.
        """

    async def validate_input(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,  # noqa: ARG002
    ) -> None:
        """
        Validate that ``state`` contains the inputs this agent requires.

        Override to check for mandatory fields before :meth:`execute` is
        called.  Raise ``ValueError`` (or any exception) to abort the run;
        the error is caught by :meth:`run` and produces a failure result.

        Prefer lightweight checks here; delegate heavier cross-model
        validation to :class:`~backend.orchestrator.state_validator.StateValidator`.

        The default implementation is a no-op.
        """

    async def before_execute(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,  # noqa: ARG002
    ) -> None:
        """
        Pre-execution hook for side-effects that must run before ``execute``.

        Examples: starting a span in a distributed tracer, acquiring a lock,
        emitting a "started" event to a message bus.

        The default implementation is a no-op.
        """

    async def after_execute(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,  # noqa: ARG002
    ) -> None:
        """
        Post-execution hook for side-effects that run after successful ``execute``.

        Examples: emitting a "completed" event, updating a secondary index,
        invalidating a downstream cache.

        This hook is **not** called when ``execute`` raises an exception;
        use :meth:`cleanup` for unconditional teardown.

        The default implementation is a no-op.
        """

    async def validate_output(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,  # noqa: ARG002
    ) -> None:
        """
        Verify that this agent has written expected data to ``state``.

        Override to assert post-conditions on ``state`` after a successful
        ``execute`` call.  Raise an exception to flag a broken contract;
        the error is caught and produces a failure result.

        Prefer lightweight checks here; delegate heavy validation to
        :class:`~backend.orchestrator.state_validator.StateValidator`.

        The default implementation is a no-op.
        """

    async def cleanup(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,  # noqa: ARG002
    ) -> None:
        """
        Unconditional teardown, always executed after ``run()`` completes.

        Called even when ``execute`` or a preceding hook raises an exception.
        Use this to release resources (file handles, DB connections, locks)
        regardless of outcome.

        Exceptions raised here are caught and logged by :meth:`run`;
        they do not replace or override the primary result.

        The default implementation is a no-op.
        """

    async def handle_error(
        self,
        exc: Exception,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,  # noqa: ARG002
    ) -> AgentResult | None:
        """
        Optional custom error handler invoked when ``execute`` or a hook fails.

        Override to implement agent-specific recovery logic:
        - Attempt a fallback strategy and return a (possibly partial) success.
        - Enrich the failure ``AgentResult`` with domain-specific context.
        - Re-raise a different exception type (it will be caught again by
          :meth:`run` and converted to a failure result).

        Parameters
        ----------
        exc:
            The exception that triggered the error path.
        state:
            Current workflow state at the time of failure.
        context:
            Immutable runtime context.

        Returns
        -------
        AgentResult | None
            * Return a fully-constructed ``AgentResult`` to override the
              default failure result.
            * Return ``None`` to let :meth:`run` build the default failure
              result from ``exc``.

        The default implementation returns ``None`` (use default failure result).
        """
        return None

    # =========================================================================
    # Lifecycle event hooks - override for observability integrations
    # =========================================================================

    async def on_start(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,
    ) -> None:
        """
        Observability event fired immediately when ``run()`` begins.

        WHY THIS EXISTS
        ~~~~~~~~~~~~~~~
        Separating "the agent started" from ``initialize()`` allows
        external monitoring systems (APM agents, metrics collectors,
        event buses) to receive a start signal **before** any agent code
        runs - including code that might fail during ``initialize()``.

        Override to:
        * Start a distributed trace span.
        * Emit a "agent_started" metric to your observability platform.
        * Publish a start event to a message bus (e.g. Pub/Sub, Kafka).
        * Increment a Prometheus counter.

        The default implementation logs at DEBUG level.

        Exceptions raised here are caught by :meth:`_fire_event` and
        logged; they do not abort the lifecycle.
        """
        self._logger.debug(
            "[%s] EVENT on_start | request_id=%s",
            self.agent_name,
            context.request_id,
        )

    async def on_success(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,
    ) -> None:
        """
        Observability event fired after the agent completes successfully.

        WHY THIS EXISTS
        ~~~~~~~~~~~~~~~
        Separating "success notification" from ``after_execute()`` keeps
        domain side-effects (e.g. invalidating a cache) separate from
        observability concerns (e.g. recording a success metric).
        ``after_execute()`` is the correct place for domain side-effects;
        ``on_success()`` is the correct place for monitoring.

        Override to:
        * Record a success metric / histogram.
        * End a distributed trace span with a success status.
        * Publish a "agent_completed" event.

        The default implementation logs at DEBUG level.

        Exceptions raised here are caught by :meth:`_fire_event` and
        logged; they do not alter the already-constructed ``AgentResult``.
        """
        self._logger.debug(
            "[%s] EVENT on_success | request_id=%s",
            self.agent_name,
            context.request_id,
        )

    async def on_failure(
        self,
        state: WorkflowState,  # noqa: ARG002
        context: ExecutionContext,
    ) -> None:
        """
        Observability event fired when the agent fails for any reason.

        WHY THIS EXISTS
        ~~~~~~~~~~~~~~~
        Fired before ``cleanup()`` so failure monitors receive the signal
        immediately, rather than waiting for resource teardown to finish.
        This is important for latency-sensitive alerting pipelines.

        Override to:
        * Record a failure metric / error rate.
        * End a distributed trace span with an error status.
        * Trigger a PagerDuty / alerting integration.
        * Publish a "agent_failed" event for downstream compensating actions.

        The default implementation logs at DEBUG level.

        Exceptions raised here are caught by :meth:`_fire_event` and
        logged; they do not suppress the original failure.
        """
        self._logger.debug(
            "[%s] EVENT on_failure | request_id=%s",
            self.agent_name,
            context.request_id,
        )

    # =========================================================================
    # Protected helpers - available to child agents
    # =========================================================================

    @property
    def llm(self) -> LLMService:
        """
        Dependency-injected :class:`~backend.services.llm.LLMService`.

        The sole gateway to LLM operations for all child agents.
        Never call :func:`~backend.services.llm.create_llm_service`
        directly from a child agent.

        Returns
        -------
        LLMService
        """
        return self._llm

    @property
    def prompts(self) -> PromptManager:
        """
        Dependency-injected :class:`~backend.services.llm.prompt_manager.PromptManager`.

        Use :meth:`~backend.services.llm.prompt_manager.PromptManager.render`
        to load and render prompt templates without hard-coding prompt text
        inside agent classes.

        Returns
        -------
        PromptManager
        """
        return self._prompt_manager

    @property
    def logger(self) -> logging.Logger:
        """
        Scoped logger for this agent (``backend.agents.<agent_name>``).

        Prefer this over calling ``logging.getLogger()`` directly so all
        agent log records share a consistent hierarchy.

        Returns
        -------
        logging.Logger
        """
        return self._logger

    def _record_llm_call(self) -> None:
        """
        Increment the LLM-call counter in the current metrics snapshot.

        Call this once per ``await self.llm.*()`` invocation inside
        ``execute()`` to keep the metrics accurate.

        Example
        -------
        ::

            response = await self.llm.generate_text(raw_prompt=prompt)
            self._record_llm_call()
        """
        if self._metrics is not None:
            self._metrics.llm_calls += 1

    def _record_metric(self, key: str, value: Any) -> None:
        """
        Record an agent-specific metric in the extensible ``_extra`` store.

        Delegates to :meth:`AgentMetrics.record_extra`.  Numeric values
        for an existing key are **accumulated** (added together); all other
        types are overwritten.

        Use this instead of modifying ``AgentMetrics`` directly so that
        future changes to the metrics storage layer are transparent to
        child agents.

        Parameters
        ----------
        key:
            Metric name (e.g. ``"tokens_used"``,
            ``"kb_articles_fetched"``, ``"crm_records_read"``).
        value:
            Metric value - any JSON-serialisable type.

        Example
        -------
        ::

            articles = await self._fetch_kb_articles(query)
            self._record_metric("kb_articles_fetched", len(articles))
        """
        if self._metrics is not None:
            self._metrics.record_extra(key, value)

    def _add_warning(self, message: str) -> None:
        """
        Append a non-blocking diagnostic warning to the current metrics.

        Warnings are propagated into ``AgentResult.warnings`` so the
        workflow engine and operators can inspect them without failing the
        run.

        Parameters
        ----------
        message:
            Human-readable warning description.
        """
        if self._metrics is not None:
            self._metrics.warnings.append(message)
        self._logger.warning("[%s] Warning: %s", self.agent_name, message)

    def _build_failure_result(
        self,
        errors: list[str],
        elapsed_ms: float,
        *,
        warnings: list[str] | None = None,
        partial_output: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        Construct a canonical failure :class:`AgentResult`.

        Merges any accumulated metric warnings with caller-supplied
        ``warnings`` and attaches the ``_metrics`` payload.

        Parameters
        ----------
        errors:
            One or more error descriptions (required by ``AgentResult``
            when ``success=False``).
        elapsed_ms:
            Wall-clock time at point of failure in milliseconds.
        warnings:
            Additional non-blocking warnings to include.
        partial_output:
            Any partial data the agent produced before the failure.

        Returns
        -------
        AgentResult
            Failure result with ``success=False``.
        """
        all_warnings: list[str] = list(warnings or [])
        if self._metrics:
            all_warnings.extend(self._metrics.warnings)

        output: dict[str, Any] = dict(partial_output or {})
        if self._metrics:
            output["_metrics"] = self._metrics.to_dict()

        return AgentResult.failure_result(
            agent_name=self.agent_name,
            execution_time_ms=round(elapsed_ms, 2),
            errors=errors,
            warnings=all_warnings,
            output_data=output,
        )

    # =========================================================================
    # Private internals - not part of the child-agent API
    # =========================================================================

    async def _run_hook(
        self,
        hook_name: str,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> None:
        """
        Invoke a named hook method and log its execution at debug level.

        Hooks are resolved by name via ``getattr`` so the call site in
        :meth:`run` remains clean and uniform.

        Parameters
        ----------
        hook_name:
            Name of the hook method (e.g. ``"initialize"``).
        state:
            Current workflow state.
        context:
            Current execution context.

        Raises
        ------
        Exception
            Propagates any exception raised by the hook so :meth:`run`'s
            top-level handler can process it uniformly.
        """
        hook = getattr(self, hook_name)
        self._logger.debug("[%s] Entering hook: %s()", self.agent_name, hook_name)
        await hook(state, context)
        self._logger.debug("[%s] Exited hook: %s()", self.agent_name, hook_name)

    async def _fire_event(
        self,
        event_name: str,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> None:
        """
        Invoke a lifecycle event hook, swallowing any exception it raises.

        Unlike :meth:`_run_hook`, event hooks are **non-fatal** - an
        exception inside ``on_start``, ``on_success``, or ``on_failure``
        must never abort the primary lifecycle or alter the ``AgentResult``.
        Failures are logged at ERROR level so operators can investigate
        broken monitoring integrations without impacting the workflow.

        Parameters
        ----------
        event_name:
            Name of the event method (``"on_start"``, ``"on_success"``,
            or ``"on_failure"``).
        state:
            Current workflow state (passed to the event hook).
        context:
            Current execution context (passed to the event hook).
        """
        try:
            event_fn = getattr(self, event_name)
            await event_fn(state, context)
        except Exception as exc:  # noqa: BLE001
            # Event hook failures are never fatal; log and continue.
            self._logger.error(
                "[%s] Lifecycle event '%s' raised an exception (non-fatal): %s",
                self.agent_name,
                event_name,
                exc,
                exc_info=True,
            )

    async def _run_precondition_validation(
        self,
        state: WorkflowState,
    ) -> None:
        """
        Run :class:`StateValidator` pre-condition checks for this agent.

        Called automatically inside :meth:`run` after ``validate_input``
        and before ``before_execute``.  Child agents do not need to call
        this explicitly.

        Behaviour
        ---------
        * If no pre-conditions are registered for this agent's
          ``agent_name``, the check is silently skipped (non-fatal).
        * Validation **warnings** are appended to the running metrics and
          surfaced in ``AgentResult.warnings`` - the run continues.
        * Validation **errors** raise ``StateValidationError``, which
          propagates to :meth:`run`'s top-level handler and produces a
          failure ``AgentResult``.

        Parameters
        ----------
        state:
            Current workflow state to validate.
        """
        report = self._state_validator.check_preconditions(state, self.agent_name)
        # Surface validation warnings without aborting the run.
        for issue in report.warnings:
            self._add_warning(f"[pre-condition] {issue.code}: {issue.message}")
        # Raise on errors - this propagates to run()'s exception handler.
        report.raise_if_invalid()

    async def _run_postcondition_validation(
        self,
        state: WorkflowState,
    ) -> None:
        """
        Run :class:`StateValidator` post-condition checks for this agent.

        Called automatically inside :meth:`run` after ``validate_output``.
        Child agents do not need to call this explicitly.

        Behaviour
        ---------
        * If no post-conditions are registered for this agent, the check
          is silently skipped.
        * Warnings are surfaced in ``AgentResult.warnings``.
        * Errors raise ``StateValidationError`` and produce a failure result.

        Parameters
        ----------
        state:
            Workflow state after ``execute()`` has run.
        """
        report = self._state_validator.check_postconditions(state, self.agent_name)
        for issue in report.warnings:
            self._add_warning(f"[post-condition] {issue.code}: {issue.message}")
        report.raise_if_invalid()

    def _enrich_result(
        self,
        raw_result: AgentResult,
        elapsed_ms: float,
    ) -> AgentResult:
        """
        Rebuild ``raw_result`` with the authoritative ``execution_time_ms``
        and append ``_metrics`` to ``output_data``.

        Because :class:`AgentResult` is frozen (``model_config={"frozen": True}``),
        a new instance is constructed via :meth:`~pydantic.BaseModel.model_copy`.

        Parameters
        ----------
        raw_result:
            The ``AgentResult`` returned by :meth:`execute`.
        elapsed_ms:
            Authoritative wall-clock time measured by :meth:`run`.

        Returns
        -------
        AgentResult
            A new, enriched result instance.
        """
        # Merge child-agent warnings with any accumulated metric warnings.
        all_warnings = list(raw_result.warnings)
        if self._metrics:
            # Avoid duplicating warnings that the child agent already added.
            for w in self._metrics.warnings:
                if w not in all_warnings:
                    all_warnings.append(w)

        # Attach execution metrics as a private key in output_data.
        enriched_output = dict(raw_result.output_data)
        if self._metrics:
            enriched_output["_metrics"] = self._metrics.to_dict()

        return raw_result.model_copy(
            update={
                "execution_time_ms": round(elapsed_ms, 2),
                "warnings": all_warnings,
                "output_data": enriched_output,
            }
        )

    async def _handle_error_internal(
        self,
        exc: Exception,
        state: WorkflowState,
        context: ExecutionContext,
        elapsed_ms: float,
    ) -> AgentResult:
        """
        Centralised error handler invoked by :meth:`run` on any exception.

        Execution order:
        1. Log the exception with full traceback at ERROR level.
        2. Delegate to :meth:`handle_error` (child-agent override).
        3. If ``handle_error`` returns an ``AgentResult``, use it.
        4. Otherwise, build a default failure result.

        LLM-specific errors (:class:`~backend.services.llm.exceptions.LLMBaseError`)
        are logged with extra provider context to aid infrastructure debugging.

        Parameters
        ----------
        exc:
            The exception that triggered the error path.
        state:
            Current workflow state (may be partially mutated).
        context:
            Immutable runtime context.
        elapsed_ms:
            Wall-clock time at point of failure.

        Returns
        -------
        AgentResult
            Always a failure result (``success=False``).
        """
        exc_type = type(exc).__name__

        # -- Structured failure log --------------------------------------------
        if isinstance(exc, LLMBaseError):
            # LLM-layer errors carry provider-specific context.
            self._logger.error(
                "[%s] LLM error during execution | type=%s message=%s details=%s "
                "request_id=%s elapsed_ms=%.1f",
                self.agent_name,
                exc_type,
                exc.message,
                exc.details,
                context.request_id,
                elapsed_ms,
                exc_info=False,  # details already logged above
            )
        else:
            self._logger.error(
                "[%s] Unexpected exception during execution | type=%s "
                "request_id=%s elapsed_ms=%.1f\n%s",
                self.agent_name,
                exc_type,
                context.request_id,
                elapsed_ms,
                traceback.format_exc(),
            )

        # -- Delegate to child-agent error handler -----------------------------
        custom_result: AgentResult | None = None
        try:
            custom_result = await self.handle_error(exc, state, context)
        except Exception as handler_exc:  # noqa: BLE001
            # The error handler itself failed; log and fall through to default.
            self._logger.error(
                "[%s] handle_error() raised a secondary exception: %s",
                self.agent_name,
                handler_exc,
                exc_info=True,
            )

        if custom_result is not None:
            # Child agent provided a custom result; annotate with metrics.
            return self._enrich_result(custom_result, elapsed_ms)

        # -- Build default failure AgentResult ---------------------------------
        primary_error = f"{exc_type}: {exc}"
        return self._build_failure_result(
            errors=[primary_error],
            elapsed_ms=elapsed_ms,
        )

    # =========================================================================
    # Dunder helpers
    # =========================================================================

    def __repr__(self) -> str:  # noqa: D105
        llm_provider = getattr(
            getattr(self._llm, "_pipeline", None),
            "_client",
            None,
        )
        provider_label = (
            getattr(llm_provider, "provider_name", "unknown")
            if llm_provider
            else "unknown"
        )
        return (
            f"{type(self).__name__}("
            f"agent_name={self.agent_name!r} "
            f"provider={provider_label!r})"
        )
