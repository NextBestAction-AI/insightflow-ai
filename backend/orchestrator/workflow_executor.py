# -*- coding: utf-8 -*-
"""
backend/orchestrator/workflow_executor.py
=========================================
WorkflowExecutor executes an ExecutionPlan stage-by-stage, managing agent
instantiation, retries, state updates, metric tracking, and failure cascade propagation.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.orchestrator.agent_registry import AgentRegistry
from backend.orchestrator.agent_result import AgentResult
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.execution_planner import ExecutionPlan
from backend.orchestrator.dependency_resolver import DependencyGraph
from backend.orchestrator.workflow_result import WorkflowResult
from backend.orchestrator.workflow_state import WorkflowState
from backend.orchestrator.workflow_status import WorkflowStatus

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Executes the scheduled ExecutionPlan, updating state and capturing metrics."""

    def __init__(
        self,
        registry: AgentRegistry,
        max_retries: int = 3,
        continue_on_failure: bool = False,
        llm_service: Optional[Any] = None,
        prompt_manager: Optional[Any] = None,
        state_validator: Optional[Any] = None
    ) -> None:
        self._registry = registry
        self._max_retries = max_retries
        self._continue_on_failure = continue_on_failure
        self._llm_service = llm_service
        self._prompt_manager = prompt_manager
        self._state_validator = state_validator

    async def execute(
        self,
        state: WorkflowState,
        context: ExecutionContext,
        plan: ExecutionPlan,
        graph: DependencyGraph
    ) -> WorkflowResult:
        """Executes the plan stage-by-stage and records results, handling retries and skips."""
        logger.info("Workflow Execution Started")

        # Mark workflow run as active
        if state.execution.started_at is None:
            state.execution.started_at = datetime.now(tz=timezone.utc)
            state.execution.execution_status = WorkflowStatus.RUNNING

        completed_agents: List[str] = []
        failed_agents: List[str] = []
        skipped_agents: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []

        total_retries = 0
        execution_start = time.monotonic()
        agent_times: Dict[str, float] = {}

        # Loop through execution stages in the plan
        for stage in plan.stages:
            logger.info("Stage Started | Stage ID: %s | Strategy: %s", stage.stage_id, stage.execution_strategy.value)

            # We execute sequentially today to preserve order and correctness,
            # but the architecture is structured to support asyncio.gather in the future.
            for agent_name in stage.agents:
                node = graph.nodes[agent_name]

                # Check if any incoming dependencies failed or were skipped
                dependency_failed = any(
                    dep in failed_agents or dep in skipped_agents
                    for dep in node.incoming
                )

                if dependency_failed:
                    logger.info("Agent Skipped (Dependency Failed) | Agent: %s", agent_name)
                    state.execution.mark_agent_skipped(agent_name, "Dependency failed or skipped.")
                    skipped_agents.append(agent_name)
                    continue

                logger.info("Agent Started | Agent: %s", agent_name)

                # Instantiate agent using the registry
                try:
                    agent_instance = self._registry.create_instance(
                        agent_name=agent_name,
                        llm_service=self._llm_service,
                        prompt_manager=self._prompt_manager,
                        state_validator=self._state_validator
                    )
                except Exception as exc:
                    err_msg = f"Agent instantiation failed for '{agent_name}': {exc}"
                    logger.error(err_msg)
                    errors.append(err_msg)
                    state.execution.mark_agent_failed(agent_name, err_msg, 0.0)
                    failed_agents.append(agent_name)
                    continue

                # Execution with retries
                retry_count = 0
                success = False
                result: Optional[AgentResult] = None

                while retry_count <= self._max_retries:
                    agent_ctx = ExecutionContext(
                        request_id=context.request_id,
                        execution_mode=context.execution_mode,
                        retry_count=retry_count,
                        max_retries=self._max_retries
                    )

                    state.execution.set_current_agent(agent_name)

                    try:
                        # Execute agent through BaseAgent.run
                        result = await agent_instance.run(state, agent_ctx)
                        if result.success:
                            success = True
                            break
                        else:
                            retry_count += 1
                            total_retries += 1
                    except Exception as exc:
                        logger.exception("Unexpected exception running agent '%s': %s", agent_name, exc)
                        retry_count += 1
                        total_retries += 1
                        result = AgentResult(
                            agent_name=agent_name,
                            success=False,
                            errors=[str(exc)],
                            execution_time_ms=0.0
                        )

                if success and result:
                    logger.info("Agent Completed | Agent: %s | Time: %s ms", agent_name, result.execution_time_ms)
                    state.execution.mark_agent_completed(agent_name, result.execution_time_ms)
                    completed_agents.append(agent_name)
                    agent_times[agent_name] = result.execution_time_ms
                    if result.warnings:
                        warnings.extend(result.warnings)
                else:
                    err_msg = result.errors[0] if result and result.errors else "Execution failed after maximum retries"
                    logger.error("Agent Failed | Agent: %s | Error: %s", agent_name, err_msg)
                    state.execution.mark_agent_failed(agent_name, err_msg, result.execution_time_ms if result else 0.0)
                    failed_agents.append(agent_name)
                    agent_times[agent_name] = result.execution_time_ms if result else 0.0
                    errors.append(f"Agent '{agent_name}' failed: {err_msg}")

                    # Halt stage execution if continue_on_failure is False
                    if not self._continue_on_failure:
                        logger.error("Halting workflow execution due to failed agent '%s'", agent_name)
                        break

            logger.info("Stage Completed | Stage ID: %s", stage.stage_id)

            if failed_agents and not self._continue_on_failure:
                break

        # Mark any remaining unexecuted/unskipped agents in the plan as skipped
        all_scheduled_agents = []
        for s in plan.stages:
            all_scheduled_agents.extend(s.agents)

        all_processed = set(completed_agents + failed_agents + skipped_agents)
        for agent_name in all_scheduled_agents:
            if agent_name not in all_processed:
                state.execution.mark_agent_skipped(agent_name, "Halted early due to preceding failure.")
                skipped_agents.append(agent_name)

        # Finalize workflow state
        final_status = WorkflowStatus.COMPLETED if not failed_agents else WorkflowStatus.FAILED
        state.execution.finalise(final_status)

        total_time_ms = round((time.monotonic() - execution_start) * 1000.0, 2)
        logger.info("Workflow Finished | Status: %s | Time: %s ms", final_status.value, total_time_ms)

        # Aggregate metrics
        metrics_dict = {
            "total_execution_time_ms": total_time_ms,
            "completed_agents": completed_agents,
            "failed_agents": failed_agents,
            "skipped_agents": skipped_agents,
            "retry_count": total_retries,
            "agent_times": agent_times
        }

        summary = (
            f"Workflow finished with status: {final_status.value}. "
            f"Executed: {len(completed_agents)} agents, Failed: {len(failed_agents)} agents, "
            f"Skipped: {len(skipped_agents)} agents. Total time: {total_time_ms} ms."
        )

        if len(failed_agents) == 0:
            return WorkflowResult.success(
                execution_time_ms=total_time_ms,
                completed_agents=completed_agents,
                final_state=state,
                warnings=warnings,
                metrics=metrics_dict,
                execution_summary=summary
            )
        elif len(completed_agents) > 0:
            return WorkflowResult.partial_success(
                execution_time_ms=total_time_ms,
                completed_agents=completed_agents,
                failed_agents=failed_agents,
                skipped_agents=skipped_agents,
                final_state=state,
                warnings=warnings,
                errors=errors,
                metrics=metrics_dict,
                execution_summary=summary
            )
        else:
            return WorkflowResult.failure(
                errors=errors,
                warnings=warnings,
                final_state=state,
                execution_time_ms=total_time_ms,
                execution_summary=summary
            )
