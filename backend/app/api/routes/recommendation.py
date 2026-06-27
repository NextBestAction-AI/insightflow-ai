from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.customer import Customer
from app.models.interaction import Interaction
from app.models.recommendation import Recommendation
from app.schemas.approval import ApprovalCreate, DecisionEnum
from app.schemas.recommendation import RecommendationCreate, RecommendationResponse
from app.services.approval_service import ApprovalService
from app.services.customer_service import CustomerService
from app.services.interaction_service import InteractionService
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.post("/generate/{interaction_id}", response_model=list[RecommendationResponse], status_code=status.HTTP_201_CREATED)
def generate_recommendations(interaction_id: int, db: Session = Depends(get_db)):
    """
    Triggers the Gemini AI engine to read the transcript and write Next Best Actions down.
    """
    service = RecommendationService(db)
    return service.generate_recommendations(interaction_id)

@router.get("/pending", response_model=list[RecommendationResponse])
def list_pending_recommendations(db: Session = Depends(get_db)):
    service = RecommendationService(db)
    return service.list_pending_recommendations()

@router.get("/{recommendation_id}", response_model=RecommendationResponse)
def get_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    service = RecommendationService(db)
    return service.get_recommendation(recommendation_id)


@router.post("/analyze", response_model=list[RecommendationResponse], status_code=status.HTTP_201_CREATED)
def analyze_interaction(payload: dict, db: Session = Depends(get_db)):
    interaction_id = payload.get("interaction_id")
    if not interaction_id:
        raise HTTPException(status_code=400, detail="interaction_id is required")

    service = RecommendationService(db)
    return service.generate_recommendations(int(interaction_id))


@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
def upload_interaction(payload: dict, db: Session = Depends(get_db)):
    customer_id = payload.get("customer_id")
    content = payload.get("content") or payload.get("text")
    interaction_type = payload.get("interaction_type") or payload.get("type") or "email"

    if not customer_id or not content:
        raise HTTPException(status_code=400, detail="customer_id and content are required")

    interaction_service = InteractionService(db)
    interaction = interaction_service.log_interaction(
        type="create",
        customer_id=int(customer_id),
        content=str(content),
    )
    return {"message": "uploaded", "interaction_id": interaction.id}


@router.get("/workflow-status", response_model=dict)
def workflow_status(db: Session = Depends(get_db)):
    recommendation_count = db.query(Recommendation).count()
    pending_count = db.query(Recommendation).filter(Recommendation.status == "Pending").count()
    return {
        "status": "ready",
        "recommendation_count": recommendation_count,
        "pending_count": pending_count,
    }


@router.get("/customer-health", response_model=dict)
def customer_health(db: Session = Depends(get_db)):
    customer_count = db.query(Customer).count()
    interaction_count = db.query(Interaction).count()
    return {
        "customer_count": customer_count,
        "interaction_count": interaction_count,
        "status": "healthy",
    }


@router.post("/approve", response_model=dict)
def approve_recommendation(payload: dict, db: Session = Depends(get_db)):
    recommendation_id = payload.get("recommendation_id")
    comments = payload.get("comments") or "Approved by frontend"
    if not recommendation_id:
        raise HTTPException(status_code=400, detail="recommendation_id is required")

    approval_service = ApprovalService(db)
    approval = approval_service.process_approval(
        ApprovalCreate(
            recommendation_id=int(recommendation_id),
            decision=DecisionEnum.APPROVED,
            comments=comments,
        )
    )
    return {"message": "approved", "approval_id": approval.id}


@router.post("/reject", response_model=dict)
def reject_recommendation(payload: dict, db: Session = Depends(get_db)):
    recommendation_id = payload.get("recommendation_id")
    comments = payload.get("comments") or "Rejected by frontend"
    if not recommendation_id:
        raise HTTPException(status_code=400, detail="recommendation_id is required")

    approval_service = ApprovalService(db)
    approval = approval_service.process_approval(
        ApprovalCreate(
            recommendation_id=int(recommendation_id),
            decision=DecisionEnum.REJECTED,
            comments=comments,
        )
    )
    return {"message": "rejected", "approval_id": approval.id}