from sqlalchemy.orm import Session
from sqlalchemy import select, func
from models.approval import Approval
from models.recommendation import Recommendation
from schemas.approval import ApprovalCreate, ApprovalUpdate
from config.logging import get_logger
from fastapi import HTTPException

logger = get_logger(__name__)


class ApprovalService:
    """Service layer for approval operations."""

    @staticmethod
    def create_approval(session: Session, approval_data: ApprovalCreate) -> Approval:
        """Create a new approval."""
        try:
            # Verify recommendation exists
            recommendation = session.execute(
                select(Recommendation).where(Recommendation.id == approval_data.recommendation_id)
            ).scalar_one_or_none()

            if not recommendation:
                logger.warning(f"Recommendation {approval_data.recommendation_id} not found")
                raise HTTPException(status_code=404, detail="Recommendation not found")

            # Check if approval already exists for this recommendation
            existing = session.execute(
                select(Approval).where(Approval.recommendation_id == approval_data.recommendation_id)
            ).scalar_one_or_none()

            if existing:
                logger.warning(f"Approval already exists for recommendation {approval_data.recommendation_id}")
                raise HTTPException(status_code=400, detail="Approval already exists for this recommendation")

            # Update recommendation status based on decision
            recommendation.status = "approved" if approval_data.decision == "approved" else "rejected"

            approval = Approval(
                recommendation_id=approval_data.recommendation_id,
                decision=approval_data.decision,
                comments=approval_data.comments,
            )
            session.add(approval)
            session.commit()
            session.refresh(approval)
            logger.info(f"Approval created: {approval.id} with decision {approval_data.decision}")
            return approval
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create approval: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create approval")

    @staticmethod
    def get_approval_by_id(session: Session, approval_id: int) -> Approval:
        """Get an approval by ID."""
        approval = session.execute(
            select(Approval).where(Approval.id == approval_id)
        ).scalar_one_or_none()

        if not approval:
            logger.warning(f"Approval {approval_id} not found")
            raise HTTPException(status_code=404, detail="Approval not found")

        return approval

    @staticmethod
    def get_approval_by_recommendation_id(session: Session, recommendation_id: int) -> Approval:
        """Get an approval by recommendation ID."""
        approval = session.execute(
            select(Approval).where(Approval.recommendation_id == recommendation_id)
        ).scalar_one_or_none()

        if not approval:
            logger.warning(f"Approval for recommendation {recommendation_id} not found")
            raise HTTPException(status_code=404, detail="Approval not found")

        return approval

    @staticmethod
    def get_all_approvals(session: Session, skip: int = 0, limit: int = 100) -> tuple[list[Approval], int]:
        """Get all approvals."""
        total = session.execute(select(func.count()).select_from(Approval)).scalar()
        approvals = session.execute(
            select(Approval).order_by(Approval.reviewed_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(approvals)} approvals (total: {total})")
        return approvals, total

    @staticmethod
    def get_approvals_by_decision(session: Session, decision: str, skip: int = 0, limit: int = 100) -> tuple[list[Approval], int]:
        """Get approvals by decision."""
        if decision not in ["approved", "rejected"]:
            raise HTTPException(status_code=400, detail="Invalid decision")

        total = session.execute(
            select(func.count()).select_from(Approval).where(Approval.decision == decision)
        ).scalar()

        approvals = session.execute(
            select(Approval).where(Approval.decision == decision).order_by(Approval.reviewed_at.desc()).offset(skip).limit(limit)
        ).scalars().all()

        logger.info(f"Retrieved {len(approvals)} approvals with decision {decision}")
        return approvals, total

    @staticmethod
    def get_approval_statistics(session: Session) -> dict:
        """Get approval statistics."""
        try:
            total = session.execute(select(func.count()).select_from(Approval)).scalar()
            approved = session.execute(
                select(func.count()).select_from(Approval).where(Approval.decision == "approved")
            ).scalar()
            rejected = session.execute(
                select(func.count()).select_from(Approval).where(Approval.decision == "rejected")
            ).scalar()

            return {
                "total_approvals": total,
                "approved": approved,
                "rejected": rejected,
                "approval_rate": (approved / total * 100) if total > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Failed to get approval statistics: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to get approval statistics")

    @staticmethod
    def update_approval(session: Session, approval_id: int, approval_data: ApprovalUpdate) -> Approval:
        """Update an approval."""
        try:
            approval = session.execute(
                select(Approval).where(Approval.id == approval_id)
            ).scalar_one_or_none()

            if not approval:
                logger.warning(f"Approval {approval_id} not found for update")
                raise HTTPException(status_code=404, detail="Approval not found")

            # Update only provided fields
            update_data = approval_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(approval, field, value)

            # Update recommendation status if decision changed
            if "decision" in update_data:
                recommendation = session.execute(
                    select(Recommendation).where(Recommendation.id == approval.recommendation_id)
                ).scalar_one_or_none()
                if recommendation:
                    recommendation.status = "approved" if update_data["decision"] == "approved" else "rejected"

            session.commit()
            session.refresh(approval)
            logger.info(f"Approval {approval_id} updated")
            return approval
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update approval {approval_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to update approval")

    @staticmethod
    def delete_approval(session: Session, approval_id: int) -> None:
        """Delete an approval."""
        try:
            approval = session.execute(
                select(Approval).where(Approval.id == approval_id)
            ).scalar_one_or_none()

            if not approval:
                logger.warning(f"Approval {approval_id} not found for deletion")
                raise HTTPException(status_code=404, detail="Approval not found")

            # Reset recommendation status to pending
            recommendation = session.execute(
                select(Recommendation).where(Recommendation.id == approval.recommendation_id)
            ).scalar_one_or_none()
            if recommendation:
                recommendation.status = "pending"

            session.delete(approval)
            session.commit()
            logger.info(f"Approval {approval_id} deleted")
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete approval {approval_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to delete approval")
