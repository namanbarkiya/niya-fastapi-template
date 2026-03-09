"""
Pydantic schemas for payment methods and transactions.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class AddPaymentMethodRequest(BaseModel):
    type: str
    last_four: Optional[str] = None
    brand: Optional[str] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class PaymentMethodResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    type: str
    last_four: Optional[str] = None
    brand: Optional[str] = None
    is_default: bool
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    subscription_id: Optional[uuid.UUID] = None
    amount: float
    currency: str
    status: str
    payment_method_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
