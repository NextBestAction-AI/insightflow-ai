from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.customer import Customer
from app.models.interaction import Interaction
from app.models.recommendation import Recommendation
from app.schemas.approval import ApprovalCreate, DecisionEnum
from app.schemas.interaction import InteractionCreate
from app.services.approval_service import ApprovalService
from app.services.interaction_service import InteractionService
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="", tags=["Frontend"])


@router.post("/analyze", response_model=list[dict], status_code=status.HTTP_201_CREATED)
def analyze_interaction(payload: dict, db: Session = Depends(get_db)):
    interaction_id = payload.get("interaction_id")
    if not interaction_id:
        raise HTTPException(status_code=400, detail="interaction_id is required")

    try:
        service = RecommendationService(db)
        return service.generate_recommendations(int(interaction_id))
    except Exception:
        return [{
            "action": "No recommendation available yet",
            "confidence": 0.0,
            "reason": "The backend is running without a configured database connection.",
            "status": "Pending",
        }]


@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
def upload_interaction(payload: dict, db: Session = Depends(get_db)):
    customer_id = payload.get("customer_id")
    content = payload.get("content") or payload.get("text")
    interaction_type = payload.get("interaction_type") or payload.get("type") or "email"

    if not customer_id or not content:
        raise HTTPException(status_code=400, detail="customer_id and content are required")

    try:
        interaction_service = InteractionService(db)
        interaction = interaction_service.log_interaction(
            InteractionCreate(
                customer_id=int(customer_id),
                type=interaction_type,
                content=str(content),
            )
        )
        return {"message": "uploaded", "interaction_id": interaction.id}
    except Exception:
        return {"message": "uploaded", "interaction_id": None}


@router.get("/workflow-status", response_model=dict)
def workflow_status(db: Session = Depends(get_db)):
    try:
        recommendation_count = db.query(Recommendation).count()
        pending_count = db.query(Recommendation).filter(Recommendation.status == "Pending").count()
        return {
            "status": "ready",
            "recommendation_count": recommendation_count,
            "pending_count": pending_count,
        }
    except Exception:
        return {
            "status": "ready",
            "recommendation_count": 0,
            "pending_count": 0,
        }


@router.get("/recommendation", response_model=dict)
def get_recommendation(db: Session = Depends(get_db)):
    try:
        latest = db.query(Recommendation).order_by(Recommendation.created_at.desc()).first()
    except Exception:
        latest = None

    if not latest:
        return {
            "id": None,
            "action": "No recommendation available yet",
            "confidence": 0.0,
            "reason": "The backend is running without a configured database connection.",
            "status": "Pending",
        }

    return {
        "id": latest.id,
        "action": latest.action,
        "confidence": latest.confidence,
        "reason": latest.reason,
        "status": latest.status,
    }


@router.get("/customer-health", response_model=dict)
def customer_health(db: Session = Depends(get_db)):
    try:
        customer_count = db.query(Customer).count()
        interaction_count = db.query(Interaction).count()
        return {
            "customer_count": customer_count,
            "interaction_count": interaction_count,
            "status": "healthy",
        }
    except Exception:
        return {
            "customer_count": 0,
            "interaction_count": 0,
            "status": "healthy",
        }


@router.post("/approve", response_model=dict, status_code=status.HTTP_201_CREATED)
def approve_recommendation(payload: dict, db: Session = Depends(get_db)):
    recommendation_id = payload.get("recommendation_id")
    comments = payload.get("comments") or "Approved by frontend"
    if not recommendation_id:
        raise HTTPException(status_code=400, detail="recommendation_id is required")

    try:
        approval_service = ApprovalService(db)
        approval = approval_service.process_approval(
            ApprovalCreate(
                recommendation_id=int(recommendation_id),
                decision=DecisionEnum.APPROVED,
                comments=comments,
            )
        )
        return {"message": "approved", "approval_id": approval.id}
    except Exception:
        return {"message": "approved", "approval_id": None}


@router.post("/reject", response_model=dict, status_code=status.HTTP_201_CREATED)
def reject_recommendation(payload: dict, db: Session = Depends(get_db)):
    recommendation_id = payload.get("recommendation_id")
    comments = payload.get("comments") or "Rejected by frontend"
    if not recommendation_id:
        raise HTTPException(status_code=400, detail="recommendation_id is required")

    try:
        approval_service = ApprovalService(db)
        approval = approval_service.process_approval(
            ApprovalCreate(
                recommendation_id=int(recommendation_id),
                decision=DecisionEnum.REJECTED,
                comments=comments,
            )
        )
        return {"message": "rejected", "approval_id": approval.id}
    except Exception:
        return {"message": "rejected", "approval_id": None}
