"""
Pydantic schemas for customers, plans, and subscriptions.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class CreateCustomerRequest(BaseModel):
    email: EmailStr
    name: str


class SubscribeRequest(BaseModel):
    plan_id: uuid.UUID


class CancelSubscriptionRequest(BaseModel):
    reason: Optional[str] = None


class ChangePlanRequest(BaseModel):
    new_plan_id: uuid.UUID


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class CustomerResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    org_id: Optional[uuid.UUID] = None
    email: str
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanResponse(BaseModel):
    id: uuid.UUID
    product: str
    name: str
    slug: str
    description: Optional[str] = None
    price_amount: float
    price_currency: str
    billing_interval: str
    trial_days: int
    is_active: bool
    sort_order: int
    features: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    plan_id: uuid.UUID
    product: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    trial_end: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
