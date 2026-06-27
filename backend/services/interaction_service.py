from sqlalchemy.orm import Session
from sqlalchemy import select, func
from models.interaction import Interaction
from models.customer import Customer
from schemas.interaction import InteractionCreate, InteractionUpdate
from config.logging import get_logger
from fastapi import HTTPException

logger = get_logger(__name__)


class InteractionService:
    """Service layer for interaction operations."""

    @staticmethod
    def create_interaction(session: Session, interaction_data: InteractionCreate) -> Interaction:
        """Create a new interaction."""
        try:
            # Verify customer exists
            customer = session.execute(
                select(Customer).where(Customer.id == interaction_data.customer_id)
            ).scalar_one_or_none()

            if not customer:
                logger.warning(f"Customer {interaction_data.customer_id} not found")
                raise HTTPException(status_code=404, detail="Customer not found")

            interaction = Interaction(
                customer_id=interaction_data.customer_id,
                type=interaction_data.type,
                content=interaction_data.content,
            )
            session.add(interaction)
            session.commit()
            session.refresh(interaction)
            logger.info(f"Interaction created: {interaction.id} for customer {interaction_data.customer_id}")
            return interaction
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create interaction: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create interaction")

    @staticmethod
    def get_interaction_by_id(session: Session, interaction_id: int) -> Interaction:
        """Get an interaction by ID."""
        interaction = session.execute(
            select(Interaction).where(Interaction.id == interaction_id)
        ).scalar_one_or_none()

        if not interaction:
            logger.warning(f"Interaction {interaction_id} not found")
            raise HTTPException(status_code=404, detail="Interaction not found")

        return interaction

    @staticmethod
    def get_interactions_by_customer(session: Session, customer_id: int, skip: int = 0, limit: int = 100) -> tuple[list[Interaction], int]:
        """Get all interactions for a customer."""
        # Verify customer exists
        customer = session.execute(
            select(Customer).where(Customer.id == customer_id)
        ).scalar_one_or_none()

        if not customer:
            logger.warning(f"Customer {customer_id} not found")
            raise HTTPException(status_code=404, detail="Customer not found")

        total = session.execute(
            select(func.count()).select_from(Interaction).where(Interaction.customer_id == customer_id)
        ).scalar()

        interactions = session.execute(
            select(Interaction).where(Interaction.customer_id == customer_id).order_by(Interaction.created_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(interactions)} interactions for customer {customer_id}")
        return interactions, total

    @staticmethod
    def get_all_interactions(session: Session, skip: int = 0, limit: int = 100) -> tuple[list[Interaction], int]:
        """Get all interactions."""
        total = session.execute(select(func.count()).select_from(Interaction)).scalar()
        interactions = session.execute(
            select(Interaction).order_by(Interaction.created_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(interactions)} interactions (total: {total})")
        return interactions, total

    @staticmethod
    def get_interactions_by_type(session: Session, interaction_type: str, skip: int = 0, limit: int = 100) -> tuple[list[Interaction], int]:
        """Get interactions by type."""
        total = session.execute(
            select(func.count()).select_from(Interaction).where(Interaction.type == interaction_type)
        ).scalar()

        interactions = session.execute(
            select(Interaction).where(Interaction.type == interaction_type).order_by(Interaction.created_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(interactions)} interactions of type {interaction_type}")
        return interactions, total

    @staticmethod
    def update_interaction(session: Session, interaction_id: int, interaction_data: InteractionUpdate) -> Interaction:
        """Update an interaction."""
        try:
            interaction = session.execute(
                select(Interaction).where(Interaction.id == interaction_id)
            ).scalar_one_or_none()

            if not interaction:
                logger.warning(f"Interaction {interaction_id} not found for update")
                raise HTTPException(status_code=404, detail="Interaction not found")

            # Update only provided fields
            update_data = interaction_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(interaction, field, value)

            session.commit()
            session.refresh(interaction)
            logger.info(f"Interaction {interaction_id} updated")
            return interaction
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update interaction {interaction_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update interaction")

    @staticmethod
    def delete_interaction(session: Session, interaction_id: int) -> None:
        """Delete an interaction."""
        try:
            interaction = session.execute(
                select(Interaction).where(Interaction.id == interaction_id)
            ).scalar_one_or_none()

            if not interaction:
                logger.warning(f"Interaction {interaction_id} not found for deletion")
                raise HTTPException(status_code=404, detail="Interaction not found")

            session.delete(interaction)
            session.commit()
            logger.info(f"Interaction {interaction_id} deleted")
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete interaction {interaction_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete interaction")
