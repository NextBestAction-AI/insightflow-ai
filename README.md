# InsightFlow AI

## Project Overview

InsightFlow AI is an intelligent customer engagement platform designed to recommend the next best actions for customer success, renewal, and risk mitigation. The repository contains a FastAPI backend with a MySQL-backed CRM and recommendation engine, and a React + TypeScript frontend that visualizes customer insights, AI-driven analysis, and recommendation workflows.

## Purpose and Objectives

- Deliver a unified platform for customer intelligence and next best action recommendations.
- Enable rapid ingestion of customer interactions, CRM context, and AI analysis.
- Provide structured recommendations with confidence scores and business reasoning.
- Support review workflows through approvals and status tracking.
- Expose REST APIs for integration with analytics dashboards, automation engines, and backend services.

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, Pydantic, PyMySQL, uvicorn
- Frontend: React 19, TypeScript, Vite, Tailwind CSS, Axios, React Router DOM, Framer Motion
- Database: MySQL
- AI / LLM: Gemini and OpenAI support via environment API keys

## Repository Structure

```
.
├── README.md
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── environment.env
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes.py
│   ├── config/
│   │   ├── logging.py
│   │   └── settings.py
│   ├── database/
│   │   ├── base.py
│   │   ├── chromadb.py
│   │   └── mysql.py
│   ├── models/
│   │   ├── approval.py
│   │   ├── customer.py
│   │   ├── interaction.py
│   │   └── recommendation.py
│   ├── schemas/
│   │   ├── approval.py
│   │   ├── customer.py
│   │   ├── interaction.py
│   │   └── recommendation.py
│   ├── services/
│   │   ├── approval_service.py
│   │   ├── customer_service.py
│   │   ├── interaction_service.py
│   │   ├── recommendation_service.py
│   │   └── llm/
│   │       ├── base_client.py
│   │       ├── gemini_client.py
│   │       ├── openai_client.py
│   │       ├── llm_service.py
│   │       └── prompt_manager.py
│   ├── orchestrator/
│   │   ├── agent_registry.py
│   │   ├── agent_result.py
│   │   ├── dependency_resolver.py
│   │   ├── execution_context.py
│   │   ├── execution_planner.py
│   │   ├── planner.py
│   │   ├── state_validator.py
│   │   ├── workflow_executor.py
│   │   ├── workflow_result.py
│   │   ├── workflow_state.py
│   │   └── workflow_status.py
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── crm_agent.py
│   │   ├── health_agent.py
│   │   ├── interaction_agent.py
│   │   ├── knowledge_agent.py
│   │   ├── reasoning_agent.py
│   │   ├── recommendation_agent.py
│   │   └── risk_agent.py
│   └── utils/
│       └── constants.py
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── src/
    │   ├── App.tsx
    │   ├── main.tsx
    │   ├── config/api.ts
    │   ├── context/DashboardContext.tsx
    │   ├── services/api/
    │   │   ├── apiClient.ts
    │   │   ├── analysisApi.ts
    │   │   ├── approvalApi.ts
    │   │   ├── customerApi.ts
    │   │   ├── interactionApi.ts
    │   │   └── recommendationApi.ts
    │   ├── pages/
    │   └── components/
    └── public/
```

## System Architecture

### Backend

- `backend/main.py`: FastAPI entry point, lifecycle management, middleware, exception handlers, and route registration.
- `backend/api/routes.py`: REST API endpoints for customers, interactions, recommendations, approvals, analysis, and health checks.
- `backend/database/mysql.py`: MySQL engine creation, session management, and table creation.
- `backend/models/`: SQLAlchemy ORM models defining the database schema.
- `backend/schemas/`: Pydantic request and response models for validation and API payload structure.
- `backend/services/`: Business logic for CRUD operations and domain workflows.
- `backend/orchestrator/`: AI workflow orchestration, agent registration, dependency resolution, execution planning, and state management.
- `backend/agents/`: Modular AI agents for CRM context, interaction understanding, knowledge retrieval, health assessment, risk scoring, reasoning, and recommendation generation.

### Frontend

