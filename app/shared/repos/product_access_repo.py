"""
ProductAccess repository — which products a user can access.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.product_access import ProductAccess


class ProductAccessRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_products(self, user_id: uuid.UUID) -> list[ProductAccess]:
        result = await self.session.execute(
            select(ProductAccess).where(
                ProductAccess.user_id == user_id,
                (ProductAccess.expires_at.is_(None))
                | (ProductAccess.expires_at > datetime.now(timezone.utc)),
            )
        )
        return list(result.scalars().all())

    async def get_user_product_names(self, user_id: uuid.UUID) -> list[str]:
        records = await self.get_user_products(user_id)
        return [r.product for r in records]

    async def grant_access(
        self,
        user_id: uuid.UUID,
        product: str,
        role: str = "user",
        org_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
    ) -> ProductAccess:
        access = ProductAccess(
            user_id=user_id,
            product=product,
            role=role,
            org_id=org_id,
            expires_at=expires_at,
        )
        self.session.add(access)
        await self.session.flush()
        return access

    async def revoke_access(
        self, user_id: uuid.UUID, product: str
    ) -> None:
        records = await self.get_user_products(user_id)
        for r in records:
            if r.product == product:
                await self.session.delete(r)
        await self.session.flush()

    async def has_access(self, user_id: uuid.UUID, product: str) -> bool:
        result = await self.session.execute(
            select(ProductAccess).where(
                ProductAccess.user_id == user_id,
                ProductAccess.product == product,
                (ProductAccess.expires_at.is_(None))
                | (ProductAccess.expires_at > datetime.now(timezone.utc)),
            )
        )
        return result.scalar_one_or_none() is not None
