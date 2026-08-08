from pydantic import BaseModel
from datetime import datetime
from typing import List

class EventCreate(BaseModel):
    event_id: str
    event_type: str
    transaction_id: str
    merchant_id: str
    merchant_name: str
    amount: float
    currency: str
    timestamp: datetime

class EventResponse(BaseModel):
    id: str
    event_type: str
    timestamp: datetime

    class Config:
        from_attributes = True

class TransactionResponse(BaseModel):
    id: str
    merchant_id: str
    amount: float
    currency: str
    status: str
    created_at: datetime
    events: List[EventResponse] = []

    class Config:
        from_attributes = True
