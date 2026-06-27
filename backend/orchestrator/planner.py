"""
backend/orchestrator/planner.py
===============================
Planner is the core orchestration engine of the InsightFlow AI platform.

Planner is NOT an AI agent; it never communicates with LLMs or performs business analysis.
Its single responsibility is to validate the state, build the dependency DAG, plan the stages, 
and execute the registered agents using composable helper components.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Type

from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent
from backend.agents.crm_agent import CRMAgent
from backend.agents.health_agent import HealthAgent
from backend.agents.interaction_agent import InteractionAgent
from backend.agents.knowledge_agent import KnowledgeAgent
from backend.agents.reasoning_agent import ReasoningAgent
from backend.agents.recommendation_agent import RecommendationAgent
from backend.agents.risk_agent import RiskAgent
from backend.orchestrator.agent_result import AgentResult
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.state_validator import StateValidator, ValidationReport
from backend.orchestrator.workflow_result import WorkflowResult, WorkflowResultMetrics
from backend.orchestrator.workflow_state import WorkflowState
from backend.orchestrator.workflow_status import WorkflowStatus

logger = logging.getLogger(__name__)

# =============================================================================
# Section 1: Configuration & Plan Models
# =============================================================================

class PlannerConfiguration(BaseModel):
    """
    Orchestration parameters configuration.
    """
    parallel_execution: bool = Field(default=False, description="Enable parallel step execution in the future.")
    max_retries: int = Field(default=3, description="Maximum execution retries for each agent.")
    continue_on_failure: bool = Field(default=False, description="Whether to continue execution on independent branches after failure.")
    stop_on_validation_error: bool = Field(default=True, description="Abort execution if state structural integrity fails.")
    emit_execution_events: bool = Field(default=True, description="Log high-level execution step events.")


class ExecutionStage(BaseModel):
    """
    A single stage of execution in the workflow plan.
    """
    stage_number: int = Field(description="Sequential stage index.")
    agents: List[str] = Field(default_factory=list, description="Names of agents executing in this stage.")
    parallel: bool = Field(default=False, description="Whether agents in this stage can execute concurrently.")
    dependencies: List[int] = Field(default_factory=list, description="Stage numbers this stage depends on.")


class ExecutionPlan(BaseModel):
    """
    The full scheduled DAG execution plan.
    """
    stages: List[ExecutionStage] = Field(default_factory=list, description="Ordered stages of execution.")


# =============================================================================
# Section 2: Helper Components
# =============================================================================

class WorkflowValidator:
    """
    Validates workflow state integrity before execution begins.
    """
    def __init__(self, state_validator: Optional[StateValidator] = None) -> None:
        self._state_validator = state_validator or StateValidator()

    def validate(self, state: WorkflowState) -> ValidationReport:
        """
        Runs pre-execution structural checks on the shared state.
        """
        return self._state_validator.check_structural_integrity(state)


class DependencyResolver:
    """
    Resolves agent-level dependencies dynamically using class metadata.
    """
    def resolve_dependencies(
        self, 
        state: WorkflowState, 
        agent_classes: List[Type[BaseAgent]]
    ) -> Dict[str, Set[str]]:
        """
        Builds a dependency map based on produced outputs and required inputs.
        """
        # Map output paths to the producing agent's name
        output_producer: Dict[str, str] = {}
        for agent in agent_classes:
            meta = agent.get_agent_metadata()
            for out in meta.get("produced_outputs", []):
                if out in output_producer:
                    raise ValueError(
                        f"Duplicate output producer detected: '{out}' is produced by both "
                        f"'{output_producer[out]}' and '{agent.agent_name}'."
                    )
                output_producer[out] = agent.agent_name

        # Helper to check if a dotted state path is populated
        def is_path_populated(path: str) -> bool:
            parts = path.split('.')
            obj = state
            for part in parts:
                if not hasattr(obj, part):
                    return False
                obj = getattr(obj, part)
            if obj is None:
                return False
            if isinstance(obj, (list, dict, set)) and len(obj) == 0:
                return False
            if isinstance(obj, str) and not obj.strip():
                return False
            return True

        # Build dependencies mapping: agent_name -> set of dependent agent names
        dependencies: Dict[str, Set[str]] = {}
        for agent in agent_classes:
            name = agent.agent_name
            meta = agent.get_agent_metadata()
            req_inputs = meta.get("required_inputs", [])
            deps: Set[str] = set()

            # Rule: InteractionAgent requires at least one of its inputs.
            # Other agents require all of their inputs.
            if name == "InteractionAgent":
                satisfied = False
                for inp in req_inputs:
                    if inp in output_producer:
                        deps.add(output_producer[inp])
                        satisfied = True
                    elif is_path_populated(inp):
                        satisfied = True
                if not satisfied:
                    raise ValueError(
                        f"Unsatisfied required inputs for '{name}': none of {req_inputs} "
                        f"are present in the initial state or produced by registered agents."
                    )
            else:
                for inp in req_inputs:
                    if inp in output_producer:
                        deps.add(output_producer[inp])
                    elif not is_path_populated(inp):
                        raise ValueError(
                            f"Unsatisfied required input '{inp}' for agent '{name}' is not "
                            f"present in the initial state or produced by registered agents."
                        )
            dependencies[name] = deps

        return dependencies


class ExecutionPlanner:
    """
    Groups dependencies level-by-level into an ExecutionPlan.
    """
    def build_plan(
        self, 
        agent_classes: List[Type[BaseAgent]], 
        dependencies: Dict[str, Set[str]]
    ) -> ExecutionPlan:
        """
        Creates prioritized stages for the pipeline.
        """
        remaining = list(agent_classes)
        stages: List[ExecutionStage] = []
        stage_num = 1
        completed: Set[str] = set()

        while remaining:
            # Gather all agents whose dependencies are met
            stage_agents = []
            for agent in list(remaining):
                deps = dependencies.get(agent.agent_name, set())
                if deps.issubset(completed):
                    stage_agents.append(agent)

            if not stage_agents:
                raise ValueError("Cyclic dependency detected in agent execution graph.")

            # Remove sorted agents from the list
            for agent in stage_agents:
                remaining.remove(agent)
                completed.add(agent.agent_name)

            # Sort agents within the stage by priority descending
            stage_agents.sort(key=lambda x: x.priority, reverse=True)

            # Identify stage-to-stage dependencies
            stage_deps = []
            for prior_idx, prior_stage in enumerate(stages):
                has_dep = any(
                    dep in prior_stage.agents 
                    for agent in stage_agents 
                    for dep in dependencies.get(agent.agent_name, set())
                )
                if has_dep:
                    stage_deps.append(prior_stage.stage_number)

            stages.append(ExecutionStage(
                stage_number=stage_num,
                agents=[a.agent_name for a in stage_agents],
                parallel=len(stage_agents) > 1,
                dependencies=stage_deps
            ))
            stage_num += 1

        return ExecutionPlan(stages=stages)


class WorkflowExecutor:
    """
    Executes stages of agents, handling state updates, retries, and failures.
    """
    def __init__(
        self, 
        config: PlannerConfiguration, 
        agent_classes: List[Type[BaseAgent]],
        llm_service: Optional[Any] = None,
        prompt_manager: Optional[Any] = None,
        state_validator: Optional[Any] = None
    ) -> None:
        self._config = config
        self._agent_map = {a.agent_name: a for a in agent_classes}
        self._llm_service = llm_service
        self._prompt_manager = prompt_manager
        self._state_validator = state_validator

    async def execute(
        self, 
        state: WorkflowState, 
        context: ExecutionContext, 
        plan: ExecutionPlan,
        dependencies: Dict[str, Set[str]]
    ) -> WorkflowResultMetrics:
        """
        Runs each stage and executes agents sequentially.
        """
        metrics = WorkflowResultMetrics(parallel_stages_count=sum(1 for s in plan.stages if s.parallel))
        total_retries = 0
        execution_start = time.monotonic()

        # Mark workflow run as active
        if state.execution.started_at is None:
            state.execution.started_at = datetime.now(tz=timezone.utc)
            state.execution.execution_status = WorkflowStatus.RUNNING

        for stage in plan.stages:
            if self._config.emit_execution_events:
                logger.info("[Planner] Executing Stage %d (agents=%s)", stage.stage_number, stage.agents)

            for agent_name in stage.agents:
                metrics.execution_order.append(agent_name)

                # Skip check: Skip if any dependencies failed or were skipped
                skipped_dep = any(
                    dep in state.execution.failed_agents or dep in state.execution.skipped_agents
                    for dep in dependencies.get(agent_name, set())
                )

                if skipped_dep:
                    state.execution.mark_agent_skipped(agent_name, "Dependency failed or skipped.")
                    metrics.agents_skipped.append(agent_name)
                    continue

                agent_class = self._agent_map[agent_name]
                # Instantiate agent with injected dependencies
                agent_instance = agent_class(
                    llm_service=self._llm_service,
                    prompt_manager=self._prompt_manager,
                    state_validator=self._state_validator
                )

                # Execution with retries
                retry_count = 0
                success = False
                result: Optional[AgentResult] = None

                while retry_count <= self._config.max_retries:
                    agent_ctx = ExecutionContext(
                        request_id=context.request_id,
                        execution_mode=context.execution_mode,
                        retry_count=retry_count,
                        max_retries=self._config.max_retries
                    )
                    
                    state.execution.set_current_agent(agent_name)
                    result = await agent_instance.run(state, agent_ctx)

                    if result.success:
                        success = True
                        break
                    else:
                        retry_count += 1
                        total_retries += 1

                if success and result:
                    state.execution.mark_agent_completed(agent_name, result.execution_time_ms)
                    metrics.agents_executed.append(agent_name)
                else:
                    err_msg = result.errors[0] if result and result.errors else "Unknown failure"
                    state.execution.mark_agent_failed(agent_name, err_msg, result.execution_time_ms if result else 0.0)
                    metrics.agents_failed.append(agent_name)

                    if not self._config.continue_on_failure:
                        if self._config.emit_execution_events:
                            logger.error("[Planner] Halting execution due to failed agent '%s'", agent_name)
                        break

            # If halted due to continue_on_failure logic
            if metrics.agents_failed and not self._config.continue_on_failure:
                break

        # Mark any remaining unexecuted/unskipped agents as skipped
        all_executed_or_skipped = set(metrics.agents_executed + metrics.agents_failed + metrics.agents_skipped)
        for stage in plan.stages:
            for agent_name in stage.agents:
                if agent_name not in all_executed_or_skipped:
                    state.execution.mark_agent_skipped(agent_name, "Halted early due to preceding failure.")
                    metrics.agents_skipped.append(agent_name)
                    metrics.execution_order.append(agent_name)

        # Finalize workflow state
        final_status = WorkflowStatus.COMPLETED if not metrics.agents_failed else WorkflowStatus.FAILED
        state.execution.finalise(final_status)

        metrics.total_execution_time_ms = round((time.monotonic() - execution_start) * 1000.0, 2)
        metrics.retry_count = total_retries
        return metrics


# =============================================================================
# Section 3: The Planner
# =============================================================================

class Planner:
    """
    Orchestrator Facade class responsible for coordinating workflow validation, 
    dependency resolution, planning, and execution.
    """
    def __init__(
        self,
        config: Optional[PlannerConfiguration] = None,
        validator: Optional[WorkflowValidator] = None,
        resolver: Optional[DependencyResolver] = None,
        planner: Optional[ExecutionPlanner] = None,
        executor: Optional[WorkflowExecutor] = None,
        agent_classes: Optional[List[Type[BaseAgent]]] = None,
        llm_service: Optional[Any] = None,
        prompt_manager: Optional[Any] = None,
        state_validator: Optional[Any] = None
    ) -> None:
        self._config = config or PlannerConfiguration()
        self._validator = validator or WorkflowValidator(state_validator=state_validator)
        self._resolver = resolver or DependencyResolver()
        self._planner = planner or ExecutionPlanner()
        self._agent_classes = agent_classes or [
            InteractionAgent,
            KnowledgeAgent,
            CRMAgent,
            HealthAgent,
            RiskAgent,
            ReasoningAgent,
            RecommendationAgent
        ]
        self._executor = executor or WorkflowExecutor(
            self._config, 
            self._agent_classes,
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            state_validator=state_validator
        )

    async def run(
        self,
        state: WorkflowState,
        context: ExecutionContext
    ) -> WorkflowResult:
        """
        Orchestrates full state validation, dependency building, plan scheduling, 
        and agent executions.
        """
        if self._config.emit_execution_events:
            logger.info("[Planner] Workflow Started | Request ID: %s", context.request_id)

        # 1. Validation
        validation_report = self._validator.validate(state)
        if not validation_report.is_valid:
            if self._config.emit_execution_events:
                logger.error("[Planner] Pre-execution structural integrity validation failed.")
            errors = [str(i) for i in validation_report.errors]
            warnings = [str(i) for i in validation_report.warnings]
            
            # Transition state to FAILED
            state.execution.finalise(WorkflowStatus.FAILED)
            return WorkflowResult.failure(errors=errors, warnings=warnings)

        if self._config.emit_execution_events:
            logger.info("[Planner] Workflow Validated")

        # 2. Dependency Resolution & Planning
        try:
            dependencies = self._resolver.resolve_dependencies(state, self._agent_classes)
            if self._config.emit_execution_events:
                logger.info("[Planner] Dependency Graph Built")

            execution_plan = self._planner.build_plan(self._agent_classes, dependencies)
            if self._config.emit_execution_events:
                logger.info("[Planner] Execution Plan Created | Stages: %d", len(execution_plan.stages))
        except Exception as exc:
            logger.error("[Planner] Failed during scheduling phase: %s", exc)
            state.execution.finalise(WorkflowStatus.FAILED)
            return WorkflowResult.failure(errors=[f"Scheduling failure: {exc}"])

        # 3. Execution
        try:
            metrics = await self._executor.execute(state, context, execution_plan, dependencies)
            success = len(metrics.agents_failed) == 0

            if self._config.emit_execution_events:
                status_label = "Completed Successfully" if success else "Failed"
                logger.info("[Planner] Workflow %s | Executed: %d", status_label, len(metrics.agents_executed))

            return WorkflowResult(
                success=success,
                metrics=metrics,
                warnings=[str(w) for w in validation_report.warnings]
            )
        except Exception as exc:
            logger.exception("[Planner] Unexpected execution exception: %s", exc)
            state.execution.finalise(WorkflowStatus.FAILED)
            return WorkflowResult.failure(errors=[f"Runtime orchestrator error: {exc}"])


# =============================================================================
# Section 4: Backend Database Planner
# =============================================================================

from sqlalchemy.orm import Session
from sqlalchemy import select
from models.recommendation import Recommendation
from models.approval import Approval
from config.logging import get_logger
from fastapi import HTTPException

backend_logger = get_logger(__name__)


class WorkflowPlanner:
    """Backend workflow planning for recommendations and approvals."""

    @staticmethod
    def submit_recommendations_for_review(session: Session, recommendation_ids: list[int]) -> dict:
        """Submit multiple recommendations for review workflow."""
        try:
            recommendations = session.execute(
                select(Recommendation).where(Recommendation.id.in_(recommendation_ids)).where(Recommendation.status == "pending")
            ).scalars().all()

            if not recommendations:
                backend_logger.warning("No pending recommendations found for review submission")
                raise HTTPException(status_code=400, detail="No pending recommendations to submit")

            for rec in recommendations:
                rec.status = "pending"

            session.commit()
            backend_logger.info(f"Submitted {len(recommendations)} recommendations for review")

            return {
                "submitted_count": len(recommendations),
                "ids": [r.id for r in recommendations],
                "submitted_at": datetime.utcnow(),
            }
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            backend_logger.error(f"Failed to submit recommendations for review: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to submit recommendations")

    @staticmethod
    def get_pending_approvals_count(session: Session) -> dict:
        """Get count of pending approvals."""
        try:
            pending_count = session.execute(
                select(Recommendation).where(Recommendation.status == "pending")
            ).scalars().all()

            approved_count = session.execute(
                select(Recommendation).where(Recommendation.status == "approved")
            ).scalars().all()

            rejected_count = session.execute(
                select(Recommendation).where(Recommendation.status == "rejected")
            ).scalars().all()

            return {
                "pending": len(pending_count),
                "approved": len(approved_count),
                "rejected": len(rejected_count),
                "total": len(pending_count) + len(approved_count) + len(rejected_count),
            }
        except Exception as e:
            backend_logger.error(f"Failed to get approval counts: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to get approval counts")

    @staticmethod
    def bulk_update_recommendation_status(
        session: Session, recommendation_ids: list[int], new_status: str
    ) -> dict:
        """Bulk update recommendation statuses."""
        if new_status not in ["pending", "approved", "rejected", "executed"]:
            raise HTTPException(status_code=400, detail="Invalid status")

        try:
            recommendations = session.execute(
                select(Recommendation).where(Recommendation.id.in_(recommendation_ids))
            ).scalars().all()

            if not recommendations:
                backend_logger.warning(f"No recommendations found for bulk update")
                raise HTTPException(status_code=400, detail="No recommendations found")

            for rec in recommendations:
                rec.status = new_status

            session.commit()
            backend_logger.info(f"Updated {len(recommendations)} recommendations to status {new_status}")

            return {
                "updated_count": len(recommendations),
                "new_status": new_status,
                "updated_at": datetime.utcnow(),
            }
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            backend_logger.error(f"Failed to bulk update recommendations: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update recommendations")

