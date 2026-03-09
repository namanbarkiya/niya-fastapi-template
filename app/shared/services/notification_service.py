"""
Notification service — create and manage in-app notifications.
"""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.shared.repos.notification_repo import NotificationRepo
from app.shared.schemas.notification import NotificationResponse

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = NotificationRepo(db)

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        body: str | None = None,
        channel: str = "in_app",
    ) -> NotificationResponse:
        notif = await self.repo.create(
            user_id=user_id, title=title, body=body, channel=channel
        )
        return NotificationResponse.model_validate(notif)

    async def list_for_user(
        self, user_id: uuid.UUID, unread_only: bool = False
    ) -> list[NotificationResponse]:
        notifs = await self.repo.list_by_user(user_id, unread_only=unread_only)
        return [NotificationResponse.model_validate(n) for n in notifs]

    async def mark_read(
        self, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> dict:
        notif = await self.repo.get_by_id(notification_id)
        if not notif:
            raise NotFoundError("Notification not found")
        if notif.user_id != user_id:
            raise AuthorizationError("Not your notification")
        await self.repo.mark_read(notification_id)
        return {"status": "success"}

    async def mark_all_read(self, user_id: uuid.UUID) -> dict:
        count = await self.repo.mark_all_read(user_id)
        return {"status": "success", "marked": count}
