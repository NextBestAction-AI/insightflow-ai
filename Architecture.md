# InsightFlow AI – System Architecture

## Overview

InsightFlow AI is a multi-agent customer intelligence platform that transforms unstructured customer interactions into actionable business recommendations. The system uses an AI orchestration layer to coordinate specialized agents, each responsible for a distinct stage of customer analysis.

The architecture follows a layered, modular design with clear separation of concerns, enabling scalability, maintainability, and easy extensibility.

---

# Architecture Diagram

```text
                    ┌─────────────────────────┐
                    │      React Frontend     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     FastAPI Backend     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │        Planner          │
                    └────────────┬────────────┘
                                 │
               ┌─────────────────┼──────────────────┐
               ▼                 ▼                  ▼
      Dependency Resolver   Execution Planner   Agent Registry
               │                 │                  │
               └─────────────────┼──────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │    Workflow Executor    │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────────────────────────────────┐
        │            Shared Workflow State                   │
        └────────────────────────────────────────────────────┘
                                 │
     ┌──────────────┬──────────────┬──────────────┬──────────────┐
     ▼              ▼              ▼              ▼
Interaction     Knowledge        CRM          Health
   Agent          Agent         Agent          Agent
                                 │
                                 ▼
                            Risk Agent
                                 │
                                 ▼
                        Reasoning Agent
                                 │
                                 ▼
                     Recommendation Agent
                                 │
                                 ▼
                     Human Approval Workflow
                                 │
                                 ▼
                         MySQL Database
```

---

# Core Components

## 1. Frontend

* React + TypeScript
* Dashboard for customer analysis
* Workflow visualization
* Recommendation review
* Human approval interface

---

## 2. Backend API

Built using FastAPI.

Responsibilities:

* REST API endpoints
* Validation
* Authentication (extensible)
* Request handling
* Database interaction

---

## 3. Planner

The Planner is the orchestration engine of the platform.

Responsibilities:

* Validate workflow input
* Resolve agent dependencies
* Generate execution plan
* Coordinate workflow execution
* Handle failures and retries

The Planner does not perform business analysis itself; it only manages execution.

---

## 4. Shared Workflow State

All agents communicate through a shared WorkflowState.

It stores:

* Customer information
* Interaction analysis
* CRM context
* Knowledge context
* Health assessment
* Risk assessment
* Business reasoning
* Recommendations
* Approval status
* Execution metadata

This eliminates direct communication between agents and keeps them loosely coupled.

---

# AI Agents

## Interaction Agent

Purpose:

* Analyze customer conversation
* Detect sentiment
* Extract intent
* Identify urgency
* Generate structured interaction summary

Output:

* Interaction Analysis

---

## Knowledge Agent

Purpose:

* Retrieve relevant enterprise knowledge
* Search documentation
* Provide contextual information

Output:

* Knowledge Context

---

## CRM Agent

Purpose:

* Retrieve customer profile
* Subscription details
* Renewal information
* Historical interactions

Output:

* CRM Context

---

## Health Agent

Purpose:

* Evaluate customer relationship health
* Combine interaction, CRM, and knowledge signals

Output:

* Health Assessment

---

## Risk Agent

Purpose:

* Detect business risks
* Estimate churn probability
* Identify renewal risks
* Highlight operational concerns

Output:

* Risk Assessment

---

## Reasoning Agent

Purpose:

* Combine outputs from previous agents
* Produce holistic business understanding
* Explain why the customer is in the current state

Output:

* Business Reasoning

---

## Recommendation Agent

Purpose:

* Generate prioritized next-best actions
* Provide confidence scores
* Attach supporting evidence

Output:

* Recommendation Plan

---

# Human-in-the-Loop

Recommendations are not executed automatically.

Business users can:

* Approve
* Reject
* Modify

This ensures transparency and human oversight.

---

# Data Flow

1. Customer uploads interaction.
2. FastAPI receives request.
3. Planner validates workflow.
4. Dependency Resolver builds execution graph.
5. Execution Planner creates execution stages.
6. Workflow Executor executes agents.
7. Agents update WorkflowState.
8. Recommendation Agent produces business actions.
9. Human reviews recommendations.
10. Results are stored in MySQL.

---

# Design Decisions

### Multi-Agent Architecture

Instead of a single LLM prompt, responsibilities are divided among specialized agents.

Benefits:

* Modular
* Easier debugging
* Better maintainability
* Independent testing

---

### Shared Workflow State

Agents never communicate directly.

Benefits:

* Loose coupling
* Extensibility
* Easier orchestration

---

### Metadata-Driven Orchestration

Each agent declares:

* required_inputs
* produced_outputs

The Planner automatically resolves dependencies.

Adding a new agent requires minimal changes.

---

### Provider Abstraction

The LLM layer supports multiple providers through a common interface.

Current providers:

* Gemini
* MockLLM

Future providers can be added without modifying business agents.

---

# Technology Stack

Frontend

* React
* TypeScript
* Tailwind CSS

Backend

* FastAPI
* Python
* Pydantic

Database

* MySQL

AI

* Gemini API
* Mock LLM Provider

Architecture

* Planner
* Dependency Resolver
* Execution Planner
* Workflow Executor
* Shared Workflow State
* Specialized AI Agents

---

# Future Enhancements

* Real-time workflow streaming using WebSockets
* Vector database integration
* Multi-tenant architecture
* Agent parallelization
* Observability dashboard
* Advanced approval workflows
* Additional specialized AI agents

---

# Conclusion

InsightFlow AI demonstrates a scalable, modular, and extensible multi-agent architecture for customer intelligence. By combining orchestration, specialized AI agents, shared workflow state, and human approval, the platform transforms customer interactions into explainable, evidence-backed business recommendations suitable for enterprise environments.
