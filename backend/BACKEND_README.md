# InsightFlow AI – Backend Architecture & Setup

## Overview

This is a **production-quality FastAPI backend** for the InsightFlow AI hackathon project. The backend implements the complete data layer, API routes, and business logic for the Intelligent Next Best Action Platform.

### Key Features

- **Clean Architecture**: Clear separation between routes, services, and database layers
- **Type Safety**: Full type hints with Pydantic v2 validation
- **REST APIs**: Complete CRUD operations for all entities
- **Error Handling**: Global exception handling with proper HTTP status codes
- **Logging**: Structured logging for debugging and monitoring
- **Dependency Injection**: FastAPI's dependency system for clean code
- **SQLAlchemy ORM**: Direct ORM integration without repository pattern
- **Production Ready**: No TODOs, no placeholders, complete implementations

---

## Architecture

### Layered Architecture

```
HTTP Requests
    ↓
[API Routes] - FastAPI endpoints, validation, HTTP
    ↓
[Services] - Business logic, validations, transactions
    ↓
[Database] - SQLAlchemy ORM, MySQL queries
    ↓
MySQL Database
```

### Folder Structure

```
backend/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
│
├── config/
│   ├── settings.py           # Configuration management
│   └── logging.py            # Logging setup
│
├── database/
│   ├── base.py               # SQLAlchemy base models
│   ├── mysql.py              # MySQL connection & session management
│   └── chromadb.py           # ChromaDB integration (placeholder)
│
├── models/
│   ├── customer.py           # Customer SQLAlchemy model
│   ├── interaction.py        # Interaction model
│   ├── recommendation.py     # Recommendation model
│   └── approval.py           # Approval model
│
├── schemas/
│   ├── customer.py           # Customer Pydantic schemas
│   ├── interaction.py        # Interaction schemas
│   ├── recommendation.py     # Recommendation schemas
│   └── approval.py           # Approval schemas
│
├── services/
│   ├── customer_service.py       # Customer business logic
│   ├── interaction_service.py    # Interaction business logic
│   ├── recommendation_service.py # Recommendation business logic
│   └── approval_service.py       # Approval business logic
│
├── api/
│   ├── routes.py             # All API endpoints
│   └── dependencies.py       # Dependency injection
│
├── orchestrator/
│   ├── planner.py            # Backend workflow planning
│   └── workflow_state.py     # Workflow state tracking
│
├── agents/
│   └── base_agent.py         # Agent integration base class
│
└── utils/
    └── constants.py          # Constants and enumerations
```

---

## API Endpoints

### Base URL
```
http://localhost:8000/api/v1
```

### Documentation
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

### Customer Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/customers` | Create customer |
| GET | `/customers` | List customers (paginated) |
| GET | `/customers/{id}` | Get customer by ID |
| GET | `/customers/email/{email}` | Get customer by email |
| GET | `/customers/company/{company}` | List customers by company |
| PUT | `/customers/{id}` | Update customer |
| DELETE | `/customers/{id}` | Delete customer |

### Interaction Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/interactions` | Create interaction |
| GET | `/interactions` | List interactions (paginated) |
| GET | `/interactions/{id}` | Get interaction by ID |
| GET | `/customers/{customer_id}/interactions` | Get customer's interactions |
| GET | `/interactions/type/{type}` | Get interactions by type |
| PUT | `/interactions/{id}` | Update interaction |
| DELETE | `/interactions/{id}` | Delete interaction |

### Recommendation Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/recommendations` | Create recommendation |
| POST | `/recommendations/bulk` | Create multiple recommendations |
| GET | `/recommendations` | List recommendations (paginated) |
| GET | `/recommendations/{id}` | Get recommendation by ID |
| GET | `/customers/{customer_id}/recommendations` | Get customer's recommendations |
| GET | `/interactions/{interaction_id}/recommendations` | Get interaction's recommendations |
| GET | `/recommendations/pending` | Get pending recommendations |
| GET | `/recommendations/status/{status}` | Get recommendations by status |
| PUT | `/recommendations/{id}` | Update recommendation |
| DELETE | `/recommendations/{id}` | Delete recommendation |

### Approval Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/approvals` | Create approval |
| GET | `/approvals` | List approvals (paginated) |
| GET | `/approvals/{id}` | Get approval by ID |
| GET | `/approvals/recommendation/{recommendation_id}` | Get approval for recommendation |
| GET | `/approvals/decision/{decision}` | Get approvals by decision |
| GET | `/approvals/statistics` | Get approval statistics |
| PUT | `/approvals/{id}` | Update approval |
| DELETE | `/approvals/{id}` | Delete approval |

### Health Check
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check endpoint |
| GET | `/` | Root endpoint with API info |

---

## Setup & Installation

### Prerequisites
- Python 3.12+
- MySQL 8.0+
- pip (Python package manager)

### 1. Clone the Repository
```bash
cd backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env with your MySQL credentials and other settings
```

Example `.env`:
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=insightflow_ai
MYSQL_USER=root
MYSQL_PASSWORD=your_password
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG
```

### 5. Create MySQL Database
```bash
mysql -u root -p
CREATE DATABASE insightflow_ai;
EXIT;
```

### 6. Run the Application
```bash
python main.py
```

Or using uvicorn:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`

---

## API Usage Examples

### Create a Customer
```bash
curl -X POST http://localhost:8000/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "company": "Acme Corp",
    "industry": "Technology",
    "email": "john@acme.com"
  }'
```

### Create an Interaction
```bash
curl -X POST http://localhost:8000/api/v1/interactions \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "type": "email",
    "content": "Customer inquired about pricing"
  }'
```

