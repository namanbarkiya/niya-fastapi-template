"""
Repository for product_alpha Resources.

Follows the same repository pattern as shared repos:
- Returns model instances or None, never raw rows.
- No business logic — pure data access.
- Never imports from shared models directly (only shared repos are used for
  cross-schema lookups, handled in the service layer).
"""
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.products.product_alpha.models.resource import Resource


class ResourceRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, resource_id: uuid.UUID) -> Resource | None:
        result = await self.session.execute(
            select(Resource).where(Resource.id == resource_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: uuid.UUID, active_only: bool = True
    ) -> list[Resource]:
        stmt = (
            select(Resource)
            .where(Resource.user_id == user_id)
            .order_by(Resource.created_at.desc())
        )
        if active_only:
            stmt = stmt.where(Resource.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        description: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> Resource:
        resource = Resource(
            user_id=user_id,
            title=title,
            description=description,
            data=data,
            is_active=True,
        )
        self.session.add(resource)
        await self.session.flush()
        await self.session.refresh(resource)
        return resource

    async def update(
        self,
        resource_id: uuid.UUID,
        title: str | None = None,
        description: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> Resource | None:
        values: dict[str, Any] = {}
        if title is not None:
            values["title"] = title
        if description is not None:
            values["description"] = description
        if data is not None:
            values["data"] = data
        if not values:
            return await self.get_by_id(resource_id)
        await self.session.execute(
            update(Resource).where(Resource.id == resource_id).values(**values)
        )
        await self.session.flush()
        return await self.get_by_id(resource_id)

    async def delete(self, resource_id: uuid.UUID) -> None:
        """Soft delete — sets is_active=False."""
        await self.session.execute(
            update(Resource).where(Resource.id == resource_id).values(is_active=False)
        )
        await self.session.flush()
