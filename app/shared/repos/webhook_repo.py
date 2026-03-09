"""
WebhookEvent repository — idempotent webhook processing.
THE ONLY way product modules access shared webhook-event data.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.webhook_event import WebhookEvent

logger = logging.getLogger(__name__)


class WebhookRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Idempotent create
    # ------------------------------------------------------------------
    async def create_if_not_exists(
        self,
        provider: str,
        event_id: str,
        event_type: str,
        payload: str,
    ) -> tuple[WebhookEvent, bool]:
        """
        Insert a webhook event if it hasn't been recorded yet.

        Returns
        -------
        (WebhookEvent, created)
            *created* is True when the row was newly inserted, False when it
            already existed (duplicate delivery).
        """
        # Check for an existing event with the same idempotency key
        result = await self.session.execute(
            select(WebhookEvent).where(WebhookEvent.event_id == event_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            logger.debug(f"Webhook event {event_id} already recorded, skipping")
            return existing, False

        event = WebhookEvent(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        self.session.add(event)
        await self.session.flush()
        logger.info(f"Recorded webhook event {event.id} ({provider}/{event_type})")
        return event, True

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------
    async def mark_processed(self, event_id: uuid.UUID) -> None:
        await self.session.execute(
            update(WebhookEvent)
            .where(WebhookEvent.id == event_id)
            .values(processed_at=datetime.now(timezone.utc))
        )

    async def mark_failed(self, event_id: uuid.UUID, error: str) -> None:
        await self.session.execute(
            update(WebhookEvent)
            .where(WebhookEvent.id == event_id)
            .values(error=error)
        )
