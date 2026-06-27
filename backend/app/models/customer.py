from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.mysql import Base


class Customer(Base):

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)

    company_name = Column(String(200), nullable=False)

    contact_person = Column(String(100))

    email = Column(String(200), unique=True)

    industry = Column(String(100))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interactions = relationship(
        "Interaction",
        back_populates="customer",
        cascade="all, delete"
    )