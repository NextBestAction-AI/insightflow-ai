from datetime import datetime

from pydantic import BaseModel, EmailStr


class CustomerBase(BaseModel):
    company_name: str
    contact_person: str | None = None
    email: EmailStr
    industry: str | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerResponse(CustomerBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True