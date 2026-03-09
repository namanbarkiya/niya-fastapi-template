"""
Billing service — orchestrates subscriptions, payments, invoices.

Takes a PaymentProvider instance. Uses provider_link_repo to map between
internal IDs and provider IDs. Zero changes needed when adding a new provider.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.shared.repos.customer_repo import CustomerRepo
from app.shared.repos.invoice_repo import InvoiceRepo
from app.shared.repos.payment_repo import PaymentMethodRepo, TransactionRepo
from app.shared.repos.provider_link_repo import ProviderLinkRepo
from app.shared.repos.subscription_repo import PlanRepo, SubscriptionRepo
from app.shared.repos.webhook_repo import WebhookRepo
from app.shared.schemas.billing import (
    CustomerResponse,
    PlanResponse,
    SubscriptionResponse,
)
from app.shared.schemas.invoice import InvoiceDetailResponse, InvoiceResponse
from app.shared.schemas.payment import PaymentMethodResponse, TransactionResponse
from app.shared.services.payment_provider import PaymentProvider

logger = logging.getLogger(__name__)


class BillingService:
    def __init__(self, db: AsyncSession, provider: PaymentProvider) -> None:
        self.db = db
        self.provider = provider
        self.customer_repo = CustomerRepo(db)
        self.plan_repo = PlanRepo(db)
        self.sub_repo = SubscriptionRepo(db)
        self.payment_method_repo = PaymentMethodRepo(db)
        self.tx_repo = TransactionRepo(db)
        self.invoice_repo = InvoiceRepo(db)
        self.link_repo = ProviderLinkRepo(db)
        self.webhook_repo = WebhookRepo(db)

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------
    async def create_customer(
        self,
        user_id: uuid.UUID,
        email: str,
        name: str,
        org_id: uuid.UUID | None = None,
    ) -> CustomerResponse:
        existing = await self.customer_repo.get_by_user_id(user_id)
        if existing:
            raise ConflictError("Customer already exists for this user")

        customer = await self.customer_repo.create(
            user_id=user_id, email=email, name=name, org_id=org_id
        )

        # Create on provider
        result = await self.provider.create_customer(name=name, email=email)
        await self.link_repo.create(
            entity_type="customer",
            entity_id=customer.id,
            provider=self._provider_name,
            provider_id=result["provider_id"],
        )

        logger.info(f"Customer created: {customer.id}")
        return CustomerResponse.model_validate(customer)

    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------
    async def list_plans(self, product: str) -> list[PlanResponse]:
        plans = await self.plan_repo.list_active_by_product(product)
        return [PlanResponse.model_validate(p) for p in plans]

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------
    async def subscribe(
        self,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        product: str,
    ) -> SubscriptionResponse:
        customer = await self.customer_repo.get_by_user_id(user_id)
        if not customer:
            raise NotFoundError("Customer not found. Create a customer first.")

        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan or not plan.is_active:
            raise NotFoundError("Plan not found or inactive")
        if plan.product != product:
            raise ValidationError("Plan does not belong to this product")

        # Check for existing active subscription
        existing = await self.sub_repo.get_by_customer_and_product(
            customer.id, product
        )
        if existing and existing.status in ("active", "trialing"):
            raise ConflictError("Already subscribed to this product")

        # Resolve provider IDs
        customer_link = await self.link_repo.get(
            "customer", customer.id, self._provider_name
        )
        plan_link = await self.link_repo.get(
            "plan", plan.id, self._provider_name
        )

        provider_result = None
        if customer_link and plan_link:
            provider_result = await self.provider.create_subscription(
                provider_customer_id=customer_link.provider_id,
                provider_plan_id=plan_link.provider_id,
            )

        now = datetime.now(timezone.utc)
        status = "trialing" if plan.trial_days > 0 else "active"
        from dateutil.relativedelta import relativedelta  # type: ignore

        if plan.billing_interval == "monthly":
            period_end = now + relativedelta(months=1)
        else:
            period_end = now + relativedelta(years=1)

        trial_end = None
        if plan.trial_days > 0:
            from datetime import timedelta

            trial_end = now + timedelta(days=plan.trial_days)

        subscription = await self.sub_repo.create(
            customer_id=customer.id,
            plan_id=plan.id,
            product=product,
            status=status,
            current_period_start=now,
            current_period_end=period_end,
            trial_end=trial_end,
        )

        if provider_result:
            await self.link_repo.create(
                entity_type="subscription",
                entity_id=subscription.id,
                provider=self._provider_name,
                provider_id=provider_result["provider_id"],
            )

        logger.info(f"Subscription created: {subscription.id} for plan {plan.slug}")
        return SubscriptionResponse.model_validate(subscription)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------
    async def cancel(
        self, user_id: uuid.UUID, product: str, reason: str | None = None
    ) -> SubscriptionResponse:
        customer = await self.customer_repo.get_by_user_id(user_id)
        if not customer:
            raise NotFoundError("Customer not found")

        sub = await self.sub_repo.get_by_customer_and_product(customer.id, product)
        if not sub or sub.status not in ("active", "trialing"):
            raise NotFoundError("No active subscription found")

        # Cancel on provider
        sub_link = await self.link_repo.get(
            "subscription", sub.id, self._provider_name
        )
        if sub_link:
            await self.provider.cancel_subscription(sub_link.provider_id)

        await self.sub_repo.cancel(sub.id, reason=reason)

        sub = await self.sub_repo.get_by_id(sub.id)
        logger.info(f"Subscription canceled: {sub.id}")
        return SubscriptionResponse.model_validate(sub)

    # ------------------------------------------------------------------
    # Change plan
    # ------------------------------------------------------------------
    async def change_plan(
        self, user_id: uuid.UUID, new_plan_id: uuid.UUID, product: str
    ) -> SubscriptionResponse:
        customer = await self.customer_repo.get_by_user_id(user_id)
        if not customer:
            raise NotFoundError("Customer not found")

        sub = await self.sub_repo.get_by_customer_and_product(customer.id, product)
        if not sub or sub.status not in ("active", "trialing"):
            raise NotFoundError("No active subscription found")

        new_plan = await self.plan_repo.get_by_id(new_plan_id)
        if not new_plan or not new_plan.is_active:
            raise NotFoundError("New plan not found or inactive")
        if new_plan.product != product:
            raise ValidationError("Plan does not belong to this product")

        # Cancel old on provider and create new
        sub_link = await self.link_repo.get(
            "subscription", sub.id, self._provider_name
        )
        if sub_link:
            await self.provider.cancel_subscription(
                sub_link.provider_id, at_period_end=False
            )

        await self.sub_repo.cancel(sub.id, reason="plan_change")

        # Create new subscription
        return await self.subscribe(user_id, new_plan_id, product)

    # ------------------------------------------------------------------
    # Record payment
    # ------------------------------------------------------------------
    async def record_payment(
        self,
        customer_id: uuid.UUID,
        amount: int,
        currency: str,
        status: str = "completed",
        subscription_id: uuid.UUID | None = None,
        payment_method_id: uuid.UUID | None = None,
        description: str | None = None,
    ) -> TransactionResponse:
        tx = await self.tx_repo.create(
            customer_id=customer_id,
            amount=amount,
            currency=currency,
            status=status,
            subscription_id=subscription_id,
            payment_method_id=payment_method_id,
            description=description,
        )
        return TransactionResponse.model_validate(tx)

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------
    async def generate_invoice(
        self,
        customer_id: uuid.UUID,
        subscription_id: uuid.UUID | None,
        items: list[dict],
        currency: str = "INR",
    ) -> InvoiceResponse:
        subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
        tax = 0  # Tax calculation can be added later
        total = subtotal + tax

        invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
        invoice = await self.invoice_repo.create(
            customer_id=customer_id,
            subscription_id=subscription_id,
            invoice_number=invoice_number,
            subtotal=subtotal,
            tax=tax,
            total=total,
            currency=currency,
        )

        for item in items:
            await self.invoice_repo.add_item(
                invoice_id=invoice.id,
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                amount=item["quantity"] * item["unit_price"],
            )

        return InvoiceResponse.model_validate(invoice)

    async def get_invoice_detail(
        self, invoice_id: uuid.UUID
    ) -> InvoiceDetailResponse:
        invoice = await self.invoice_repo.get_by_id(invoice_id)
        if not invoice:
            raise NotFoundError("Invoice not found")
        return InvoiceDetailResponse.model_validate(invoice)

    async def list_invoices(
        self, user_id: uuid.UUID
    ) -> list[InvoiceResponse]:
        customer = await self.customer_repo.get_by_user_id(user_id)
        if not customer:
            return []
        invoices = await self.invoice_repo.list_by_customer(customer.id)
        return [InvoiceResponse.model_validate(i) for i in invoices]

    # ------------------------------------------------------------------
    # Payment methods
    # ------------------------------------------------------------------
    async def list_payment_methods(
        self, user_id: uuid.UUID
    ) -> list[PaymentMethodResponse]:
        customer = await self.customer_repo.get_by_user_id(user_id)
        if not customer:
            return []
        methods = await self.payment_method_repo.list_by_customer(customer.id)
        return [PaymentMethodResponse.model_validate(m) for m in methods]

    async def add_payment_method(
        self,
        user_id: uuid.UUID,
        method_type: str,
        last_four: str | None = None,
        brand: str | None = None,
    ) -> PaymentMethodResponse:
        customer = await self.customer_repo.get_by_user_id(user_id)
        if not customer:
            raise NotFoundError("Customer not found")

        method = await self.payment_method_repo.create(
            customer_id=customer.id,
            type_=method_type,
            last_four=last_four,
            brand=brand,
        )
        return PaymentMethodResponse.model_validate(method)

    async def delete_payment_method(
        self, user_id: uuid.UUID, method_id: uuid.UUID
    ) -> dict:
        customer = await self.customer_repo.get_by_user_id(user_id)
        if not customer:
            raise NotFoundError("Customer not found")
        method = await self.payment_method_repo.get_by_id(method_id)
        if not method or method.customer_id != customer.id:
            raise NotFoundError("Payment method not found")
        await self.payment_method_repo.delete(method_id)
        return {"status": "success", "message": "Payment method removed"}

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------
    async def list_transactions(
        self, user_id: uuid.UUID
    ) -> list[TransactionResponse]:
        customer = await self.customer_repo.get_by_user_id(user_id)
        if not customer:
            return []
        txs = await self.tx_repo.list_by_customer(customer.id)
        return [TransactionResponse.model_validate(t) for t in txs]

    # ------------------------------------------------------------------
    # Webhook handling
    # ------------------------------------------------------------------
    async def handle_webhook(
        self, provider_name: str, event_id: str, event_type: str, payload: str
    ) -> dict:
        event, is_new = await self.webhook_repo.create_if_not_exists(
            provider=provider_name,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        if not is_new:
            return {"status": "already_processed"}

        try:
            # Process based on event type
            # Subclasses or handler maps can be used for complex logic
            logger.info(f"Processing webhook: {provider_name}/{event_type}/{event_id}")
            await self.webhook_repo.mark_processed(event.id)
            return {"status": "processed"}
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            await self.webhook_repo.mark_failed(event.id, str(e))
            return {"status": "failed", "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @property
    def _provider_name(self) -> str:
        return self.provider.__class__.__name__.replace("Provider", "").lower()
