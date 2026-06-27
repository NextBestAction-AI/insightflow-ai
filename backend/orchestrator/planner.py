"""
Backend workflow planner for recommendation processing and approval workflows.

This module handles workflow planning for recommendations and approvals,
NOT AI-driven planning (which is handled by the AI team).

It manages:
- Recommendation workflow transitions
- Approval request generation
- Status progression workflows
"""

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from models.recommendation import Recommendation
from models.approval import Approval
from config.logging import get_logger
from fastapi import HTTPException

logger = get_logger(__name__)


class WorkflowPlanner:
    """Backend workflow planning for recommendations and approvals."""

    @staticmethod
    def submit_recommendations_for_review(session: Session, recommendation_ids: list[int]) -> dict:
        """Submit multiple recommendations for review workflow."""
        try:
            recommendations = session.execute(
                select(Recommendation).where(Recommendation.id.in_(recommendation_ids)).where(Recommendation.status == "pending")
            ).scalars().all()

            if not recommendations:
                logger.warning("No pending recommendations found for review submission")
                raise HTTPException(status_code=400, detail="No pending recommendations to submit")

            # Transition recommendations to 'pending' status (already are, so this is a no-op)
            # In a real scenario, this might trigger notifications to reviewers
            for rec in recommendations:
                rec.status = "pending"

            session.commit()
            logger.info(f"Submitted {len(recommendations)} recommendations for review")

            return {
                "submitted_count": len(recommendations),
                "ids": [r.id for r in recommendations],
                "submitted_at": datetime.utcnow(),
            }
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to submit recommendations for review: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to submit recommendations")

    @staticmethod
    def get_pending_approvals_count(session: Session) -> dict:
        """Get count of pending approvals."""
        try:
            pending_count = session.execute(
                select(Recommendation).where(Recommendation.status == "pending")
            ).scalars().all()

            approved_count = session.execute(
                select(Recommendation).where(Recommendation.status == "approved")
            ).scalars().all()

            rejected_count = session.execute(
                select(Recommendation).where(Recommendation.status == "rejected")
            ).scalars().all()

            return {
                "pending": len(pending_count),
                "approved": len(approved_count),
                "rejected": len(rejected_count),
                "total": len(pending_count) + len(approved_count) + len(rejected_count),
            }
        except Exception as e:
            logger.error(f"Failed to get approval counts: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to get approval counts")

    @staticmethod
    def bulk_update_recommendation_status(
        session: Session, recommendation_ids: list[int], new_status: str
    ) -> dict:
        """Bulk update recommendation statuses."""
        if new_status not in ["pending", "approved", "rejected", "executed"]:
            raise HTTPException(status_code=400, detail="Invalid status")

        try:
            recommendations = session.execute(
                select(Recommendation).where(Recommendation.id.in_(recommendation_ids))
            ).scalars().all()

            if not recommendations:
                logger.warning(f"No recommendations found for bulk update")
                raise HTTPException(status_code=400, detail="No recommendations found")

            for rec in recommendations:
                rec.status = new_status

            session.commit()
            logger.info(f"Updated {len(recommendations)} recommendations to status {new_status}")

            return {
                "updated_count": len(recommendations),
                "new_status": new_status,
                "updated_at": datetime.utcnow(),
            }
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to bulk update recommendations: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update recommendations")
