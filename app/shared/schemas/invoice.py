"""
Pydantic schemas for invoices and invoice items.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class InvoiceItemResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    description: str
    quantity: int
    unit_price: float
    amount: float
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    subscription_id: Optional[uuid.UUID] = None
    invoice_number: str
    status: str
    subtotal: float
    tax: float
    total: float
    currency: str
    issued_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceDetailResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    subscription_id: Optional[uuid.UUID] = None
    invoice_number: str
    status: str
    subtotal: float
    tax: float
    total: float
    currency: str
    issued_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    created_at: datetime
    items: List[InvoiceItemResponse]

    model_config = {"from_attributes": True}
