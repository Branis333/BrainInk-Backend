from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InitiateSubscriptionRequest(BaseModel):
    amount: float = 5.0
    currency: str = "USD"
    interval: str = "monthly"


class InitiateSubscriptionResponse(BaseModel):
    checkoutUrl: str
    paymentReference: str


class VerifyRequest(BaseModel):
    reference: str


class SubscriptionStatus(BaseModel):
    active: bool
    expiresAt: Optional[datetime] = None
    lastPaymentId: Optional[str] = None
