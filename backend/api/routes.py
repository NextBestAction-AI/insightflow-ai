from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from config.logging import get_logger
from database.mysql import get_db
from services.customer_service import CustomerService
from services.interaction_service import InteractionService
from services.recommendation_service import RecommendationService
from services.approval_service import ApprovalService
from schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse
from schemas.interaction import InteractionCreate, InteractionUpdate, InteractionResponse, InteractionListResponse
from schemas.recommendation import (
    RecommendationCreate,
    RecommendationUpdate,
    RecommendationResponse,
    RecommendationListResponse,
    BulkRecommendationCreate,
)
from schemas.approval import ApprovalCreate, ApprovalUpdate, ApprovalResponse, ApprovalListResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["InsightFlow AI"])


# ============================================================================
# CUSTOMER ENDPOINTS
# ============================================================================


@router.post("/customers", response_model=CustomerResponse, status_code=201)
def create_customer(customer_data: CustomerCreate, db: Session = Depends(get_db)):
    """Create a new customer."""
    return CustomerService.create_customer(db, customer_data)


@router.get("/customers", response_model=dict)
def list_customers(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    """List all customers with pagination."""
    customers, total = CustomerService.get_all_customers(db, skip=skip, limit=limit)
    return {"total": total, "items": customers}


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """Get a customer by ID."""
    return CustomerService.get_customer_by_id(db, customer_id)


@router.get("/customers/email/{email}", response_model=CustomerResponse)
def get_customer_by_email(email: str, db: Session = Depends(get_db)):
    """Get a customer by email."""
    return CustomerService.get_customer_by_email(db, email)


@router.get("/customers/company/{company}", response_model=dict)
def list_customers_by_company(
    company: str, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    """Get customers by company."""
    customers, total = CustomerService.get_customers_by_company(db, company, skip=skip, limit=limit)
    return {"total": total, "items": customers}


@router.put("/customers/{customer_id}", response_model=CustomerResponse)
def update_customer(customer_id: int, customer_data: CustomerUpdate, db: Session = Depends(get_db)):
    """Update a customer."""
    return CustomerService.update_customer(db, customer_id, customer_data)


@router.delete("/customers/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """Delete a customer."""
    CustomerService.delete_customer(db, customer_id)


# ============================================================================
# INTERACTION ENDPOINTS
# ============================================================================


@router.post("/interactions", response_model=InteractionResponse, status_code=201)
def create_interaction(interaction_data: InteractionCreate, db: Session = Depends(get_db)):
    """Create a new interaction."""
    return InteractionService.create_interaction(db, interaction_data)


@router.get("/interactions", response_model=InteractionListResponse)
def list_interactions(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    """List all interactions with pagination."""
    interactions, total = InteractionService.get_all_interactions(db, skip=skip, limit=limit)
    return {"total": total, "items": interactions}


@router.get("/interactions/{interaction_id}", response_model=InteractionResponse)
def get_interaction(interaction_id: int, db: Session = Depends(get_db)):
    """Get an interaction by ID."""
    return InteractionService.get_interaction_by_id(db, interaction_id)


@router.get("/customers/{customer_id}/interactions", response_model=InteractionListResponse)
def list_customer_interactions(
    customer_id: int, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    """Get all interactions for a customer."""
    interactions, total = InteractionService.get_interactions_by_customer(db, customer_id, skip=skip, limit=limit)
    return {"total": total, "items": interactions}


@router.get("/interactions/type/{interaction_type}", response_model=InteractionListResponse)
def list_interactions_by_type(
    interaction_type: str, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    """Get interactions by type."""
    interactions, total = InteractionService.get_interactions_by_type(db, interaction_type, skip=skip, limit=limit)
    return {"total": total, "items": interactions}


@router.put("/interactions/{interaction_id}", response_model=InteractionResponse)
def update_interaction(interaction_id: int, interaction_data: InteractionUpdate, db: Session = Depends(get_db)):
    """Update an interaction."""
    return InteractionService.update_interaction(db, interaction_id, interaction_data)


@router.delete("/interactions/{interaction_id}", status_code=204)
def delete_interaction(interaction_id: int, db: Session = Depends(get_db)):
    """Delete an interaction."""
    InteractionService.delete_interaction(db, interaction_id)


# ============================================================================
# RECOMMENDATION ENDPOINTS
# ============================================================================


@router.post("/recommendations", response_model=RecommendationResponse, status_code=201)
def create_recommendation(rec_data: RecommendationCreate, db: Session = Depends(get_db)):
    """Create a new recommendation."""
    return RecommendationService.create_recommendation(db, rec_data)


@router.post("/recommendations/bulk", response_model=list[RecommendationResponse], status_code=201)
def create_bulk_recommendations(bulk_data: BulkRecommendationCreate, db: Session = Depends(get_db)):
    """Create multiple recommendations at once."""
    return RecommendationService.create_bulk_recommendations(db, bulk_data)


@router.get("/recommendations", response_model=RecommendationListResponse)
def list_recommendations(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    """List all recommendations with pagination."""
    recommendations, total = RecommendationService.get_all_recommendations(db, skip=skip, limit=limit)
    pending_recs, _ = RecommendationService.get_pending_recommendations(db, skip=0, limit=1)
    from sqlalchemy import func, select
    from models.recommendation import Recommendation
    pending = db.execute(select(func.count()).select_from(Recommendation).where(Recommendation.status == "pending")).scalar()
    return {"total": total, "pending": pending, "items": recommendations}


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationResponse)
def get_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    """Get a recommendation by ID."""
    return RecommendationService.get_recommendation_by_id(db, recommendation_id)


@router.get("/customers/{customer_id}/recommendations", response_model=RecommendationListResponse)
def list_customer_recommendations(
    customer_id: int, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    """Get all recommendations for a customer."""
    recommendations, total = RecommendationService.get_recommendations_by_customer(db, customer_id, skip=skip, limit=limit)
    return {"total": total, "pending": 0, "items": recommendations}


@router.get("/interactions/{interaction_id}/recommendations", response_model=RecommendationListResponse)
def list_interaction_recommendations(
    interaction_id: int, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    """Get all recommendations for an interaction."""
    recommendations, total = RecommendationService.get_recommendations_by_interaction(db, interaction_id, skip=skip, limit=limit)
    return {"total": total, "pending": 0, "items": recommendations}


@router.get("/recommendations/pending", response_model=RecommendationListResponse)
def list_pending_recommendations(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    """Get all pending recommendations."""
    recommendations, total = RecommendationService.get_pending_recommendations(db, skip=skip, limit=limit)
    return {"total": total, "pending": total, "items": recommendations}


@router.get("/recommendations/status/{status}", response_model=RecommendationListResponse)
def list_recommendations_by_status(
    status: str, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    """Get recommendations by status."""
    recommendations, total = RecommendationService.get_recommendations_by_status(db, status, skip=skip, limit=limit)
    return {"total": total, "pending": 0, "items": recommendations}


@router.put("/recommendations/{recommendation_id}", response_model=RecommendationResponse)
def update_recommendation(recommendation_id: int, rec_data: RecommendationUpdate, db: Session = Depends(get_db)):
    """Update a recommendation."""
    return RecommendationService.update_recommendation(db, recommendation_id, rec_data)


@router.delete("/recommendations/{recommendation_id}", status_code=204)
def delete_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    """Delete a recommendation."""
    RecommendationService.delete_recommendation(db, recommendation_id)


# ============================================================================
# APPROVAL ENDPOINTS
# ============================================================================


@router.post("/approvals", response_model=ApprovalResponse, status_code=201)
def create_approval(approval_data: ApprovalCreate, db: Session = Depends(get_db)):
    """Create a new approval."""
    return ApprovalService.create_approval(db, approval_data)


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approvals(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    """List all approvals with pagination."""
    approvals, total = ApprovalService.get_all_approvals(db, skip=skip, limit=limit)
    stats = ApprovalService.get_approval_statistics(db)
    return {"total": total, "approved": stats["approved"], "rejected": stats["rejected"], "items": approvals}


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
def get_approval(approval_id: int, db: Session = Depends(get_db)):
    """Get an approval by ID."""
    return ApprovalService.get_approval_by_id(db, approval_id)


@router.get("/approvals/recommendation/{recommendation_id}", response_model=ApprovalResponse)
def get_approval_by_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    """Get an approval by recommendation ID."""
    return ApprovalService.get_approval_by_recommendation_id(db, recommendation_id)


@router.get("/approvals/decision/{decision}", response_model=ApprovalListResponse)
def list_approvals_by_decision(
    decision: str, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    """Get approvals by decision."""
    approvals, total = ApprovalService.get_approvals_by_decision(db, decision, skip=skip, limit=limit)
    return {"total": total, "approved": total if decision == "approved" else 0, "rejected": total if decision == "rejected" else 0, "items": approvals}


@router.get("/approvals/statistics", response_model=dict)
def get_approval_statistics(db: Session = Depends(get_db)):
    """Get approval statistics."""
    return ApprovalService.get_approval_statistics(db)


@router.put("/approvals/{approval_id}", response_model=ApprovalResponse)
def update_approval(approval_id: int, approval_data: ApprovalUpdate, db: Session = Depends(get_db)):
    """Update an approval."""
    return ApprovalService.update_approval(db, approval_id, approval_data)


@router.delete("/approvals/{approval_id}", status_code=204)
def delete_approval(approval_id: int, db: Session = Depends(get_db)):
    """Delete an approval."""
    ApprovalService.delete_approval(db, approval_id)


# ============================================================================
# HEALTH CHECK
# ============================================================================


@router.get("/health", status_code=200)
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "InsightFlow AI Backend"}
