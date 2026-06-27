from sqlalchemy.orm import Session
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.reccomendation_repository import RecommendationRepository
from app.schemas.approval import ApprovalCreate, DecisionEnum
from app.models.approval import Approval
from fastapi import HTTPException, status

class ApprovalService:
    def __init__(self, db: Session):
        self.approval_repo = ApprovalRepository(db)
        self.recommendation_repo = RecommendationRepository(db)

    def process_approval(self, approval_data: ApprovalCreate) -> Approval:
        """
        Logs a human decision and updates the corresponding recommendation's status.
        """
        # 1. Verify the recommendation actually exists
        recommendation = self.recommendation_repo.get_by_id(approval_data.recommendation_id)
        if not recommendation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation ID {approval_data.recommendation_id} not found."
            )

        # 2. Prevent overriding an already finalized recommendation
        if recommendation.status != "Pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Recommendation has already been processed with status: {recommendation.status}."
            )

        # 3. Create the historical approval audit log
        new_approval = self.approval_repo.create(approval_data)

        # 4. Sync and update the recommendation state map
        # Maps the DecisionEnum values ('Approved', 'Rejected', 'Modified') directly to the recommendation status
        self.recommendation_repo.update_status(
            recommendation_id=approval_data.recommendation_id,
            status=approval_data.decision.value
        )

        return new_approval

    def get_approval_log(self, approval_id: int) -> Approval:
        """
        Retrieves a single approval audit record.
        """
        approval = self.approval_repo.get_by_id(approval_id)
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval log entry {approval_id} not found."
            )
        return approval

    def get_approval_by_recommendation(self, recommendation_id: int) -> Approval:
        """
        Retrieves the audit trail for a specific recommendation.
        """
        approval = self.approval_repo.get_by_recommendation(recommendation_id)
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No decision log found for Recommendation ID {recommendation_id}."
            )
        return approval