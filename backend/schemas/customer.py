from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class CustomerBase(BaseModel):
    """Base customer schema with common fields."""
    name: str = Field(..., min_length=1, max_length=255, description="Customer name")
    company: str = Field(..., min_length=1, max_length=255, description="Company name")
    industry: str = Field(..., min_length=1, max_length=100, description="Industry")
    email: EmailStr = Field(..., description="Customer email address")


class CustomerCreate(CustomerBase):
    """Schema for creating a new customer."""
    pass


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None


class CustomerResponse(CustomerBase):
    """Schema for customer response."""
    id: int = Field(..., description="Customer ID")
    created_at: datetime = Field(..., description="Customer creation timestamp")

    class Config:
        from_attributes = True
