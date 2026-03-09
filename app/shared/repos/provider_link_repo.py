"""
ProviderLink repository — maps internal entities to external payment provider IDs.
THE ONLY way product modules access shared provider-link data.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.provider_link import ProviderLink

logger = logging.getLogger(__name__)


class ProviderLinkRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get(
        self, entity_type: str, entity_id: uuid.UUID, provider: str
    ) -> Optional[ProviderLink]:
        result = await self.session.execute(
            select(ProviderLink).where(
                ProviderLink.entity_type == entity_type,
                ProviderLink.entity_id == entity_id,
                ProviderLink.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_provider_id(
        self, provider: str, provider_id: str
    ) -> Optional[ProviderLink]:
        result = await self.session.execute(
            select(ProviderLink).where(
                ProviderLink.provider == provider,
                ProviderLink.provider_id == provider_id,
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    async def create(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        provider: str,
        provider_id: str,
        provider_data: str | None = None,
    ) -> ProviderLink:
        link = ProviderLink(
            entity_type=entity_type,
            entity_id=entity_id,
            provider=provider,
            provider_id=provider_id,
            provider_data=provider_data,
        )
        self.session.add(link)
        await self.session.flush()
        logger.info(
            f"Created provider link {link.id}: {entity_type}/{entity_id} "
            f"-> {provider}/{provider_id}"
        )
        return link

    async def update(
        self,
        link_id: uuid.UUID,
        provider_id: str | None = None,
        provider_data: str | None = None,
    ) -> Optional[ProviderLink]:
        values: dict = {"updated_at": datetime.now(timezone.utc)}
        if provider_id is not None:
            values["provider_id"] = provider_id
        if provider_data is not None:
            values["provider_data"] = provider_data
        await self.session.execute(
            update(ProviderLink).where(ProviderLink.id == link_id).values(**values)
        )
        result = await self.session.execute(
            select(ProviderLink).where(ProviderLink.id == link_id)
        )
        return result.scalar_one_or_none()
