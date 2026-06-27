from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.customer import Customer
from app.models.recommendation import Recommendation

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Aggregates essential counts for the React frontend's metric dashboard tiles.
    """
    total_customers = db.query(Customer).count()
    total_recommendations = db.query(Recommendation).count()
    
    approved_count = db.query(Recommendation).filter(Recommendation.status == "Approved").count()
    rejected_count = db.query(Recommendation).filter(Recommendation.status == "Rejected").count()
    pending_count = db.query(Recommendation).filter(Recommendation.status == "Pending").count()

    return {
        "total_customers": total_customers,
        "total_recommendations": total_recommendations,
        "status_breakdown": {
            "approved": approved_count,
            "rejected": rejected_count,
            "pending": pending_count
        }
    }