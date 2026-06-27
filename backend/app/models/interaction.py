from sqlalchemy import Column,Integer,String,Text,ForeignKey,DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.mysql import Base


class Interaction(Base):

    __tablename__="interactions"

    id=Column(Integer,primary_key=True,index=True)

    customer_id=Column(Integer,ForeignKey("customers.id"))

    interaction_type=Column(String(50))

    content=Column(Text)

    summary=Column(Text)

    sentiment=Column(String(50))

    created_at=Column(DateTime(timezone=True),server_default=func.now())

    customer=relationship("Customer",back_populates="interactions")

    recommendations=relationship(
        "Recommendation",
        back_populates="interaction",
        cascade="all, delete"
    )