from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from database.base import Base


class Interaction(Base):
    """SQLAlchemy model for interactions table."""

    __tablename__ = "interactions"
    __table_args__ = (
        Index("idx_customer_id", "customer_id"),
        Index("idx_created_at", "created_at"),
        Index("idx_type", "type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False, index=True)  # email, call, meeting, etc.
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Interaction(id={self.id}, customer_id={self.customer_id}, type={self.type})>"
