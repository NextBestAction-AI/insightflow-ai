from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from database.base import Base


class Approval(Base):
    """SQLAlchemy model for approvals table."""

    __tablename__ = "approvals"
    __table_args__ = (
        Index("idx_recommendation_id", "recommendation_id"),
        Index("idx_reviewed_at", "reviewed_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, unique=True)
    decision = Column(String(20), nullable=False)  # approved, rejected
    comments = Column(Text, nullable=True)  # Optional reviewer comments
    reviewed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Approval(id={self.id}, recommendation_id={self.recommendation_id}, decision={self.decision})>"
