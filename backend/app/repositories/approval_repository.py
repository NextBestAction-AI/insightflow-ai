from sqlalchemy.orm import Session
from app.models.approval import Approval
from app.schemas.approval import ApprovalCreate

class ApprovalRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, approval: ApprovalCreate) -> Approval:
        db_approval = Approval(**approval.model_dump())
        self.db.add(db_approval)
        self.db.commit()
        self.db.refresh(db_approval)
        return db_approval

    def get_by_id(self, approval_id: int) -> Approval | None:
        return self.db.query(Approval).filter(Approval.id == approval_id).first()

    def get_by_recommendation(self, recommendation_id: int) -> Approval | None:
        return self.db.query(Approval).filter(Approval.recommendation_id == recommendation_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Approval]:
        return self.db.query(Approval).offset(skip).limit(limit).all()