"""
Invoice repository — invoices + line items.
THE ONLY way product modules access shared invoice data.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.models.invoice import Invoice, InvoiceItem

logger = logging.getLogger(__name__)


class InvoiceRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get_by_id(self, invoice_id: uuid.UUID) -> Optional[Invoice]:
        """Return an invoice with its items eagerly loaded."""
        result = await self.session.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(selectinload(Invoice.items))  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def list_by_customer(self, customer_id: uuid.UUID) -> list[Invoice]:
        result = await self.session.execute(
            select(Invoice)
            .where(Invoice.customer_id == customer_id)
            .order_by(Invoice.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    async def create(
        self,
        customer_id: uuid.UUID,
        subscription_id: uuid.UUID | None,
        invoice_number: str,
        subtotal: int,
        tax: int,
        total: int,
        currency: str = "INR",
    ) -> Invoice:
        invoice = Invoice(
            customer_id=customer_id,
            subscription_id=subscription_id,
            invoice_number=invoice_number,
            subtotal=subtotal,
            tax=tax,
            total=total,
            currency=currency,
        )
        self.session.add(invoice)
        await self.session.flush()
        logger.info(
            f"Created invoice {invoice.id} ({invoice_number}) "
            f"for customer {customer_id}"
        )
        return invoice

    async def add_item(
        self,
        invoice_id: uuid.UUID,
        description: str,
        quantity: int,
        unit_price: int,
        amount: int,
    ) -> InvoiceItem:
        item = InvoiceItem(
            invoice_id=invoice_id,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_status(
        self, invoice_id: uuid.UUID, status: str
    ) -> Optional[Invoice]:
        await self.session.execute(
            update(Invoice)
            .where(Invoice.id == invoice_id)
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        return await self.get_by_id(invoice_id)

    async def mark_paid(self, invoice_id: uuid.UUID) -> Optional[Invoice]:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(Invoice)
            .where(Invoice.id == invoice_id)
            .values(status="paid", paid_at=now, updated_at=now)
        )
        return await self.get_by_id(invoice_id)
