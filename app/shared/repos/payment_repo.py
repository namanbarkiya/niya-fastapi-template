"""
Payment repository — payment methods + transactions.
THE ONLY way product modules access shared payment data.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.payment import PaymentMethod, Transaction

logger = logging.getLogger(__name__)


# ======================================================================
# PaymentMethodRepo
# ======================================================================
class PaymentMethodRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get_by_id(self, method_id: uuid.UUID) -> Optional[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod).where(PaymentMethod.id == method_id)
        )
        return result.scalar_one_or_none()

    async def list_by_customer(self, customer_id: uuid.UUID) -> list[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod)
            .where(PaymentMethod.customer_id == customer_id)
            .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    async def create(self, **kwargs) -> PaymentMethod:
        method = PaymentMethod(**kwargs)
        self.session.add(method)
        await self.session.flush()
        logger.info(
            f"Created payment method {method.id} for customer {method.customer_id}"
        )
        return method

    async def set_default(
        self, method_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Optional[PaymentMethod]:
        # Unset current default(s) for this customer
        await self.session.execute(
            update(PaymentMethod)
            .where(
                PaymentMethod.customer_id == customer_id,
                PaymentMethod.is_default.is_(True),
            )
            .values(is_default=False)
        )
        # Set the new default
        await self.session.execute(
            update(PaymentMethod)
            .where(PaymentMethod.id == method_id)
            .values(is_default=True)
        )
        return await self.get_by_id(method_id)

    async def delete(self, method_id: uuid.UUID) -> None:
        method = await self.get_by_id(method_id)
        if method:
            await self.session.delete(method)
            await self.session.flush()
            logger.info(f"Deleted payment method {method_id}")


# ======================================================================
# TransactionRepo
# ======================================================================
class TransactionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get_by_id(self, transaction_id: uuid.UUID) -> Optional[Transaction]:
        result = await self.session.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def list_by_customer(
        self, customer_id: uuid.UUID, limit: int = 50
    ) -> list[Transaction]:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.customer_id == customer_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    async def create(self, **kwargs) -> Transaction:
        txn = Transaction(**kwargs)
        self.session.add(txn)
        await self.session.flush()
        logger.info(
            f"Created transaction {txn.id} for customer {txn.customer_id} "
            f"(amount={txn.amount}, status={txn.status})"
        )
        return txn

    async def update_status(
        self, transaction_id: uuid.UUID, status: str
    ) -> Optional[Transaction]:
        await self.session.execute(
            update(Transaction)
            .where(Transaction.id == transaction_id)
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        return await self.get_by_id(transaction_id)
