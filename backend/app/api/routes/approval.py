from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.approval import ApprovalCreate, ApprovalResponse
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["Approvals"])

@router.post("/", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
def process_human_decision(approval: ApprovalCreate, db: Session = Depends(get_db)):
    """
    Saves human audit context and updates recommendation status to Approved/Rejected/Modified.
    """
    service = ApprovalService(db)
    return service.process_approval(approval)

@router.get("/{approval_id}", response_model=ApprovalResponse)
def get_approval_log(approval_id: int, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    return service.get_approval_log(approval_id)