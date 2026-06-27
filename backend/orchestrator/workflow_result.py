# -*- coding: utf-8 -*-
"""
backend/orchestrator/workflow_result.py
=======================================
WorkflowResult contains the final execution status, metrics, and any errors/warnings 
emitted by the Planner orchestration layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from pydantic._internal._model_construction import ModelMetaclass

from backend.orchestrator.workflow_state import WorkflowState


class WorkflowResultMetrics(BaseModel):
    """
    Workflow-level metrics captured during orchestrator execution.
    """
    model_config = ConfigDict(frozen=True)

    total_execution_time_ms: float = Field(
        default=0.0,
        description="Total duration of the workflow execution run."
    )
    agents_executed: List[str] = Field(
        default_factory=list,
        description="Names of agents successfully executed."
    )
    agents_skipped: List[str] = Field(
        default_factory=list,
        description="Names of agents skipped due to failed dependencies."
    )
    agents_failed: List[str] = Field(
        default_factory=list,
        description="Names of agents that failed execution."
    )
    execution_order: List[str] = Field(
        default_factory=list,
        description="Sequential list of agent executions (including skips/failures)."
    )
    retry_count: int = Field(
        default=0,
        description="Total retries attempted across all agents."
    )
    parallel_stages_count: int = Field(
        default=0,
        description="Number of parallelizable stages designed in the execution plan."
    )


class WorkflowResultMetaclass(ModelMetaclass):
    """
    Custom metaclass to allow defining a classmethod named 'success' 
    on a Pydantic model that also has a field named 'success'.
    """
    def __new__(mcs, name, bases, namespace, **kwargs):
        success_func = namespace.get("success")
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        if success_func:
            setattr(cls, "success", success_func)
        return cls


class WorkflowResult(BaseModel, metaclass=WorkflowResultMetaclass):
    """
    Uniform immutable response object returned by the Planner.
    """
    model_config = ConfigDict(frozen=True)

    success: bool = Field(
        description="Whether the entire workflow finished successfully without any unhandled failures."
    )
    execution_time_ms: float = Field(
        default=0.0,
        description="Total duration of the workflow execution run."
    )
    completed_agents: List[str] = Field(
        default_factory=list,
        description="List of agent names that completed successfully."
    )
    failed_agents: List[str] = Field(
        default_factory=list,
        description="List of agent names that failed during execution."
    )
    skipped_agents: List[str] = Field(
        default_factory=list,
        description="List of agent names skipped due to cascading failures."
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-blocking warning messages surfaced during validation or hooks."
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Blocking error messages encountered during validation or execution."
    )
    metrics: WorkflowResultMetrics = Field(
        default_factory=WorkflowResultMetrics,
        description="Detailed orchestration and execution metrics."
    )
    final_state: Optional[WorkflowState] = Field(
        default=None,
        description="Final modified snapshot of the shared WorkflowState."
    )
    execution_summary: str = Field(
        default="",
        description="Human-readable text summary of the execution run."
    )

    @classmethod
    def success(
        cls,
        execution_time_ms: float,
        completed_agents: List[str],
        final_state: WorkflowState,
        warnings: Optional[List[str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        execution_summary: str = "Workflow completed successfully."
    ) -> WorkflowResult:
        """Helper constructor for a fully successful workflow result."""
        result_metrics = WorkflowResultMetrics(
            total_execution_time_ms=execution_time_ms,
            agents_executed=completed_agents,
            execution_order=completed_agents,
            retry_count=metrics.get("retry_count", 0) if metrics else 0,
            parallel_stages_count=metrics.get("parallel_stages_count", 0) if metrics else 0
        )
        return cls(
            success=True,
            execution_time_ms=execution_time_ms,
            completed_agents=completed_agents,
            failed_agents=[],
            skipped_agents=[],
            warnings=warnings or [],
            errors=[],
            metrics=result_metrics,
            final_state=final_state,
            execution_summary=execution_summary
        )

    @classmethod
    def failure(
        cls,
        errors: List[str],
        warnings: Optional[List[str]] = None,
        final_state: Optional[WorkflowState] = None,
        execution_time_ms: float = 0.0,
        completed_agents: Optional[List[str]] = None,
        failed_agents: Optional[List[str]] = None,
        skipped_agents: Optional[List[str]] = None,
        execution_order: Optional[List[str]] = None,
        retry_count: int = 0,
        metrics: Optional[Dict[str, Any]] = None,
        execution_summary: str = "Workflow execution failed."
    ) -> WorkflowResult:
        """Helper constructor for a failed workflow result preserving diagnostic execution data."""
        # Prioritize values from the passed metrics dictionary if available
        final_completed = completed_agents or (metrics.get("completed_agents") if metrics else None) or []
        final_failed = failed_agents or (metrics.get("failed_agents") if metrics else None) or []
        final_skipped = skipped_agents or (metrics.get("skipped_agents") if metrics else None) or []
        final_order = execution_order or (metrics.get("execution_order") if metrics else None) or (final_completed + final_failed + final_skipped)
        final_retries = retry_count or (metrics.get("retry_count") if metrics else 0)

        result_metrics = WorkflowResultMetrics(
            total_execution_time_ms=execution_time_ms,
            agents_executed=final_completed,
            agents_failed=final_failed,
            agents_skipped=final_skipped,
            execution_order=final_order,
            retry_count=final_retries,
            parallel_stages_count=metrics.get("parallel_stages_count", 0) if metrics else 0
        )
        return cls(
            success=False,
            execution_time_ms=execution_time_ms,
            completed_agents=final_completed,
            failed_agents=final_failed,
            skipped_agents=final_skipped,
            warnings=warnings or [],
            errors=errors,
            metrics=result_metrics,
            final_state=final_state,
            execution_summary=execution_summary
        )

    @classmethod
    def partial_success(
        cls,
        execution_time_ms: float,
        completed_agents: List[str],
        failed_agents: List[str],
        skipped_agents: List[str],
        final_state: WorkflowState,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        execution_summary: str = "Workflow finished with partial success."
    ) -> WorkflowResult:
        """Helper constructor for a partially successful workflow result."""
        result_metrics = WorkflowResultMetrics(
            total_execution_time_ms=execution_time_ms,
            agents_executed=completed_agents,
            agents_failed=failed_agents,
            agents_skipped=skipped_agents,
            execution_order=metrics.get("execution_order") or (completed_agents + failed_agents + skipped_agents),
            retry_count=metrics.get("retry_count", 0) if metrics else 0,
            parallel_stages_count=metrics.get("parallel_stages_count", 0) if metrics else 0
        )
        return cls(
            success=False,
            execution_time_ms=execution_time_ms,
            completed_agents=completed_agents,
            failed_agents=failed_agents,
            skipped_agents=skipped_agents,
            warnings=warnings or [],
            errors=errors or [],
            metrics=result_metrics,
            final_state=final_state,
            execution_summary=execution_summary
        )
