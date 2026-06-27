from sqlalchemy import *
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.mysql import Base


class Approval(Base):

    __tablename__="approvals"

    id=Column(Integer,primary_key=True,index=True)

    recommendation_id=Column(
        Integer,
        ForeignKey("recommendations.id")
    )

    decision=Column(String(30))

    comments=Column(Text)

    reviewed_at=Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    recommendation=relationship(
        "Recommendation",
        back_populates="approvals"
    )