"""
Repository for API keys.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.api_key import ApiKey


class ApiKeyRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        key_hash: str,
        prefix: str,
        scopes: str | None = None,
        org_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
    ) -> ApiKey:
        api_key = ApiKey(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            scopes=scopes,
            org_id=org_id,
            expires_at=expires_at,
        )
        self.session.add(api_key)
        await self.session.flush()
        await self.session.refresh(api_key)
        return api_key

    async def get_by_id(self, key_id: uuid.UUID) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[ApiKey]:
        result = await self.session.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_last_used(self, key_id: uuid.UUID) -> None:
        await self.session.execute(
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
        await self.session.flush()

    async def revoke(self, key_id: uuid.UUID) -> None:
        await self.session.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(is_active=False)
        )
        await self.session.flush()
