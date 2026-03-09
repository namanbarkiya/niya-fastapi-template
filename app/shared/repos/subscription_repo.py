"""
Subscription + Plan repositories.
THE ONLY way product modules access shared subscription/plan data.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.plan import Plan
from app.shared.models.subscription import Subscription

logger = logging.getLogger(__name__)


# ======================================================================
# SubscriptionRepo
# ======================================================================
class SubscriptionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get_by_id(self, subscription_id: uuid.UUID) -> Optional[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_customer(
        self, customer_id: uuid.UUID
    ) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.customer_id == customer_id,
                Subscription.status.in_(["active", "trialing"]),
            )
        )
        return list(result.scalars().all())

    async def get_by_customer_and_product(
        self, customer_id: uuid.UUID, product: str
    ) -> Optional[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.customer_id == customer_id,
                Subscription.product == product,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_plan(self, plan_id: uuid.UUID) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.plan_id == plan_id)
            .order_by(Subscription.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    async def create(
        self,
        customer_id: uuid.UUID,
        plan_id: uuid.UUID,
        product: str,
        status: str,
        period_start: datetime,
        period_end: datetime,
        trial_end: datetime | None = None,
    ) -> Subscription:
        subscription = Subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            product=product,
            status=status,
            current_period_start=period_start,
            current_period_end=period_end,
            trial_end=trial_end,
        )
        self.session.add(subscription)
        await self.session.flush()
        logger.info(
            f"Created subscription {subscription.id} for customer {customer_id} "
            f"(product={product}, status={status})"
        )
        return subscription

    async def update_status(
        self, subscription_id: uuid.UUID, status: str
    ) -> Optional[Subscription]:
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        return await self.get_by_id(subscription_id)

    async def cancel(
        self, subscription_id: uuid.UUID, reason: str | None = None
    ) -> Optional[Subscription]:
        await self.session.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(
                status="canceled",
                canceled_at=datetime.now(timezone.utc),
                cancel_reason=reason,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return await self.get_by_id(subscription_id)


# ======================================================================
# PlanRepo
# ======================================================================
class PlanRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get_by_id(self, plan_id: uuid.UUID) -> Optional[Plan]:
        result = await self.session.execute(
            select(Plan).where(Plan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Plan]:
        result = await self.session.execute(
            select(Plan).where(Plan.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_active_by_product(self, product: str) -> list[Plan]:
        result = await self.session.execute(
            select(Plan)
            .where(Plan.product == product, Plan.is_active.is_(True))
            .order_by(Plan.sort_order, Plan.price_amount)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    async def create(self, **kwargs) -> Plan:
        plan = Plan(**kwargs)
        self.session.add(plan)
        await self.session.flush()
        logger.info(f"Created plan {plan.id} ({plan.slug})")
        return plan

    async def update(self, plan_id: uuid.UUID, **kwargs) -> Optional[Plan]:
        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            update(Plan).where(Plan.id == plan_id).values(**kwargs)
        )
        return await self.get_by_id(plan_id)