- `frontend/src/App.tsx`: App routes and layout.
- `frontend/src/config/api.ts`: API base configuration.
- `frontend/src/services/api/apiClient.ts`: Axios HTTP client with error handling.
- `frontend/src/services/api/*Api.ts`: Domain service wrappers for customers, interactions, recommendations, approvals, and analysis.
- `frontend/src/context/DashboardContext.tsx`: Global state, workflow simulation, and customer/recommendation management.
- `frontend/src/pages/`: UI screens for dashboard, analysis, recommendations, history, and settings.

## Database Schema

### `customers`
- `id` INT PRIMARY KEY
- `name` VARCHAR(255) NOT NULL
- `company` VARCHAR(255) NOT NULL
- `industry` VARCHAR(100) NOT NULL
- `email` VARCHAR(255) NOT NULL UNIQUE
- `created_at` DATETIME NOT NULL

Indexes:
- `idx_email` on `email`
- `idx_company` on `company`

### `interactions`
- `id` INT PRIMARY KEY
- `customer_id` INT NOT NULL FOREIGN KEY → `customers.id`
- `type` VARCHAR(50) NOT NULL
- `content` TEXT NOT NULL
- `created_at` DATETIME NOT NULL

Indexes:
- `idx_customer_id` on `customer_id`
- `idx_created_at` on `created_at`
- `idx_type` on `type`

### `recommendations`
- `id` INT PRIMARY KEY
- `interaction_id` INT NOT NULL FOREIGN KEY → `interactions.id`
- `customer_id` INT NOT NULL FOREIGN KEY → `customers.id`
- `action` VARCHAR(255) NOT NULL
- `confidence` FLOAT NOT NULL
- `reason` TEXT NOT NULL
- `status` VARCHAR(50) NOT NULL DEFAULT `pending`
- `created_at` DATETIME NOT NULL

Indexes:
- `idx_interaction_id` on `interaction_id`
- `idx_customer_id` on `customer_id`
- `idx_status` on `status`
- `idx_created_at` on `created_at`

### `approvals`
- `id` INT PRIMARY KEY
- `recommendation_id` INT NOT NULL UNIQUE FOREIGN KEY → `recommendations.id`
- `decision` VARCHAR(20) NOT NULL
- `comments` TEXT
- `reviewed_at` DATETIME NOT NULL

Indexes:
- `idx_recommendation_id` on `recommendation_id`
- `idx_reviewed_at` on `reviewed_at`

## API Endpoints

### Base URL
`http://localhost:8000/api/v1`

### Customer APIs
- `POST /customers`
- `GET /customers`
- `GET /customers/{customer_id}`
- `GET /customers/email/{email}`
- `GET /customers/company/{company}`
- `PUT /customers/{customer_id}`
- `DELETE /customers/{customer_id}`

### Interaction APIs
- `POST /interactions`
- `GET /interactions`
- `GET /interactions/{interaction_id}`
- `GET /customers/{customer_id}/interactions`
- `GET /interactions/type/{interaction_type}`
- `PUT /interactions/{interaction_id}`
- `DELETE /interactions/{interaction_id}`

### Recommendation APIs
- `POST /recommendations`
- `POST /recommendations/bulk`
- `GET /recommendations`
- `GET /recommendations/{recommendation_id}`
- `GET /customers/{customer_id}/recommendations`
- `GET /interactions/{interaction_id}/recommendations`
- `GET /recommendations/pending`
- `GET /recommendations/status/{status}`
- `PUT /recommendations/{recommendation_id}`
- `DELETE /recommendations/{recommendation_id}`

### Approval APIs
- `POST /approvals`
- `GET /approvals`
- `GET /approvals/{approval_id}`
- `GET /approvals/recommendation/{recommendation_id}`
- `GET /approvals/decision/{decision}`
- `GET /approvals/statistics`
- `PUT /approvals/{approval_id}`
- `DELETE /approvals/{approval_id}`

### Analysis / Orchestration
- `POST /analyze`
- `GET /health`
- `GET /`

### Documentation
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## LLM API Keys and AI Integration

