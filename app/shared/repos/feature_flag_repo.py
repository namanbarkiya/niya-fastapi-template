"""
Repository for feature flags.
"""
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.feature_flag import FeatureFlag


class FeatureFlagRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_key(self, key: str) -> FeatureFlag | None:
        result = await self.session.execute(
            select(FeatureFlag).where(FeatureFlag.key == key)
        )
        return result.scalar_one_or_none()

    async def is_enabled(self, key: str, product: str | None = None) -> bool:
        flag = await self.get_by_key(key)
        if not flag:
            return False
        if not flag.is_enabled:
            return False
        # If flag has a product scope, check it matches
        if flag.product and flag.product != product:
            return False
        return True

    async def list_all(self, product: str | None = None) -> list[FeatureFlag]:
        stmt = select(FeatureFlag).order_by(FeatureFlag.key)
        if product:
            stmt = stmt.where(
                (FeatureFlag.product == product) | (FeatureFlag.product.is_(None))
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        key: str,
        description: str | None = None,
        is_enabled: bool = False,
        product: str | None = None,
        rules: str | None = None,
    ) -> FeatureFlag:
        flag = FeatureFlag(
            key=key,
            description=description,
            is_enabled=is_enabled,
            product=product,
            rules=rules,
        )
        self.session.add(flag)
        await self.session.flush()
        await self.session.refresh(flag)
        return flag

    async def toggle(self, flag_id: uuid.UUID, enabled: bool) -> None:
        await self.session.execute(
            update(FeatureFlag)
            .where(FeatureFlag.id == flag_id)
            .values(is_enabled=enabled)
        )
        await self.session.flush()
