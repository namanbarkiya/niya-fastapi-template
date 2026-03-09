"""
ProductClient repository — look up frontend client keys.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.product_client import ProductClient


class ProductClientRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_client_key(self, key: str) -> ProductClient | None:
        result = await self.session.execute(
            select(ProductClient).where(
                ProductClient.client_key == key,
                ProductClient.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()
