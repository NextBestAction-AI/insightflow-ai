# -*- coding: utf-8 -*-
"""
backend/orchestrator/planner.py
===============================
Planner is the core orchestration facade of the InsightFlow AI platform.

Planner coordinates workflow validation, dependency resolution, execution planning,
and execution scheduling via WorkflowExecutor.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Type
from datetime import datetime

from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent
from backend.orchestrator.agent_registry import AgentRegistry
from backend.orchestrator.dependency_resolver import DependencyResolver
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.execution_planner import ExecutionPlanner, ExecutionPlan, SchedulingPolicy
from backend.orchestrator.state_validator import StateValidator, ValidationReport
from backend.orchestrator.workflow_executor import WorkflowExecutor
from backend.orchestrator.workflow_result import WorkflowResult
from backend.orchestrator.workflow_state import WorkflowState
from backend.orchestrator.workflow_status import WorkflowStatus

logger = logging.getLogger(__name__)

# =============================================================================
# Section 1: Configuration Models
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
        state_validator: Optional[Any] = None,
        registry: Optional[AgentRegistry] = None
    ) -> None:
        self._config = config or PlannerConfiguration()
        
        # Initialize registry and populate initial agent_classes if provided
        if registry:
            self._registry = registry
        else:
            self._registry = AgentRegistry()
            if agent_classes:
                try:
                    self._registry.register_many(agent_classes)
                except Exception as exc:
                    logger.warning("Agent registration warning during initialization: %s", exc)

        self._validator = validator or WorkflowValidator(state_validator=state_validator)
        self._resolver = resolver or DependencyResolver()
        self._planner = planner or ExecutionPlanner()
        self._executor = executor or WorkflowExecutor(
            self._registry,
            max_retries=self._config.max_retries,
            continue_on_failure=self._config.continue_on_failure,
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
        logger.info("Workflow Started")

        # 1. Validation
        validation_report = self._validator.validate(state)
        if not validation_report.is_valid:
            logger.error("Pre-execution structural integrity validation failed.")
            errors = [str(i) for i in validation_report.errors]
            warnings = [str(i) for i in validation_report.warnings]
            
            # Transition state to FAILED
            state.execution.finalise(WorkflowStatus.FAILED)
            return WorkflowResult.failure(errors=errors, warnings=warnings, final_state=state)

        logger.info("Workflow Validated")

        # 2. Dependency Resolution
        try:
            graph = self._resolver.resolve(self._registry)
            logger.info("Dependency Graph Resolved")
        except Exception as exc:
            logger.error("Failed during dependency resolution phase: %s", exc)
            state.execution.finalise(WorkflowStatus.FAILED)
            return WorkflowResult.failure(errors=[f"Dependency resolution failure: {exc}"], final_state=state)

        # 3. Execution Planning
        try:
            plan = self._planner.plan(graph)
            logger.info("Execution Plan Created")
        except Exception as exc:
            logger.error("Failed during execution planning phase: %s", exc)
            state.execution.finalise(WorkflowStatus.FAILED)
            return WorkflowResult.failure(errors=[f"Execution planning failure: {exc}"], final_state=state)

        # 4. Execution
        try:
            logger.info("Workflow Execution Started")
            result = await self._executor.execute(state, context, plan, graph)
            logger.info("Workflow Completed")
            return result
        except Exception as exc:
            logger.exception("Unexpected execution exception: %s", exc)
            state.execution.finalise(WorkflowStatus.FAILED)
            return WorkflowResult.failure(errors=[f"Runtime orchestrator error: {exc}"], final_state=state)


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
