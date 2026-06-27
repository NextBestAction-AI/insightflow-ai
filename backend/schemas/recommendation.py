from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class RecommendationBase(BaseModel):
    """Base recommendation schema with common fields."""
    interaction_id: int = Field(..., gt=0, description="Interaction ID")
    customer_id: int = Field(..., gt=0, description="Customer ID")
    action: str = Field(..., min_length=1, max_length=255, description="Recommended action")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    reason: str = Field(..., min_length=1, description="Reason for the recommendation")


class RecommendationCreate(RecommendationBase):
    """Schema for creating a new recommendation."""
    status: Optional[Literal["pending", "approved", "rejected", "executed"]] = Field("pending", description="Initial status")


class RecommendationUpdate(BaseModel):
    """Schema for updating a recommendation."""
    action: Optional[str] = Field(None, min_length=1, max_length=255)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    reason: Optional[str] = Field(None, min_length=1)
    status: Optional[Literal["pending", "approved", "rejected", "executed"]] = None


class RecommendationResponse(RecommendationBase):
    """Schema for recommendation response."""
    id: int = Field(..., description="Recommendation ID")
    status: str = Field(..., description="Current status")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True


class RecommendationListResponse(BaseModel):
    """Schema for recommendation list response."""
    total: int = Field(..., ge=0, description="Total number of recommendations")
    pending: int = Field(..., ge=0, description="Number of pending recommendations")
    items: list[RecommendationResponse] = Field(..., description="List of recommendations")


class BulkRecommendationCreate(BaseModel):
    """Schema for creating multiple recommendations at once."""
    recommendations: list[RecommendationCreate] = Field(..., min_items=1, max_items=100, description="List of recommendations to create")
