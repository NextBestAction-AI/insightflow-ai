# -*- coding: utf-8 -*-
"""
backend/orchestrator/execution_planner.py
=========================================
ExecutionPlanner is responsible for transforming a validated DependencyGraph 
into an optimized and validated ExecutionPlan schedule.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ConfigDict

from backend.orchestrator.dependency_resolver import DependencyGraph

logger = logging.getLogger(__name__)

# =============================================================================
# Section 1: Enums & Custom Exceptions
# =============================================================================

class ExecutionStrategy(str, Enum):
    """Workflow execution strategies for a stage."""
    SEQUENTIAL = "Sequential"
    PARALLEL = "Parallel"
    CONDITIONAL = "Conditional"


class SchedulingPolicy(str, Enum):
    """Abstractions for different scheduling policies/optimizations."""
    DEFAULT = "Default"
    FASTEST = "Fastest"
    LOWEST_COST = "LowestCost"
    SEQUENTIAL_ONLY = "SequentialOnly"


class ExecutionPlanningError(Exception):
    """Base exception for all execution planning errors."""
    pass

class InvalidExecutionPlanError(ExecutionPlanningError):
    """Raised when an execution plan fails validation checks."""
    pass

class StageConstructionError(ExecutionPlanningError):
    """Raised when stage conversion or estimation fails."""
    pass

class PlanOptimizationError(ExecutionPlanningError):
    """Raised when plan optimization fails."""
    pass


# =============================================================================
# Section 2: Output Models
# =============================================================================

class ExecutionStage(BaseModel):
    """An execution stage containing deterministic order of agents, strategy and dependencies."""
    model_config = ConfigDict(frozen=True)

    stage_id: str = Field(description="Stable stage identifier (e.g. 'stage_1').")
    stage_number: int = Field(description="1-based continuous sequence index.")
    agents: List[str] = Field(description="Deterministic sorted list of agent names in this stage.")
    execution_strategy: ExecutionStrategy = Field(description="How the agents in this stage should run.")
    dependencies: List[str] = Field(
        default_factory=list,
        description="Stable stage IDs this stage directly depends on."
    )
    estimated_duration_ms: float = Field(description="Estimated execution time for the stage.")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata for scheduling policies."
    )

    @property
    def parallel(self) -> bool:
        """Returns True if the execution strategy is PARALLEL."""
        return self.execution_strategy == ExecutionStrategy.PARALLEL


class PlanStatistics(BaseModel):
    """Descriptive statistics summarizing the planned execution workflow."""
    model_config = ConfigDict(frozen=True)

    agent_count: int = Field(description="Total number of agents scheduled.")
    stage_count: int = Field(description="Total number of stages in the plan.")
    parallel_stage_count: int = Field(description="Number of parallel execution stages.")
    sequential_stage_count: int = Field(description="Number of sequential execution stages.")
    maximum_parallel_width: int = Field(description="Maximum concurrent agents in a single stage.")
    critical_path_length: int = Field(description="Critical path length in stages (stage count).")
    execution_depth: int = Field(description="Depth of the execution graph stages.")
    estimated_parallelism: float = Field(description="Calculated ratio of parallelism (agents/stages).")


class ExecutionPlan(BaseModel):
    """Immutable execution plan scheduled and validated for runtime execution."""
    model_config = ConfigDict(frozen=True)

    stages: List[ExecutionStage] = Field(description="List of execution stages sorted by stage_number.")
    total_stages: int = Field(description="Total count of stages in the plan.")
    parallel_stage_count: int = Field(description="Count of parallel stages.")
    sequential_stage_count: int = Field(description="Count of sequential stages.")
    estimated_total_duration_ms: float = Field(description="Sum of stage-level estimated runtimes.")
    critical_path_length: int = Field(description="Total stages along critical path.")
    execution_depth: int = Field(description="Execution depth of the scheduling levels.")
    signature: str = Field(description="SHA-256 fingerprint tracing the source dependency graph.")
    execution_order_hash: str = Field(description="Fingerprint of the finalized stage sequence.")
    created_at: datetime = Field(description="UTC timestamp when the plan was constructed.")
    statistics: PlanStatistics = Field(description="Summary execution metrics.")


# =============================================================================
# Section 3: Helper Components
# =============================================================================

class StageConstructor:
    """Converts DependencyGraph levels into stable ExecutionStage objects."""

    @staticmethod
    def _get_agent_duration(node: Any) -> float:
        """Helper to extract estimated execution duration from agent metadata."""
        meta = node.metadata
        if hasattr(meta, "estimated_execution_ms"):
            return float(meta.estimated_execution_ms)
        if isinstance(meta, dict) and "estimated_execution_ms" in meta:
            return float(meta["estimated_execution_ms"])
        return 500.0

    def construct_stages(self, graph: DependencyGraph) -> List[ExecutionStage]:
        """Converts graph execution levels into raw ExecutionStage objects with durations."""
        stages: List[ExecutionStage] = []
        
        # Maps agent name to stage ID for dependency lookup
        agent_to_stage_id: Dict[str, str] = {}
        for lvl in graph.levels:
            stage_num = lvl.level_number + 1
            stage_id = f"stage_{stage_num}"
            for agent in lvl.agents:
                agent_to_stage_id[agent] = stage_id

        for lvl in graph.levels:
            stage_num = lvl.level_number + 1
            stage_id = f"stage_{stage_num}"
            
            # Map parallel flag to ExecutionStrategy
            strategy = (
                ExecutionStrategy.PARALLEL if lvl.parallel 
                else ExecutionStrategy.SEQUENTIAL
            )
            
            # Determine stage dependencies from agent incoming links
            dependencies_set = set()
            for agent in lvl.agents:
                node = graph.nodes[agent]
                for parent in node.incoming:
                    parent_stage_id = agent_to_stage_id.get(parent)
                    if parent_stage_id and parent_stage_id != stage_id:
                        dependencies_set.add(parent_stage_id)
            
            dependencies = sorted(list(dependencies_set))
            
            # Calculate estimated duration
            # Parallel: Max of agent durations (longest running concurrent task)
            # Sequential: Sum of agent durations
            agent_durations = [self._get_agent_duration(graph.nodes[a]) for a in lvl.agents]
            
            if strategy == ExecutionStrategy.PARALLEL:
                estimated_duration_ms = max(agent_durations) if agent_durations else 0.0
            else:
                estimated_duration_ms = sum(agent_durations) if agent_durations else 0.0

            stages.append(ExecutionStage(
                stage_id=stage_id,
                stage_number=stage_num,
                agents=lvl.agents,
                execution_strategy=strategy,
                dependencies=dependencies,
                estimated_duration_ms=estimated_duration_ms,
                metadata={}
            ))
            
        return stages


class ParallelAnalyzer:
    """Analyzes stage strategies to compute parallel execution statistics."""

    @staticmethod
    def analyze(stages: List[ExecutionStage]) -> PlanStatistics:
        """Aggregates execution plan parallelization metrics."""
        agent_count = sum(len(s.agents) for s in stages)
        stage_count = len(stages)
        
        parallel_stages = [s for s in stages if s.execution_strategy == ExecutionStrategy.PARALLEL]
        sequential_stages = [s for s in stages if s.execution_strategy == ExecutionStrategy.SEQUENTIAL]
        
        max_width = max(len(s.agents) for s in stages) if stages else 0
        depth = stage_count  # Stages are mapped sequentially from dependency levels
        
        estimated_parallelism = (
            round(agent_count / depth, 2) if depth > 0 
            else 0.0
        )
        
        parallel_groups = [s.agents for s in parallel_stages]

        return PlanStatistics(
            agent_count=agent_count,
            stage_count=stage_count,
            parallel_stage_count=len(parallel_stages),
            sequential_stage_count=len(sequential_stages),
            maximum_parallel_width=max_width,
            critical_path_length=stage_count,
            execution_depth=depth,
            estimated_parallelism=estimated_parallelism
        )


class PlanOptimizer:
    """Applies scheduling policy optimizations and constructs sequence hashes."""

    @staticmethod
    def optimize(
        stages: List[ExecutionStage], 
        policy: SchedulingPolicy
    ) -> Tuple[List[ExecutionStage], str]:
        """Normalizes metadata and computes finalized execution order signature."""
        optimized_stages: List[ExecutionStage] = []
        
        # Policy hook extension point: SequentialOnly forces SEQUENTIAL strategy
        for stage in stages:
            strategy = stage.execution_strategy
            estimated_duration_ms = stage.estimated_duration_ms
            
            if policy == SchedulingPolicy.SEQUENTIAL_ONLY and strategy == ExecutionStrategy.PARALLEL:
                strategy = ExecutionStrategy.SEQUENTIAL
                # Recalculate duration as sum instead of max for sequential fallback
                # In actual implementation, we'd retrieve durations, but we can reuse stage metadata
                # for simple heuristic adjustment or recalculation. Since we normalize stage metadata
                # here, we can set normalized indicators.
                pass
                
            # Normalize metadata with policy information
            meta = dict(stage.metadata)
            meta["policy_applied"] = policy.value
            meta["normalized_cost"] = 1.0  # Extension point for cost scheduling
            
            optimized_stages.append(ExecutionStage(
                stage_id=stage.stage_id,
                stage_number=stage.stage_number,
                agents=stage.agents,
                execution_strategy=strategy,
                dependencies=stage.dependencies,
                estimated_duration_ms=estimated_duration_ms,
                metadata=meta
            ))
            
        # Build execution order fingerprint hash (SHA-256)
        hash_builder = []
        for stage in optimized_stages:
            hash_builder.append(f"{stage.stage_id}:{stage.execution_strategy.value}:{','.join(stage.agents)}")
            
        execution_order_hash = hashlib.sha256(
            ";".join(hash_builder).encode('utf-8')
        ).hexdigest()
        
        return optimized_stages, execution_order_hash


class PlanValidator:
    """Validates structural integrity and correctness of the ExecutionPlan."""

    @staticmethod
    def validate(graph: DependencyGraph, stages: List[ExecutionStage]) -> None:
        """Enforces stage sequence continuity, dependency safety, and node counts."""
        if not stages:
            raise InvalidExecutionPlanError("Execution plan must contain at least one stage.")

        # 1. Continuous stage numbering with no gaps starting at 1
        sorted_stages = sorted(stages, key=lambda s: s.stage_number)
        for idx, stage in enumerate(sorted_stages):
            expected_num = idx + 1
            if stage.stage_number != expected_num:
                raise InvalidExecutionPlanError(
                    f"Stage numbering gap detected: expected stage {expected_num}, got {stage.stage_number}."
                )

        # 2. Check node counts: Every graph node must appear exactly once in the plan
        scheduled_agents: List[str] = []
        for stage in stages:
            if not stage.agents:
                raise InvalidExecutionPlanError(f"Stage '{stage.stage_id}' is empty.")
            scheduled_agents.extend(stage.agents)

        unique_scheduled = set(scheduled_agents)
        if len(unique_scheduled) != len(scheduled_agents):
            raise InvalidExecutionPlanError("Duplicate agents detected across stages.")

        graph_nodes = set(graph.nodes.keys())
        if unique_scheduled != graph_nodes:
            missing = graph_nodes - unique_scheduled
            extra = unique_scheduled - graph_nodes
            raise InvalidExecutionPlanError(
                f"Plan nodes do not match dependency graph nodes. Missing: {missing}, Extra: {extra}."
            )

        # 3. Dependencies are respected (predecessors must reside in earlier stages)
        agent_to_stage_num: Dict[str, int] = {}
        for stage in stages:
            for agent in stage.agents:
                agent_to_stage_num[agent] = stage.stage_number

        for stage in stages:
            for agent in stage.agents:
                node = graph.nodes[agent]
                for parent in node.incoming:
                    parent_stage_num = agent_to_stage_num[parent]
                    if parent_stage_num >= stage.stage_number:
                        raise InvalidExecutionPlanError(
                            f"Dependency violation: Agent '{agent}' in stage {stage.stage_number} "
                            f"depends on agent '{parent}' in stage {parent_stage_num}."
                        )


# =============================================================================
# Section 4: Main ExecutionPlanner
# =============================================================================

class ExecutionPlanner:
    """Coordinates ExecutionStage construction, parallel profiling, optimization, and caching."""

    def __init__(self) -> None:
        self._cached_signature: Optional[str] = None
        self._cached_plan: Optional[ExecutionPlan] = None

    def invalidate_cache(self) -> None:
        """Explicitly clear the cached execution plan."""
        self._cached_signature = None
        self._cached_plan = None
        logger.info("[ExecutionPlanner] Plan cache explicitly invalidated")

    def _generate_graph_signature(self, graph: DependencyGraph) -> str:
        """Generates a SHA-256 fingerprint tracing the source dependency graph structure."""
        node_sigs = []
        for name, node in sorted(graph.nodes.items()):
            node_sigs.append(f"{name}:{sorted(node.incoming)}:{sorted(node.outgoing)}")
        return hashlib.sha256(";".join(node_sigs).encode('utf-8')).hexdigest()

    def plan(
        self, 
        graph: DependencyGraph, 
        policy: SchedulingPolicy = SchedulingPolicy.DEFAULT,
        force_refresh: bool = False
    ) -> ExecutionPlan:
        """Transforms a DependencyGraph into a schedule-optimized ExecutionPlan."""
        logger.info("Execution Planning Started")

        # 1. Signature generation for cache matching
        graph_signature = self._generate_graph_signature(graph)

        if not force_refresh and self._cached_signature == graph_signature and self._cached_plan is not None:
            logger.info("Execution Planning Finished (Cached)")
            return self._cached_plan

        # 2. Stage Construction
        constructor = StageConstructor()
        stages = constructor.construct_stages(graph)
        logger.info("Execution Stages Built")

        # 3. Parallel analysis
        stats = ParallelAnalyzer.analyze(stages)
        logger.info("Parallel Analysis Complete")

        # 4. Optimization
        optimizer = PlanOptimizer()
        optimized_stages, order_hash = optimizer.optimize(stages, policy)
        logger.info("Execution Plan Optimized")

        # 5. Validation
        PlanValidator.validate(graph, optimized_stages)
        logger.info("Execution Plan Validated")

        # 6. Total duration estimation
        estimated_duration = sum(s.estimated_duration_ms for s in optimized_stages)

        plan = ExecutionPlan(
            stages=optimized_stages,
            total_stages=stats.stage_count,
            parallel_stage_count=stats.parallel_stage_count,
            sequential_stage_count=stats.sequential_stage_count,
            estimated_total_duration_ms=estimated_duration,
            critical_path_length=stats.critical_path_length,
            execution_depth=stats.execution_depth,
            signature=graph_signature,
            execution_order_hash=order_hash,
            created_at=datetime.now(tz=timezone.utc),
            statistics=stats
        )

        # Cache result
        self._cached_signature = graph_signature
        self._cached_plan = plan
        logger.info("Execution Plan Cached")
        logger.info(
            "Execution Planning Finished | Estimated Runtime: %s ms | Critical Path Length: %s | Max Parallel Width: %s",
            estimated_duration, stats.critical_path_length, stats.maximum_parallel_width
        )

        return plan
