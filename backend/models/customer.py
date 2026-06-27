from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index
from database.base import Base


class Customer(Base):
    """SQLAlchemy model for customers table."""

    __tablename__ = "customers"
    __table_args__ = (
        Index("idx_email", "email"),
        Index("idx_company", "company"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False, index=True)
    industry = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name={self.name}, email={self.email})>"
