"""
Billing routes: plans, subscriptions, payments, invoices, webhooks.
"""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_product, get_current_user
from app.core.exceptions import AuthenticationError, ValidationError
from app.shared.models.user import User
from app.shared.schemas.billing import (
    CancelSubscriptionRequest,
    ChangePlanRequest,
    CustomerResponse,
    PlanResponse,
    SubscribeRequest,
    SubscriptionResponse,
)
from app.shared.schemas.invoice import InvoiceDetailResponse, InvoiceResponse
from app.shared.schemas.payment import (
    AddPaymentMethodRequest,
    PaymentMethodResponse,
    TransactionResponse,
)
from app.shared.services.billing_service import BillingService
from app.shared.services.payment_provider import PaymentProvider

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_provider(product: str | None = None) -> PaymentProvider:
    """Resolve payment provider for a product. Defaults to settings.default_payment_provider."""
    provider_name = settings.default_payment_provider
    if product and settings.product_payment_providers:
        provider_name = settings.product_payment_providers.get(product, provider_name)

    if provider_name == "razorpay":
        from app.shared.services.razorpay_provider import RazorpayProvider

        return RazorpayProvider()
    # Future: elif provider_name == "stripe": ...
    raise ValidationError(f"Unknown payment provider: {provider_name}")


def _billing_service(
    db: AsyncSession, product: str | None = None
) -> BillingService:
    return BillingService(db, _get_provider(product))


# ------------------------------------------------------------------
# Plans
# ------------------------------------------------------------------
@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    product: str = Depends(get_current_product),
):
    svc = _billing_service(db, product)
    return await svc.list_plans(product)


# ------------------------------------------------------------------
# Subscription
# ------------------------------------------------------------------
@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    product: str = Depends(get_current_product),
):
    from app.shared.repos.customer_repo import CustomerRepo
    from app.shared.repos.subscription_repo import SubscriptionRepo

    customer = await CustomerRepo(db).get_by_user_id(current_user.id)
    if not customer:
        raise ValidationError("No customer record found")
    sub = await SubscriptionRepo(db).get_by_customer_and_product(
        customer.id, product
    )
    if not sub:
        raise ValidationError("No subscription found for this product")
    return SubscriptionResponse.model_validate(sub)


@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe(
    payload: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    product: str = Depends(get_current_product),
):
    svc = _billing_service(db, product)
    return await svc.subscribe(current_user.id, payload.plan_id, product)


@router.post("/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    payload: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    product: str = Depends(get_current_product),
):
    svc = _billing_service(db, product)
    return await svc.cancel(current_user.id, product, payload.reason)


@router.post("/change-plan", response_model=SubscriptionResponse)
async def change_plan(
    payload: ChangePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    product: str = Depends(get_current_product),
):
    svc = _billing_service(db, product)
    return await svc.change_plan(current_user.id, payload.new_plan_id, product)


# ------------------------------------------------------------------
# Webhooks
# ------------------------------------------------------------------
@router.post("/webhook/{provider}")
async def webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    payment_provider = _get_provider()

    # Verify signature
    if signature:
        valid = await payment_provider.verify_webhook_signature(
            body, signature
        )
        if not valid:
            raise AuthenticationError("Invalid webhook signature")

    payload = body.decode()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON payload")

    event_id = data.get("event_id") or data.get("id") or ""
    event_type = data.get("event") or data.get("type") or "unknown"

    svc = BillingService(db, payment_provider)
    result = await svc.handle_webhook(provider, event_id, event_type, payload)
    return result


# ------------------------------------------------------------------
# Invoices
# ------------------------------------------------------------------
@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _billing_service(db)
    return await svc.list_invoices(current_user.id)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _billing_service(db)
    return await svc.get_invoice_detail(invoice_id)


# ------------------------------------------------------------------
# Payment methods
# ------------------------------------------------------------------
@router.get("/payment-methods", response_model=list[PaymentMethodResponse])
async def list_payment_methods(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _billing_service(db)
    return await svc.list_payment_methods(current_user.id)


@router.post(
    "/payment-methods", response_model=PaymentMethodResponse, status_code=201
)
async def add_payment_method(
    payload: AddPaymentMethodRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _billing_service(db)
    return await svc.add_payment_method(
        current_user.id, payload.type, payload.last_four, payload.brand
    )


@router.delete("/payment-methods/{method_id}")
async def delete_payment_method(
    method_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _billing_service(db)
    return await svc.delete_payment_method(current_user.id, method_id)


# ------------------------------------------------------------------
# Transactions
# ------------------------------------------------------------------
@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _billing_service(db)
    return await svc.list_transactions(current_user.id)
