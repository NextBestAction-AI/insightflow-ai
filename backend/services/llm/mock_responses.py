"""
backend/services/llm/mock_responses.py
======================================
Deterministic mock responses for every business agent in the InsightFlow AI platform.

Each generator returns valid JSON strings matching the exact Pydantic schema
expected by the corresponding agent's ResponseParser.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def interaction_response(prompt: str) -> str:
    """Return mock response for InteractionAgent matching InteractionAnalysis schema."""
    return json.dumps(
        {
            "customer": "Globex Corporation",
            "participants": ["Bob Miller", "CSM Sarah Johnson"],
            "sentiment": "negative",
            "sentiment_score": -0.85,
            "urgency": "critical",
            "issues": [
                {
                    "description": "Continuous API timeouts on sync endpoints delaying releases.",
                    "severity": "critical",
                    "category": "performance",
                    "status": "escalated"
                },
                {
                    "description": "Downtime occurred last Tuesday; requesting billing credit.",
                    "severity": "medium",
                    "category": "billing",
                    "status": "open"
                }
            ],
            "entities": [
                {"name": "Globex Corporation", "entity_type": "organisation"},
                {"name": "Bob Miller", "entity_type": "person"},
                {"name": "DataFlow AI", "entity_type": "competitor", "context": "Evaluating alternatives like DataFlow AI"}
            ],
            "action_items": [
                {
                    "description": "Escalate API timeouts to principal reliability team.",
                    "owner": "CSM Sarah Johnson",
                    "due_date": "Today",
                    "priority": "high"
                },
                {
                    "description": "Calculate downtime and check billing credit eligibility.",
                    "owner": "Finance Team",
                    "due_date": "Next week",
                    "priority": "medium"
                }
            ],
            "commitments": [
                {
                    "description": "Provide written root cause analysis for timeouts.",
                    "made_by": "CSM Sarah Johnson",
                    "due_date": "Within 48 hours"
                }
            ],
            "key_topics": ["API timeouts", "billing credit", "SLA violation", "non-renewal threat"],
            "summary": "Bob Miller from Globex Corporation is frustrated with continuous API timeouts delaying sync jobs and releases. Threatening not to renew in June and evaluating competitor DataFlow AI if SLA is not met. Demanding billing credit.",
            "interaction_count": 4,
            "sources_analysed": ["email", "transcript", "meeting_notes"],
            "analysed_at": datetime.now(tz=timezone.utc).isoformat(),
            "confidence": 0.95
        }
    )


def knowledge_response(prompt: str) -> str:
    """Return mock response for KnowledgeAgent matching KnowledgeContext schema."""
    return json.dumps(
        {
            "summary": "For API timeouts and query latency, the Database Latency playbook recommends slow query logs review and read replica routing. Billing credits under 10% can be approved by account manager, whereas larger credits require CFO approval.",
            "confidence": 0.90,
            "relevant_documents": [
                {
                    "doc_id": "KB-101",
                    "title": "Database Latency & Query Timeout Escalation Playbook",
                    "type": "playbook",
                    "score": 0.95
                },
                {
                    "doc_id": "KB-102",
                    "title": "Billing Disputes & Credit Application Playbook",
                    "type": "playbook",
                    "score": 0.88
                }
            ],
            "playbooks": [
                "Database Latency & Query Timeout Escalation Playbook outlines escalation to infrastructure engineering when timeouts occur on read replica.",
                "Billing Disputes & Credit Application Playbook specifies credits require SLA validation logs."
            ],
            "troubleshooting_guides": [
                "Check slow query logs for executions exceeding 5000ms.",
                "Ensure dashboard panels do not exceed 10 panels per viewer."
            ],
            "previous_cases": [
                "Case #98127: Latency resolved by database re-indexing and query partition."
            ],
            "product_information": [
                "API rate limits allow 1000 requests per minute per IP."
            ],
            "known_limitations": [
                "Older sync client versions do not auto-retry on 504 Gateway Timeouts."
            ],
            "best_practices": [
                "Apply partition keys for date ranges under 30 days to optimize reads."
            ],
            "citations": ["KB-101", "KB-102"]
        }
    )


def crm_response(prompt: str) -> str:
    """Stub generator for CRM context if queried by any future AI models."""
    return json.dumps({"status": "CRM Agent handles retrieval; no direct LLM generation required."})


def health_response(prompt: str) -> str:
    """Return mock response for HealthAgent matching HealthAssessment schema."""
    return json.dumps(
        {
            "score": 35,
            "status": "poor",
            "trend": "declining",
            "drivers": [
                "Critical support escalation due to API timeouts",
                "Decline in active usage telemetry",
                "Direct threat of competitor replacement"
            ],
            "confidence": 0.85,
            "summary": "Customer relationship health has significantly declined due to unresolved API timeouts impacting production releases, combined with a direct evaluation of DataFlow AI."
        }
    )


def risk_response(prompt: str) -> str:
    """Return mock response for RiskAgent matching RiskAssessment schema."""
    return json.dumps(
        {
            "overall_level": "critical",
            "identified_risks": [
                {
                    "category": "support",
                    "severity": "critical",
                    "probability": 0.90,
                    "impact": 0.95,
                    "evidence": "Bob Miller explicitly stated that if API stability is not resolved quickly, it will affect renewal.",
                    "description": "Renewal risk due to SLA breach and unresolved API timeouts."
                },
                {
                    "category": "sentiment",
                    "severity": "high",
                    "probability": 0.85,
                    "impact": 0.80,
                    "evidence": "Evaluated DataFlow AI and demanded credit.",
                    "description": "Competitor replacement threat from DataFlow AI."
                }
            ],
            "confidence": 0.90,
            "summary": "Overall risk level is critical due to upcoming renewal in June, direct non-renewal threat, active evaluation of competitor, and ongoing technical friction."
        }
    )


def reasoning_response(prompt: str) -> str:
    """Return mock response for ReasoningAgent matching BusinessReasoning schema."""
    return json.dumps(
        {
            "overall_assessment": "critical_escalation",
            "business_context": {
                "customer_stage": "renewal",
                "relationship_status": "critical",
                "product_adoption": "declining",
                "support_state": "escalated"
            },
            "key_findings": [
                {
                    "title": "API Instability Endangering June Renewal",
                    "reasoning": "Recurring 504 Gateway Timeouts on synchronisation jobs directly interrupt the customer's business process, leading to executive evaluation of alternatives.",
                    "evidence": "Customer email and call transcript indicating non-renewal threat and competitor evaluation."
                }
            ],
            "supporting_facts": [
                "Globex ARR is $45,000.",
                "June renewal is within 90 days.",
                "1 open critical support ticket regarding API timeouts."
            ],
            "confidence": 0.95,
            "summary": "Globex Corporation is a renewal-risk account in a critical escalation state. Immediate technical resolution and billing credit approval are required to preserve the relationship."
        }
    )


def recommendation_response(prompt: str) -> str:
    """Return mock response for RecommendationAgent matching RecommendationPlan schema."""
    return json.dumps(
        {
            "recommendations": [
                {
                    "title": "Escalate API Timeout Ticket and Provide RCA",
                    "description": "Engage principal reliability engineering team to perform root cause analysis on database timeouts and sync lag. Share RCA within 48 hours.",
                    "priority": "critical",
                    "category": "Support",
                    "expected_impact": "Restores customer confidence in operational capability.",
                    "success_probability": 0.90,
                    "reasoning": "RCA is the primary executive commitment made by CSM, addressing the core technical blocker.",
                    "supporting_evidence": ["1 open support ticket", "Commitment: provide RCA within 48h"]
                },
                {
                    "title": "Approve Proactive Billing Credit",
                    "description": "Issue a billing credit representing 10% of last month's subscription value to compensate for query latency and timeout downtime.",
                    "priority": "high",
                    "category": "Renewal",
                    "expected_impact": "Mitigates billing dispute and renewal risk.",
                    "success_probability": 0.85,
                    "reasoning": "Bob Miller explicitly requested credit and indicated non-renewal is possible if not addressed.",
                    "supporting_evidence": ["Requested billing credit", "ACV is $45,000"]
                },
                {
                    "title": "Schedule Executive Support Review",
                    "description": "Align CSM VP with Bob Miller to discuss the SLA improvement plan and present the custom read replica routing timeline.",
                    "priority": "medium",
                    "category": "Executive Engagement",
                    "expected_impact": "Maintains alignment and delays competitor transition.",
                    "success_probability": 0.75,
                    "reasoning": "Direct engagement with decision makers demonstrates corporate prioritization.",
                    "supporting_evidence": ["Evaluated alternatives like DataFlow AI"]
                }
            ],
            "overall_priority": "critical",
            "confidence": 0.95,
            "summary": "An urgent technical escalation, proactive credit offering, and executive alignment are needed to retain Globex Corporation."
        }
    )
