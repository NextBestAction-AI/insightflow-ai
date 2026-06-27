from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class DecisionEnum(str, Enum):
    APPROVED = "Approved"
    REJECTED = "Rejected"
    MODIFIED = "Modified"

class ApprovalBase(BaseModel):
    recommendation_id: int
    decision: DecisionEnum
    comments: Optional[str] = None

class ApprovalCreate(ApprovalBase):
    pass

class ApprovalResponse(ApprovalBase):
    id: int
    reviewed_at: datetime

    class Config:
        from_attributes = True