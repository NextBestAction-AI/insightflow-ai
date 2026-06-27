from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class InteractionBase(BaseModel):
    """Base interaction schema with common fields."""
    customer_id: int = Field(..., gt=0, description="Customer ID")
    type: str = Field(..., min_length=1, max_length=50, description="Interaction type (email, call, meeting, etc.)")
    content: str = Field(..., min_length=1, description="Interaction content")


class InteractionCreate(InteractionBase):
    """Schema for creating a new interaction."""
    pass


class InteractionUpdate(BaseModel):
    """Schema for updating an interaction."""
    type: Optional[str] = Field(None, min_length=1, max_length=50)
    content: Optional[str] = Field(None, min_length=1)


class InteractionResponse(InteractionBase):
    """Schema for interaction response."""
    id: int = Field(..., description="Interaction ID")
    created_at: datetime = Field(..., description="Interaction creation timestamp")

    class Config:
        from_attributes = True


class InteractionListResponse(BaseModel):
    """Schema for interaction list response with pagination."""
    total: int = Field(..., ge=0, description="Total number of interactions")
    items: list[InteractionResponse] = Field(..., description="List of interactions")
