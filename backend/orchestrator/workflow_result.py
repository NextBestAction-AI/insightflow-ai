"""
backend/orchestrator/workflow_result.py
=======================================
WorkflowResult contains the final execution status, metrics, and any errors/warnings 
emitted by the Planner orchestration layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowResultMetrics(BaseModel):
    """
    Workflow-level metrics captured during orchestrator execution.
    """
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


class WorkflowResult(BaseModel):
    """
    Uniform response object returned by the Planner.
    """
    success: bool = Field(
        description="Whether the entire workflow finished successfully without any unhandled failures."
    )
    metrics: WorkflowResultMetrics = Field(
        default_factory=WorkflowResultMetrics,
        description="Workflow execution metrics bookkeeping."
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Descriptions of any blocking errors encountered during validation or execution."
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-blocking warning messages surfaced by StateValidator or execution hooks."
    )

    @classmethod
    def failure(cls, errors: List[str], warnings: List[str] | None = None) -> WorkflowResult:
        """
        Convenience factory to build a failure result.
        """
        return cls(
            success=False,
            metrics=WorkflowResultMetrics(),
            errors=errors,
            warnings=warnings or []
        )
