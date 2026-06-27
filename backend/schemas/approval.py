from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class ApprovalBase(BaseModel):
    """Base approval schema with common fields."""
    recommendation_id: int = Field(..., gt=0, description="Recommendation ID")
    decision: Literal["approved", "rejected"] = Field(..., description="Approval decision")
    comments: Optional[str] = Field(None, max_length=1000, description="Reviewer comments")


class ApprovalCreate(ApprovalBase):
    """Schema for creating a new approval."""
    pass


class ApprovalUpdate(BaseModel):
    """Schema for updating an approval."""
    decision: Optional[Literal["approved", "rejected"]] = None
    comments: Optional[str] = Field(None, max_length=1000)


class ApprovalResponse(ApprovalBase):
    """Schema for approval response."""
    id: int = Field(..., description="Approval ID")
    reviewed_at: datetime = Field(..., description="Review timestamp")

    class Config:
        from_attributes = True


class ApprovalListResponse(BaseModel):
    """Schema for approval list response."""
    total: int = Field(..., ge=0, description="Total number of approvals")
    approved: int = Field(..., ge=0, description="Number of approved recommendations")
    rejected: int = Field(..., ge=0, description="Number of rejected recommendations")
    items: list[ApprovalResponse] = Field(..., description="List of approvals")
