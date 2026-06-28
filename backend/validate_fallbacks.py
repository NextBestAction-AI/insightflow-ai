"""
validate_fallbacks.py
=====================
Standalone script — run from inside backend/ with:

    python validate_fallbacks.py

Imports every agent's Pydantic output model and feeds it the JSON produced by
get_fallback_response() to confirm that each one passes validation.
"""

import json
import sys
import os
import traceback

# ── path setup ────────────────────────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))          # .../backend
_root = os.path.dirname(_here)                              # .../insightflow-ai
sys.path.insert(0, _root)
sys.path.insert(0, _here)
os.environ.setdefault("LLM_MODEL_TYPE", "openai")   # avoid config warnings

# ── helpers ───────────────────────────────────────────────────────────────────
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results = {}

def validate(label: str, model_cls, json_text: str) -> bool:
    try:
        obj = model_cls.model_validate(json.loads(json_text))
        print(f"  [{PASS}] {label}")
        results[label] = "PASS"
        return True
    except Exception as exc:
        print(f"  [{FAIL}] {label}")
        print(f"          {type(exc).__name__}: {exc}")
        results[label] = f"FAIL — {exc}"
        return False


# ── import fallback generator ─────────────────────────────────────────────────
print("\n=== Importing get_fallback_response ===")
from backend.services.llm.openai_client import get_fallback_response
print("  OK\n")


# ── import Pydantic output models ─────────────────────────────────────────────
print("=== Importing Pydantic models ===")
from backend.agents.interaction_agent import InteractionAnalysis
from backend.agents.knowledge_agent import KnowledgeContext
from backend.agents.health_agent import HealthAssessment
from backend.agents.risk_agent import RiskAssessment
from backend.agents.reasoning_agent import BusinessReasoning
from backend.agents.recommendation_agent import RecommendationPlan
print("  All models imported OK\n")


# ── generate fallback JSON using actual system prompts ────────────────────────
# We pass the exact _SYSTEM_PROMPT strings the agents use so the detection logic
# in get_fallback_response() selects the correct branch.

INTERACTION_SYSTEM = (
    "You are a structured JSON extraction engine. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

KNOWLEDGE_SYSTEM = (
    "You are a structured JSON knowledge synthesis engine. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

HEALTH_SYSTEM = (
    "You are a customer relationship health scoring system. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

RISK_SYSTEM = (
    "You are a customer relationship risk scoring system. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

REASONING_SYSTEM = (
    "You are a customer relationship business reasoning system. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

RECOMMENDATION_SYSTEM = (
    "You are a customer success next-best action recommendation engine. "
    "You ALWAYS respond with a single valid JSON object and nothing else. "
    "Never include explanatory prose, markdown fences, or code blocks outside the JSON."
)

DUMMY_PROMPT = "Analyze the following customer data."


# ── run validations ───────────────────────────────────────────────────────────
print("=== Running validations ===\n")

# 1. InteractionAgent
fb_interaction = get_fallback_response(DUMMY_PROMPT, INTERACTION_SYSTEM)
print("--- InteractionAnalysis ---")
print(json.dumps(json.loads(fb_interaction), indent=2))
validate("InteractionAnalysis", InteractionAnalysis, fb_interaction)
print()

# 2. KnowledgeAgent
fb_knowledge = get_fallback_response(DUMMY_PROMPT, KNOWLEDGE_SYSTEM)
print("--- KnowledgeContext ---")
print(json.dumps(json.loads(fb_knowledge), indent=2))
validate("KnowledgeContext", KnowledgeContext, fb_knowledge)
print()

# 3. HealthAgent
fb_health = get_fallback_response(DUMMY_PROMPT, HEALTH_SYSTEM)
print("--- HealthAssessment ---")
print(json.dumps(json.loads(fb_health), indent=2))
validate("HealthAssessment", HealthAssessment, fb_health)
print()

# 4. RiskAgent
fb_risk = get_fallback_response(DUMMY_PROMPT, RISK_SYSTEM)
print("--- RiskAssessment ---")
print(json.dumps(json.loads(fb_risk), indent=2))
validate("RiskAssessment", RiskAssessment, fb_risk)
print()

# 5. ReasoningAgent
fb_reasoning = get_fallback_response(DUMMY_PROMPT, REASONING_SYSTEM)
print("--- BusinessReasoning ---")
print(json.dumps(json.loads(fb_reasoning), indent=2))
validate("BusinessReasoning", BusinessReasoning, fb_reasoning)
print()

# 6. RecommendationAgent
fb_recommendation = get_fallback_response(DUMMY_PROMPT, RECOMMENDATION_SYSTEM)
print("--- RecommendationPlan ---")
print(json.dumps(json.loads(fb_recommendation), indent=2))
validate("RecommendationPlan", RecommendationPlan, fb_recommendation)
print()


# ── summary ───────────────────────────────────────────────────────────────────
print("=== Summary ===")
passed = sum(1 for v in results.values() if v == "PASS")
total  = len(results)
for label, status in results.items():
    icon = "[OK]" if status == "PASS" else "[!!]"
    print(f"  {icon} {label}: {status}")

print(f"\n  Result: {passed}/{total} validations passed")
sys.exit(0 if passed == total else 1)
