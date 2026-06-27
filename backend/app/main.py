import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.core.exceptions.handlers import register_exception_handlers
from app.database.mysql import init_db
from app.api.routes.customer import router as customer_router
from app.api.routes.interaction import router as interaction_router
from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.approval import router as approval_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.health import router as health_router
from app.api.routes.frontend import router as frontend_router

load_dotenv()

app = FastAPI(
    title="InsightFlow AI - Decision Intelligence Platform",
    description="Core backend orchestration engine running targeted business reasoning and Next Best Action pipelines.",
    version="1.0.0",
)

register_exception_handlers(app)

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customer_router, prefix="/api")
app.include_router(interaction_router, prefix="/api")
app.include_router(recommendation_router, prefix="/api")
app.include_router(approval_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(frontend_router, prefix="/api")


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/", tags=["Root"])
def read_root():
    """Root health check endpoint to verify backend operational readiness."""
    return {
        "status": "Online",
        "platform": "InsightFlow AI Backend Engine",
        "docs_url": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))

    uvicorn.run("app.main:app", host=host, port=port, reload=True)