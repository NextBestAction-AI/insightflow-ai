from pydantic import BaseModel
from datetime import datetime

class InteractionBase(BaseModel):
    customer_id: int
    type: str  # 'email', 'transcript', etc.
    content: str

class InteractionCreate(InteractionBase):
    pass

class InteractionResponse(InteractionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True