The backend supports external LLM providers via environment variables:

- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_MODEL`

The AI orchestration endpoint uses these keys indirectly through the LLM services in `backend/services/llm/` and the multi-agent planner.

Additional configuration:

- `AI_PLANNER_URL`: URL used for external AI planning or integration.
- `AI_AGENT_TIMEOUT`: request timeout for AI integration.

## Key Features and Functionality

- Customer CRUD management with email uniqueness and pagination.
- Interaction tracking for customer conversations, transcripts, and notes.
- Recommendation generation, status tracking, and filtering.
- Approval workflows tied to recommendations.
- AI-driven analyze endpoint that orchestrates multiple agents and persists recommendations.
- Health checks and global exception handling.
- Frontend dashboard with route-based navigation and state management.

## Modules and Responsibilities

### Backend Modules
- `main.py`: App lifecycle, CORS, logging, exception handling.
- `api/routes.py`: Route definitions and HTTP contract.
- `config/settings.py`: Environment-driven configuration.
- `config/logging.py`: Logger setup.
- `database/mysql.py`: Engine setup, session factory, lifecycle hooks.
- `database/base.py`: SQLAlchemy declarative base.
- `models/`: Data definitions and foreign keys.
- `schemas/`: Request/response validation and serialization.
- `services/`: Business rules, DB access, data validation.
- `orchestrator/`: Workflow planning, agent execution, state validation.
- `agents/`: Domain-specific AI component logic.

### Frontend Modules
- `src/App.tsx`: Route definitions and layout.
- `src/layouts/MainLayout.tsx`: Shared page container.
- `src/context/DashboardContext.tsx`: Dashboard state and analysis workflows.
- `src/services/api/`: HTTP clients for the backend APIs.
- `src/pages/`: User-facing views for dashboard, analysis, recommendation, history, and settings.
- `src/components/`: Reusable UI primitives.

## Installation and Setup

### Backend Setup

1. Navigate to the backend folder:

```bash
cd backend
```

2. Create and activate a Python virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables by editing `backend/environment.env` or creating `.env`:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=insightflow_ai
MYSQL_USER=root
MYSQL_PASSWORD=your_password
GEMINI_API_KEY=
OPENAI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG
```

5. Create the MySQL database:

```sql
CREATE DATABASE insightflow_ai;
```

6. Start the backend:

```bash
python main.py
```

Or with uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

1. Navigate to the frontend folder:

```bash
cd frontend
```

2. Install Node dependencies:

```bash
npm install
```

3. Start the frontend development server:

```bash
npm run dev
```

4. Open the app in your browser at the URL shown by Vite.

## Configuration Details

- Backend settings are driven by `backend/config/settings.py`.
- The backend reads `.env` automatically using Pydantic settings.
- `API_CONFIG.BASE_URL` in `frontend/src/config/api.ts` points the frontend to the backend API.
- Logging is centralized in `backend/config/logging.py`.
- Database connection pooling and session lifecycle are managed in `backend/database/mysql.py`.

## How the Application Works

1. Users interact with the React frontend and navigate to dashboard, analysis, recommendations, and history views.
2. The frontend calls backend endpoints using Axios.
3. The backend validates requests with Pydantic schemas and executes business logic via service classes.
4. CRUD operations persist data to MySQL through SQLAlchemy models.
5. The `/analyze` endpoint triggers the orchestrator and agent pipeline to synthesize customer context, interaction signals, risk, health, and recommended actions.
6. Generated recommendations are stored in the database and surfaced back to the UI.
7. Approvals can be created and managed to update recommendation statuses.

## Notes

- The `backend/database/chromadb.py` module is currently a placeholder for future vector search integration.
- `backend/agents/` contains rich agent logic for multi-step analysis and can be extended for production AI workflows.
- For local development, ensure the backend is running before using the frontend.

## Contact

For contribution or extension, start with `backend/api/routes.py`, `backend/services/`, and `frontend/src/context/DashboardContext.tsx`.

---

This README documents the InsightFlow AI project structure, setup, and core behavior for developers, integrators, and stakeholders.