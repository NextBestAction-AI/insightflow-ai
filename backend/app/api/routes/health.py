from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/health", tags=["System Health"])

@router.get("", status_code=status.HTTP_200_OK)
def check_system_health(db: Session = Depends(get_db)):
    """
    Verifies that the FastAPI application is alive and checks 
    connectivity to the underlying MySQL database instance.
    """
    health_status = {
        "status": "healthy",
        "services": {
            "api_gateway": "online",
            "database": "unknown"
        }
    }
    
    try:
        # Execute a low-overhead primitive query to test connection pool liveness
        db.execute(text("SELECT 1"))
        health_status["services"]["database"] = "connected"
    except Exception as e:
        # Update flags if database connectivity fails
        health_status["status"] = "unhealthy"
        health_status["services"]["database"] = f"disconnected: {str(e)}"
        
    return health_status