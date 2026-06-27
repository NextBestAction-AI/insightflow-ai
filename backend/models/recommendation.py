from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Index
from database.base import Base


class Recommendation(Base):
    """SQLAlchemy model for recommendations table."""

    __tablename__ = "recommendations"
    __table_args__ = (
        Index("idx_interaction_id", "interaction_id"),
        Index("idx_customer_id", "customer_id"),
        Index("idx_status", "status"),
        Index("idx_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    interaction_id = Column(Integer, ForeignKey("interactions.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(255), nullable=False)  # Recommended action
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    reason = Column(Text, nullable=False)  # Explanation for the recommendation
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected, executed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Recommendation(id={self.id}, interaction_id={self.interaction_id}, status={self.status})>"
