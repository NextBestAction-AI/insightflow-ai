"""
backend/scratch/run_insightflow.py
====================================
Standalone end-to-end execution script for the InsightFlow AI pipeline.

Reads LLM provider and model configuration from the environment and executes
the workflow pipeline.
"""

from __future__ import annotations

import sys
import os
import time
import asyncio
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, List, Optional, Type, Dict

# Ensure stdout supports UTF-8 on Windows for checkmark symbols
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 1. Bootstrap sys.path and load environment.env before any other imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPT_DIR)
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)

for _path in [_PROJECT_DIR, _BACKEND_DIR]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Load environment.env directly into os.environ
_env_file = os.path.join(_BACKEND_DIR, "environment.env")
if os.path.exists(_env_file):
    with open(_env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# Now configure logging to INFO level
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("run_insightflow")

# Clear LLMConfig singleton cache to ensure it loads the env vars
from backend.services.llm.config import get_llm_config, LLMProvider
get_llm_config.cache_clear()
cfg = get_llm_config()

# Apply the Gemini embedding model monkey patch ONLY if active provider is Gemini
if cfg.llm_model_type == LLMProvider.GEMINI:
    try:
        import google.generativeai as genai
        _original_embed_content = genai.embed_content

        def _patched_embed_content(model, *args, **kwargs):
            if model == "models/text-embedding-004":
                model = "models/gemini-embedding-001"
            return _original_embed_content(model, *args, **kwargs)

        genai.embed_content = _patched_embed_content
        logger.info("Patched Gemini embedding health check model.")
    except Exception as e:
        logger.warning(f"Could not patch Gemini embedding model: {e}")

# 2. Production imports
from backend.services.llm import create_llm_service, LLMService
from backend.orchestrator.workflow_state import (
    WorkflowState, CustomerState, InputState, ContextState, AnalysisState, MetadataState
)
from backend.orchestrator.execution_context import ExecutionContext
from backend.orchestrator.workflow_status import ExecutionMode
from backend.orchestrator.planner import Planner, PlannerConfiguration
from backend.orchestrator.agent_registry import AgentRegistry
from backend.orchestrator.workflow_executor import WorkflowExecutor

# Import business agents
from backend.agents.interaction_agent import InteractionAgent
from backend.agents.knowledge_agent import KnowledgeAgent
from backend.agents.crm_agent import CRMAgent
from backend.agents.health_agent import HealthAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.reasoning_agent import ReasoningAgent
from backend.agents.recommendation_agent import RecommendationAgent

# =============================================================================
# Custom Subclasses to Intercept and Display Execution Progress
# =============================================================================

class InstrumentedAgentRegistry(AgentRegistry):
    """
    AgentRegistry that wraps created agent instances to intercept their run()
    calls and print start/completion status.
    """
    def __init__(self, llm_service: LLMService) -> None:
        super().__init__()
        self._llm_service = llm_service

    def create_instance(
        self,
        agent_name: str,
        llm_service: Optional[Any] = None,
        prompt_manager: Optional[Any] = None,
        state_validator: Optional[Any] = None
    ):
        instance = super().create_instance(agent_name, llm_service, prompt_manager, state_validator)
        
        # Override the run method of the instance to track completion times
        original_run = instance.run
        
        async def custom_run(state: WorkflowState, context: ExecutionContext):
            print(f"\n[Execution] Running {agent_name}...")
            
            # Sleep only if using real Gemini/OpenAI provider to avoid rate limiting
            active_service = llm_service or self._llm_service
            is_mock = False
            if active_service and hasattr(active_service, "_pipeline"):
                client = getattr(active_service._pipeline, "_client", None)
                if client and getattr(client, "provider_name", "") == "mock":
                    is_mock = True
            
            if not is_mock:
                print(f"[Execution] Sleeping 10.0 seconds to prevent rate limiting on real LLM...")
                await asyncio.sleep(10.0)
            
            start_time = time.monotonic()
            result = await original_run(state, context)
            elapsed_ms = (time.monotonic() - start_time) * 1000.0
            print(f"[Execution] Finished {agent_name} in {elapsed_ms:.2f}ms")
            return result
            
        instance.run = custom_run
        return instance


class InstrumentedWorkflowExecutor(WorkflowExecutor):
    """
    WorkflowExecutor that prints the planned stages and execution progress.
    """
    async def execute(self, state, context, plan, graph):
        print("\nWorkflow Started\n")
        
        # Print all planned stages and agents in each stage as requested by Requirement 5
        for stage in plan.stages:
            print(f"Stage {stage.stage_number}")
            for agent_name in stage.agents:
                print(agent_name)
            print()
            
        # Execute the actual workflow plan
        return await super().execute(state, context, plan, graph)

# =============================================================================
# Helper function to print outputs in a readable format
# =============================================================================

def print_section_header(title: str):
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)

