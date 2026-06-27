from sqlalchemy.orm import Session
from sqlalchemy import select, func
from models.recommendation import Recommendation
from models.interaction import Interaction
from models.customer import Customer
from schemas.recommendation import RecommendationCreate, RecommendationUpdate, BulkRecommendationCreate
from config.logging import get_logger
from fastapi import HTTPException

logger = get_logger(__name__)


class RecommendationService:
    """Service layer for recommendation operations."""

    @staticmethod
    def create_recommendation(session: Session, rec_data: RecommendationCreate) -> Recommendation:
        """Create a new recommendation."""
        try:
            # Verify interaction exists
            interaction = session.execute(
                select(Interaction).where(Interaction.id == rec_data.interaction_id)
            ).scalar_one_or_none()

            if not interaction:
                logger.warning(f"Interaction {rec_data.interaction_id} not found")
                raise HTTPException(status_code=404, detail="Interaction not found")

            # Verify customer exists
            customer = session.execute(
                select(Customer).where(Customer.id == rec_data.customer_id)
            ).scalar_one_or_none()

            if not customer:
                logger.warning(f"Customer {rec_data.customer_id} not found")
                raise HTTPException(status_code=404, detail="Customer not found")

            recommendation = Recommendation(
                interaction_id=rec_data.interaction_id,
                customer_id=rec_data.customer_id,
                action=rec_data.action,
                confidence=rec_data.confidence,
                reason=rec_data.reason,
                status=rec_data.status or "pending",
            )
            session.add(recommendation)
            session.commit()
            session.refresh(recommendation)
            logger.info(f"Recommendation created: {recommendation.id}")
            return recommendation
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create recommendation: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create recommendation")

    @staticmethod
    def create_bulk_recommendations(session: Session, bulk_data: BulkRecommendationCreate) -> list[Recommendation]:
        """Create multiple recommendations."""
        created_recommendations = []
        try:
            for rec_data in bulk_data.recommendations:
                recommendation = RecommendationService.create_recommendation(session, rec_data)
                created_recommendations.append(recommendation)
            
            logger.info(f"Created {len(created_recommendations)} recommendations")
            return created_recommendations
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create bulk recommendations: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create recommendations")

    @staticmethod
    def get_recommendation_by_id(session: Session, recommendation_id: int) -> Recommendation:
        """Get a recommendation by ID."""
        recommendation = session.execute(
            select(Recommendation).where(Recommendation.id == recommendation_id)
        ).scalar_one_or_none()

        if not recommendation:
            logger.warning(f"Recommendation {recommendation_id} not found")
            raise HTTPException(status_code=404, detail="Recommendation not found")

        return recommendation

    @staticmethod
    def get_recommendations_by_customer(session: Session, customer_id: int, skip: int = 0, limit: int = 100) -> tuple[list[Recommendation], int]:
        """Get all recommendations for a customer."""
        # Verify customer exists
        customer = session.execute(
            select(Customer).where(Customer.id == customer_id)
        ).scalar_one_or_none()

        if not customer:
            logger.warning(f"Customer {customer_id} not found")
            raise HTTPException(status_code=404, detail="Customer not found")

        total = session.execute(
            select(func.count()).select_from(Recommendation).where(Recommendation.customer_id == customer_id)
        ).scalar()

        recommendations = session.execute(
            select(Recommendation).where(Recommendation.customer_id == customer_id).order_by(Recommendation.created_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(recommendations)} recommendations for customer {customer_id}")
        return recommendations, total

    @staticmethod
    def get_recommendations_by_interaction(session: Session, interaction_id: int, skip: int = 0, limit: int = 100) -> tuple[list[Recommendation], int]:
        """Get all recommendations for an interaction."""
        total = session.execute(
            select(func.count()).select_from(Recommendation).where(Recommendation.interaction_id == interaction_id)
        ).scalar()

        recommendations = session.execute(
            select(Recommendation).where(Recommendation.interaction_id == interaction_id).order_by(Recommendation.created_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(recommendations)} recommendations for interaction {interaction_id}")
        return recommendations, total

    @staticmethod
    def get_pending_recommendations(session: Session, skip: int = 0, limit: int = 100) -> tuple[list[Recommendation], int]:
        """Get all pending recommendations."""
        total = session.execute(
            select(func.count()).select_from(Recommendation).where(Recommendation.status == "pending")
        ).scalar()

        recommendations = session.execute(
            select(Recommendation).where(Recommendation.status == "pending").order_by(Recommendation.confidence.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(recommendations)} pending recommendations")
        return recommendations, total

    @staticmethod
    def get_recommendations_by_status(session: Session, status: str, skip: int = 0, limit: int = 100) -> tuple[list[Recommendation], int]:
        """Get recommendations by status."""
        if status not in ["pending", "approved", "rejected", "executed"]:
            raise HTTPException(status_code=400, detail="Invalid status")

        total = session.execute(
            select(func.count()).select_from(Recommendation).where(Recommendation.status == status)
        ).scalar()

        recommendations = session.execute(
            select(Recommendation).where(Recommendation.status == status).order_by(Recommendation.created_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(recommendations)} recommendations with status {status}")
        return recommendations, total

    @staticmethod
    def get_all_recommendations(session: Session, skip: int = 0, limit: int = 100) -> tuple[list[Recommendation], int]:
        """Get all recommendations."""
        total = session.execute(select(func.count()).select_from(Recommendation)).scalar()
        recommendations = session.execute(
            select(Recommendation).order_by(Recommendation.created_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(recommendations)} recommendations (total: {total})")
        return recommendations, total

    @staticmethod
    def update_recommendation(session: Session, recommendation_id: int, rec_data: RecommendationUpdate) -> Recommendation:
        """Update a recommendation."""
        try:
            recommendation = session.execute(
                select(Recommendation).where(Recommendation.id == recommendation_id)
            ).scalar_one_or_none()

            if not recommendation:
                logger.warning(f"Recommendation {recommendation_id} not found for update")
                raise HTTPException(status_code=404, detail="Recommendation not found")

            # Update only provided fields
            update_data = rec_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(recommendation, field, value)

            session.commit()
            session.refresh(recommendation)
            logger.info(f"Recommendation {recommendation_id} updated")
            return recommendation
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update recommendation {recommendation_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update recommendation")

    @staticmethod
    def delete_recommendation(session: Session, recommendation_id: int) -> None:
        """Delete a recommendation."""
        try:
            recommendation = session.execute(
                select(Recommendation).where(Recommendation.id == recommendation_id)
            ).scalar_one_or_none()

            if not recommendation:
                logger.warning(f"Recommendation {recommendation_id} not found for deletion")
                raise HTTPException(status_code=404, detail="Recommendation not found")

            session.delete(recommendation)
            session.commit()
            logger.info(f"Recommendation {recommendation_id} deleted")
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete recommendation {recommendation_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete recommendation")
