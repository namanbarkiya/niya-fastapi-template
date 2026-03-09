"""
User repository — users + profiles + emails.
THE ONLY way product modules access shared user data.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.models.user import User, UserEmail, UserProfile

logger = logging.getLogger(__name__)


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # User CRUD
    # ------------------------------------------------------------------
    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .where(User.email == email.lower())
            .options(selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        password_hash: Optional[str] = None,
        email_verified: bool = False,
    ) -> User:
        user = User(
            email=email.lower(),
            password_hash=password_hash,
            email_verified=email_verified,
        )
        self.session.add(user)
        await self.session.flush()
        logger.info(f"Created user {user.id} ({email})")
        return user

    async def update(self, user_id: uuid.UUID, **kwargs) -> Optional[User]:
        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            update(User).where(User.id == user_id).values(**kwargs)
        )
        return await self.get_by_id(user_id)

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )

    async def update_password(self, user_id: uuid.UUID, new_hash: str) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(password_hash=new_hash)
        )

    async def verify_email(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(email_verified=True)
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    async def get_profile(self, user_id: uuid.UUID) -> Optional[UserProfile]:
        result = await self.session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_profile(self, user_id: uuid.UUID, **kwargs) -> UserProfile:
        profile = UserProfile(user_id=user_id, **kwargs)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def update_profile(
        self, user_id: uuid.UUID, data: dict
    ) -> Optional[UserProfile]:
        data["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            update(UserProfile)
            .where(UserProfile.user_id == user_id)
            .values(**data)
        )
        return await self.get_profile(user_id)

    async def update_last_seen(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(UserProfile)
            .where(UserProfile.user_id == user_id)
            .values(last_seen_at=datetime.now(timezone.utc))
        )

    # ------------------------------------------------------------------
    # User Emails
    # ------------------------------------------------------------------
    async def get_emails(self, user_id: uuid.UUID) -> list[UserEmail]:
        result = await self.session.execute(
            select(UserEmail)
            .where(UserEmail.user_id == user_id)
            .order_by(UserEmail.is_primary.desc(), UserEmail.created_at)
        )
        return list(result.scalars().all())

    async def add_email(
        self, user_id: uuid.UUID, email: str, is_primary: bool = False
    ) -> UserEmail:
        user_email = UserEmail(
            user_id=user_id,
            email=email.lower(),
            is_primary=is_primary,
            is_verified=False,
        )
        self.session.add(user_email)
        await self.session.flush()
        return user_email

    async def verify_user_email(self, email_id: uuid.UUID) -> None:
        await self.session.execute(
            update(UserEmail)
            .where(UserEmail.id == email_id)
            .values(is_verified=True, verified_at=datetime.now(timezone.utc))
        )

    async def get_email_by_address(self, email: str) -> Optional[UserEmail]:
        result = await self.session.execute(
            select(UserEmail).where(UserEmail.email == email.lower())
        )
        return result.scalar_one_or_none()