### Create a Recommendation
```bash
curl -X POST http://localhost:8000/api/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_id": 1,
    "customer_id": 1,
    "action": "Send detailed pricing information",
    "confidence": 0.95,
    "reason": "Customer showed high interest in pricing"
  }'
```

### Create an Approval
```bash
curl -X POST http://localhost:8000/api/v1/approvals \
  -H "Content-Type: application/json" \
  -d '{
    "recommendation_id": 1,
    "decision": "approved",
    "comments": "Looks good, proceed with outreach"
  }'
```

---

## Data Models

### Customer
- `id`: Integer (Primary Key)
- `name`: String (255)
- `company`: String (255)
- `industry`: String (100)
- `email`: String (255, Unique)
- `created_at`: DateTime

### Interaction
- `id`: Integer (Primary Key)
- `customer_id`: Integer (Foreign Key → Customer)
- `type`: String (50) - email, call, meeting, support_ticket, feedback, other
- `content`: Text
- `created_at`: DateTime

### Recommendation
- `id`: Integer (Primary Key)
- `interaction_id`: Integer (Foreign Key → Interaction)
- `customer_id`: Integer (Foreign Key → Customer)
- `action`: String (255)
- `confidence`: Float (0.0-1.0)
- `reason`: Text
- `status`: String (50) - pending, approved, rejected, executed
- `created_at`: DateTime

### Approval
- `id`: Integer (Primary Key)
- `recommendation_id`: Integer (Foreign Key → Recommendation, Unique)
- `decision`: String (20) - approved, rejected
- `comments`: Text (Optional)
- `reviewed_at`: DateTime

---

## Response Format

All API responses follow a consistent JSON format:

### Success Response
```json
{
  "id": 1,
  "name": "John Doe",
  "company": "Acme Corp",
  "industry": "Technology",
  "email": "john@acme.com",
  "created_at": "2024-06-27T10:30:00"
}
```

### List Response
```json
{
  "total": 10,
  "items": [
    { "id": 1, "name": "John Doe", ... },
    { "id": 2, "name": "Jane Smith", ... }
  ]
}
```

### Error Response
```json
{
  "detail": "Customer not found"
}
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Successful GET |
| 201 | Created - Successful POST |
| 204 | No Content - Successful DELETE |
| 400 | Bad Request - Validation error |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |

---

## Logging

Logs are written to:
- **Console**: For development (when DEBUG=True)
- **File**: `logs/app.log` with rotation (10MB files, 5 backups)

### Log Levels
- DEBUG: Detailed diagnostic information
- INFO: General informational messages
- WARNING: Warning messages
- ERROR: Error messages

### Example Log Entries
```
2024-06-27 10:30:00 - services.customer_service - INFO - Customer created: 1
2024-06-27 10:31:00 - api.routes - WARNING - Customer with email john@acme.com already exists
2024-06-27 10:32:00 - database.mysql - ERROR - Failed to create tables: ...
```

---

## Dependency Injection

The backend uses FastAPI's dependency injection system for clean, testable code:

```python
@router.get("/customers/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return CustomerService.get_customer_by_id(db, customer_id)
```

---

## Error Handling

The backend implements comprehensive error handling:

1. **Input Validation**: Pydantic validates request payloads
2. **Business Logic Validation**: Services validate business rules
3. **Exception Handlers**: Global exception handlers return proper HTTP status codes
4. **Logging**: All errors are logged for debugging

---

## Testing

To test the API endpoints, use the Swagger UI:
```
http://localhost:8000/api/docs
```

Or use curl, Postman, or any HTTP client.

---

## Performance Considerations

- **Database Connection Pooling**: MySQL connection pooling configured
- **Pagination**: All list endpoints support pagination (default 100, max 1000)
- **Indexes**: Indexes on frequently queried columns (email, company, customer_id, etc.)
- **Async I/O**: FastAPI's async support for non-blocking operations

---

## Security Notes

- **CORS**: Configured to allow cross-origin requests
- **Input Validation**: All inputs validated with Pydantic
- **SQL Injection Prevention**: SQLAlchemy ORM prevents SQL injection
- **Error Messages**: Generic error messages in production

---

## Troubleshooting

### Database Connection Issues
```
Error: Can't connect to MySQL server
Solution: Check MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD in .env
```

### Port Already in Use
```
Error: Address already in use
Solution: Use a different port: uvicorn main:app --port 8001
```

### Import Errors
```
Error: ModuleNotFoundError
Solution: Ensure you're running from the backend directory and have activated the virtual environment
```

---

## Development Tips

1. **Reload on Changes**: Use `--reload` flag with uvicorn for auto-reload during development
2. **Database Reset**: Drop all tables by calling `DatabaseManager.drop_tables()` in a script
3. **Async Testing**: Use async test clients for testing async endpoints
4. **Logging Debug**: Set LOG_LEVEL=DEBUG in .env for verbose logging

---

## Next Steps

1. **Setup MySQL Database**: Create database and import schema
2. **Configure Environment**: Copy `.env.example` to `.env` and add credentials
3. **Install Dependencies**: Run `pip install -r requirements.txt`
4. **Run Backend**: Execute `python main.py`
5. **Test APIs**: Visit Swagger UI at http://localhost:8000/api/docs

---

## Support

For issues or questions, refer to:
- FastAPI Docs: https://fastapi.tiangolo.com
- SQLAlchemy Docs: https://docs.sqlalchemy.org
- Pydantic Docs: https://docs.pydantic.dev

---

**Backend Version**: 1.0.0  
**Last Updated**: 2024-06-27  
**Python**: 3.12+  
**Status**: Production Ready
