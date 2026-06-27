from sqlalchemy.orm import Session
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.interaction import InteractionCreate
from app.models.interaction import Interaction
from fastapi import HTTPException, status

class InteractionService:
    def __init__(self, db: Session):
        self.interaction_repo = InteractionRepository(db)
        self.customer_repo = CustomerRepository(db)

    def log_interaction(self, interaction_data: InteractionCreate) -> Interaction:
        """
        Logs a new raw interaction string (transcript/email) after validating the customer profile exists.
        """
        # Business Rule: Prevent orphan interactions by verifying the customer profile first
        customer = self.customer_repo.get_by_id(interaction_data.customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cannot log interaction. Customer ID {interaction_data.customer_id} does not exist."
            )
        
        return self.interaction_repo.create(interaction_data)

    def get_interaction_details(self, interaction_id: int) -> Interaction:
        """
        Retrieves a single interaction context log.
        """
        interaction = self.interaction_repo.get_by_id(interaction_id)
        if not interaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interaction ID {interaction_id} not found."
            )
        return interaction

    def get_customer_history(self, customer_id: int) -> list[Interaction]:
        """
        Gathers all chronological interaction touchpoints for a specific customer.
        """
        # Verify customer validity first
        customer = self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer ID {customer_id} not found."
            )
            
        return self.interaction_repo.get_by_customer(customer_id)