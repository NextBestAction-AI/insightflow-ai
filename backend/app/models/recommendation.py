from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.mysql import Base


class Recommendation(Base):

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)

    interaction_id = Column(Integer, ForeignKey("interactions.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)

    action = Column(String(255))
    confidence = Column(Float)
    reason = Column(Text)

    priority = Column(String(50))
    status = Column(String(30), default="Pending")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interaction = relationship("Interaction", back_populates="recommendations")
    approvals = relationship("Approval", back_populates="recommendation", cascade="all, delete")