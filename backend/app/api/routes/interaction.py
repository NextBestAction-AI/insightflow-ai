from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.interaction import InteractionCreate, InteractionResponse
from app.services.interaction_service import InteractionService

router = APIRouter(prefix="/interactions", tags=["Interactions"])

@router.post("/", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
def log_interaction(interaction: InteractionCreate, db: Session = Depends(get_db)):
    service = InteractionService(db)
    return service.log_interaction(interaction)

@router.get("/{interaction_id}", response_model=InteractionResponse)
def get_interaction(interaction_id: int, db: Session = Depends(get_db)):
    service = InteractionService(db)
    return service.get_interaction_details(interaction_id)

@router.get("/customer/{customer_id}", response_model=list[InteractionResponse])
def get_customer_history(customer_id: int, db: Session = Depends(get_db)):
    service = InteractionService(db)
    return service.get_customer_history(customer_id)