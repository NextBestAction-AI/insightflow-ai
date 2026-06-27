from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class RecommendationBase(BaseModel):
    interaction_id: int
    customer_id: int
    action: str
    confidence: float = Field(..., ge=0.0, le=100.0)
    reason: str
    status: Optional[str] = "Pending"

class RecommendationCreate(RecommendationBase):
    pass

class RecommendationResponse(RecommendationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True