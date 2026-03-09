"""
Repository for notifications.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.models.notification import Notification


class NotificationRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str | None = None,
        channel: str = "in_app",
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            title=title,
            body=body,
            channel=channel,
        )
        self.session.add(notif)
        await self.session.flush()
        await self.session.refresh(notif)
        return notif

    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: uuid.UUID, unread_only: bool = False
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_read(self, notification_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.session.flush()

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.session.flush()
        return result.rowcount
