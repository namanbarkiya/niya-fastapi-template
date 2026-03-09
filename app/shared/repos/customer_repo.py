"""
Customer repository — billing customers.
THE ONLY way product modules access shared customer data.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.customer import Customer
from app.shared.models.subscription import Subscription

logger = logging.getLogger(__name__)


class CustomerRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get_by_id(self, customer_id: uuid.UUID) -> Optional[Customer]:
        result = await self.session.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Optional[Customer]:
        result = await self.session.execute(
            select(Customer).where(Customer.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_product(
        self, user_id: uuid.UUID, product: str
    ) -> Optional[Customer]:
        """Return the customer for a user that has a subscription to *product*."""
        result = await self.session.execute(
            select(Customer)
            .join(Subscription, Subscription.customer_id == Customer.id)
            .where(Customer.user_id == user_id, Subscription.product == product)
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    async def create(
        self,
        user_id: uuid.UUID,
        email: str,
        name: str,
        org_id: uuid.UUID | None = None,
    ) -> Customer:
        customer = Customer(
            user_id=user_id,
            email=email,
            name=name,
            org_id=org_id,
        )
        self.session.add(customer)
        await self.session.flush()
        logger.info(f"Created customer {customer.id} for user {user_id}")
        return customer

    async def update(
        self, customer_id: uuid.UUID, **kwargs
    ) -> Optional[Customer]:
        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            update(Customer).where(Customer.id == customer_id).values(**kwargs)
        )
        return await self.get_by_id(customer_id)

    async def deactivate(self, customer_id: uuid.UUID) -> Optional[Customer]:
        await self.session.execute(
            update(Customer)
            .where(Customer.id == customer_id)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        return await self.get_by_id(customer_id)