def print_final_outputs(state: WorkflowState):
    print_section_header("Interaction Analysis")
    ia = state.analysis.interaction_analysis
    if ia:
        print(f"Sentiment: {ia.get('sentiment', 'N/A')} (Score: {ia.get('sentiment_score', 'N/A')})")
        print(f"Intent: {ia.get('intent', 'N/A')}")
        print(f"Urgency: {ia.get('urgency', 'N/A')}")
        print(f"Summary: {ia.get('summary', 'N/A')}")
        print("\nKey Topics:")
        for t in ia.get("key_topics", []):
            print(f" - {t}")
        print("\nAction Items:")
        for ai in ia.get("action_items", []):
            print(f" - [{ai.get('owner', 'N/A')}] {ai.get('action', 'N/A') or ai.get('description', 'N/A')} (Due: {ai.get('due', 'N/A') or ai.get('due_date', 'N/A')})")
    else:
        print("No interaction analysis output.")

    print_section_header("Knowledge Context")
    kc = state.context.knowledge_context
    if kc:
        if isinstance(kc, list):
            for doc in kc:
                print(f"Title: {doc.get('title', 'N/A')} (Relevance Score: {doc.get('relevance_score', 'N/A') or doc.get('score', 'N/A')})")
                print(f"Summary: {doc.get('summary', 'N/A')}")
                print("-" * 30)
        elif isinstance(kc, dict):
            print(f"Summary: {kc.get('summary', 'N/A')}")
            print("\nRelevant Documents:")
            for doc in kc.get("relevant_documents", []):
                print(f" - [{doc.get('doc_id', 'N/A')}] {doc.get('title', 'N/A')} (Score: {doc.get('score', 'N/A')})")
    else:
        print("No knowledge context retrieved.")

    print_section_header("CRM Context")
    crm = state.context.crm_context
    if crm:
        profile = crm.get("profile", {})
        contract = crm.get("contract", {})
        renewal = crm.get("renewal", {})
        usage = crm.get("usage", {})
        support = crm.get("support", {})
        
        print(f"Company: {profile.get('company', 'N/A')} ({profile.get('customer_name', 'N/A')})")
        print(f"Industry: {profile.get('industry', 'N/A')} | Region: {profile.get('region', 'N/A')} | Tier: {profile.get('account_type', 'N/A')}")
        print(f"ACV: ${contract.get('annual_contract_value_usd', 0):,.2f} | Billing Frequency: {contract.get('billing_frequency', 'N/A')}")
        print(f"Renewal Likelihood: {renewal.get('renewal_likelihood', 0.0)*100:.1f}% | Risk Level: {renewal.get('risk_level', 'N/A')}")
        print(f"Usage: {usage.get('dau', 0)} DAU / {usage.get('monthly_active_users', 0)} MAU | API Calls: {usage.get('api_calls_last_30_days', 0):,}")
        print(f"Open Tickets: {support.get('open_tickets_count', 0)} | Escalation Status: {support.get('escalation_status', False)}")
    else:
        print("No CRM context loaded.")

    print_section_header("Health Assessment")
    ha = state.analysis.health_assessment
    if ha:
        print(f"Health Score: {ha.get('score', 'N/A') or ha.get('health_score', 'N/A')}")
        print(f"Category: {ha.get('status', 'N/A') or ha.get('health_category', 'N/A')} | Trend: {ha.get('trend', 'N/A') or ha.get('health_trend', 'N/A')}")
        print(f"Explanation: {ha.get('summary', 'N/A') or ha.get('health_explanation', 'N/A')}")
        print("\nDrivers:")
        drivers = ha.get("drivers", []) or ha.get("health_factors", {}).keys()
        for d in drivers:
            print(f" - {d}")
    else:
        print("No health assessment output.")

    print_section_header("Risk Assessment")
    ra = state.analysis.risk_assessment
    if ra:
        print(f"Overall Risk Level: {ra.get('overall_level', 'N/A') or ra.get('overall_risk_level', 'N/A')}")
        print(f"Confidence: {ra.get('confidence', 0.0)*100:.1f}%")
        print(f"Summary: {ra.get('summary', 'N/A')}")
        print("\nIdentified Risks:")
        risks = ra.get("identified_risks", []) or ra.get("risks", [])
        for r in risks:
            severity = r.get('severity', 'N/A')
            category = r.get('category', r.get('risk_type', 'N/A'))
            print(f" - [{severity.upper()}] {category}: {r.get('description', 'N/A')}")
    else:
        print("No risk assessment output.")

    print_section_header("Business Reasoning")
    br = state.analysis.business_reasoning
    if br:
        print(f"Overall Assessment: {br.get('overall_assessment', 'N/A')}")
        print(f"Confidence Score: {br.get('confidence', 0.0)*100:.1f}%")
        print(f"Summary: {br.get('summary', 'N/A')}")
        print("\nKey Findings:")
        for kf in br.get("key_findings", []):
            print(f" - {kf.get('title', 'N/A')}: {kf.get('reasoning', 'N/A')} (Evidence: {kf.get('evidence', 'N/A')})")
    else:
        print("No business reasoning output.")

    print_section_header("Recommendations")
    recs_block = state.analysis.recommendations
    if recs_block:
        print(f"Overall Priority: {recs_block.get('overall_priority', 'N/A')}")
        print(f"Confidence Score: {recs_block.get('confidence', 0.0)*100:.1f}%")
        print(f"Summary: {recs_block.get('summary', 'N/A') or recs_block.get('recommendation_summary', 'N/A')}")
        print("\nAction Plan:")
        for idx, rec in enumerate(recs_block.get("recommendations", []), 1):
            print(f" {idx}. [{rec.get('priority', 'N/A').upper()}] {rec.get('title', 'N/A') or rec.get('action', 'N/A')}")
            print(f"    Description: {rec.get('description', 'N/A') or rec.get('rationale', 'N/A')}")
            print(f"    Expected Outcome: {rec.get('expected_impact', 'N/A') or rec.get('expected_outcome', 'N/A')}")
    else:
        print("No recommendations generated.")

