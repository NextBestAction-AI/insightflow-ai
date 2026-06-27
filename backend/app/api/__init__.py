from fastapi import APIRouter
from app.api.routes.customer import router as customer_router
from app.api.routes.interaction import router as interaction_router
from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.approval import router as approval_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.health import router as health_router
from app.api.routes.frontend import router as frontend_router

api_router = APIRouter()

api_router.include_router(customer_router)
api_router.include_router(interaction_router)
api_router.include_router(recommendation_router)
api_router.include_router(approval_router)
api_router.include_router(analytics_router)
api_router.include_router(health_router)
api_router.include_router(frontend_router)