# =============================================================================
# Main Script Execution
# =============================================================================

async def main():
    print_section_header("LLM Configuration")
    
    # Load LLM Config dynamically
    try:
        cfg = get_llm_config()
    except Exception as e:
        print(f"Error loading LLM Configuration: {e}")
        traceback.print_exc()
        return 1

    print(f"Provider: {cfg.llm_model_type.value}")
    print(f"Model: {cfg.active_model_name}")

    # Instantiate LLMService
    try:
        llm_service = create_llm_service(config=cfg)
    except Exception as e:
        print(f"Error creating LLM Service: {e}")
        traceback.print_exc()
        return 1

    # Run health check
    health = await llm_service.health_check()
    status = health.get("status", "unknown")
    print(f"Status: {status}")
    print(f"Providers Status: {health.get('providers', {})}")
    
    if status != "healthy":
        print("Aborting: LLM provider health check failed (not healthy).")
        return 1

    # Initialize registry
    registry = InstrumentedAgentRegistry(llm_service=llm_service)
    registry.register_many([
        InteractionAgent,
        KnowledgeAgent,
        CRMAgent,
        HealthAgent,
        RiskAgent,
        ReasoningAgent,
        RecommendationAgent
    ])

    # Build Sample WorkflowState
    state = WorkflowState(
        customer=CustomerState(
            customer_id="CUST-102",  # matches seed customer Bob Miller, Globex Corporation in CRMAgent
            customer_name="Bob Miller",
            company="Globex Corporation",
            industry="Technology",
            account_type="Mid-Market",
            region="AMER",
            employee_count=350,
            annual_revenue_usd=15000000.0
        ),
        input=InputState(
            user_query=(
                "Bob Miller from Globex Corporation has raised a critical support ticket regarding "
                "continuous API timeouts. He indicates this is impacting their release schedules "
                "and is seriously questioning whether Globex will renew their subscription "
                "this June. Suggest a health assessment, risk evaluation, and recommendations."
            ),
            transcript=(
                "Bob Miller: We are seeing high latency and timeouts on the sync API endpoints. "
                "This is affecting our daily jobs. Honestly, if this isn't resolved quickly, "
                "we will have to look at alternatives like DataFlow AI. We also expect billing "
                "credit for the downtime."
            ),
            emails=[
                (
                    "From: bob.miller@globex.com\n"
                    "Subject: Billing credit and API stability issues\n\n"
                    "Hi Success Team,\n\n"
                    "Following up on our call, we need a written root cause analysis for the "
                    "timeouts on Tuesday. Please issue a billing credit for last month's downtime.\n\n"
                    "Bob Miller\nGlobex Corp"
                )
            ],
            meeting_notes=(
                "Sync meeting with Globex - 2026-06-25\n"
                "Bob Miller expressed severe frustration with API downtime.\n"
                "CSM to escalate with the engineering team."
            ),
            source_channel="email",
            language="en"
        ),
        metadata=MetadataState(
            version="1.0.0",
            tags=["api-timeouts", "renewal-risk", "credit-request"],
            source_system="email-inbox",
            priority="critical"
        )
    )

    # Initialize custom Executor and Planner
    planner_config = PlannerConfiguration(
        parallel_execution=False,
        max_retries=1,
        continue_on_failure=False,
        stop_on_validation_error=True
    )
    
    executor = InstrumentedWorkflowExecutor(
        registry=registry,
        max_retries=planner_config.max_retries,
        continue_on_failure=planner_config.continue_on_failure,
        llm_service=llm_service
    )
    
    planner = Planner(
        config=planner_config,
        registry=registry,
        executor=executor,
        llm_service=llm_service
    )

    context = ExecutionContext(
        request_id="scratch-test-run-gemini",
        execution_mode=ExecutionMode.LIVE,
        retry_count=0,
        max_retries=planner_config.max_retries
    )

    last_completed_agent = None
    failing_agent = None
    execution_stage = None
    root_cause = None
    
    wall_start = time.monotonic()
    
    try:
        result = await planner.run(state, context)
        wall_end = time.monotonic()
        elapsed_seconds = wall_end - wall_start
        
        # Display Outputs
        print_final_outputs(state)
        
        # Display Metrics
        print_section_header("Metrics")
        print(f"Workflow Status: {state.execution.execution_status.value}")
        print(f"Execution Time: {elapsed_seconds:.3f}s ({state.execution.total_execution_time_ms or 0.0} ms)")
        print(f"Completed Agents: {result.completed_agents}")
        print(f"Failed Agents: {result.failed_agents}")
        print(f"Skipped Agents: {result.skipped_agents}")
        
        # Planner & Executor Metrics
        print("\nPlanner Metrics:")
        print(f" - Stages Count: {len(result.completed_agents) if result.success else 'N/A'}")
        
        print("\nExecutor Metrics:")
        print(f" - Total Attempts: {len(result.completed_agents) + len(result.failed_agents)}")
        for agent_name, record in state.execution.agent_records.items():
            print(f"   • {agent_name}: Status={record.status.value}, Duration={record.execution_time_ms}ms, Retries={record.retry_count}")
        
        # LLM Usage Statistics
        print_section_header("LLM Usage Statistics")
        stats = await llm_service.get_stats()
        print(f"Total Requests: {stats.get('total_requests', 0)}")
        print(f"Success Rate: {stats.get('success_rate', 0.0)*100:.2f}%")
        print(f"Cache Hit Rate: {stats.get('cache_hit_rate', 0.0)*100:.2f}%")
        print("\nToken Usage:")
        print(f" - Prompt Tokens: {stats.get('total_prompt_tokens', 0):,}")
        print(f" - Output Tokens: {stats.get('total_output_tokens', 0):,}")
        print(f" - Total Tokens: {stats.get('total_tokens', 0):,}")
        print(f"\nEstimated Cost: ${stats.get('total_cost_usd', 0.0):.6f}")

        # Verification Checklist
        print_section_header("Validation Checklist")
        agents_ordered = [
            ("InteractionAgent", "Interaction completed"),
            ("KnowledgeAgent", "Knowledge completed"),
            ("CRMAgent", "CRM completed"),
            ("HealthAgent", "Health completed"),
            ("RiskAgent", "Risk completed"),
            ("ReasoningAgent", "Reasoning completed"),
            ("RecommendationAgent", "Recommendation completed")
        ]
        
        completed_set = set(result.completed_agents)
        all_passed = True
        for agent_id, display_name in agents_ordered:
            passed = agent_id in completed_set
            status_char = "✓" if passed else "✗"
            try:
                print(f"{status_char} {display_name}")
            except UnicodeEncodeError:
                status_ascii = "[OK]" if passed else "[FAIL]"
                print(f"{status_ascii} {display_name}")
            if not passed:
                all_passed = False
                
        print("\n" + "=" * 50)
        if all_passed:
            print("SUMMARY: Workflow completed successfully with all agents executing.")
            return 0
        else:
            print("SUMMARY: Workflow completed, but not all agents executed successfully.")
            return 1

    except Exception as e:
        print_section_header("Execution Error")
        print("UNHANDLED EXCEPTION — full traceback:")
        traceback.print_exc()
        
        # Extract failing agent and stage if we can find it
        failing_agent = state.execution.current_agent or "Unknown Agent"
        print(f"\nFailing Agent: {failing_agent}")
        
        # Find last completed agent
        completed_list = state.execution.completed_agents
        last_completed_agent = completed_list[-1] if completed_list else "None"
        print(f"Last Completed Agent: {last_completed_agent}")
        
        print(f"Root Cause: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
