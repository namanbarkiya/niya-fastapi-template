"""
User repository — all database queries, no business logic here.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import handle_db_error
from core.security import generate_secure_token, hash_token
from models.db_models import (
    EmailVerificationToken,
    OAuthAccount,
    PasswordResetToken,
    RefreshToken,
    User,
    UserProfile,
)

import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Async repository for user-related DB operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # User CRUD
    # ------------------------------------------------------------------
    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email.lower()).options(selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def create_user(
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
        self.db.add(user)
        await self.db.flush()   # get the generated id before commit

        # Create an empty profile immediately
        profile = UserProfile(user_id=user.id)
        self.db.add(profile)
        await self.db.flush()

        logger.info(f"Created user {user.id} ({email})")
        return user

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )

    async def verify_email(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(User).where(User.id == user_id).values(email_verified=True)
        )

    async def update_password(self, user_id: uuid.UUID, new_hash: str) -> None:
        await self.db.execute(
            update(User).where(User.id == user_id).values(password_hash=new_hash)
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    async def get_profile(self, user_id: uuid.UUID) -> Optional[UserProfile]:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_profile(self, user_id: uuid.UUID, data: dict) -> Optional[UserProfile]:
        data["updated_at"] = datetime.now(timezone.utc)
        await self.db.execute(
            update(UserProfile).where(UserProfile.user_id == user_id).values(**data)
        )
        return await self.get_profile(user_id)

    async def update_last_seen(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(UserProfile)
            .where(UserProfile.user_id == user_id)
            .values(last_seen_at=datetime.now(timezone.utc))
        )

    # ------------------------------------------------------------------
    # Refresh tokens
    # ------------------------------------------------------------------
    async def create_refresh_token(
        self, user_id: uuid.UUID, raw_token: str, expire_days: int
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=expire_days),
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_refresh_token(self, raw_token: str) -> Optional[RefreshToken]:
        result = await self.db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.token_hash == hash_token(raw_token),
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
            .options(selectinload(RefreshToken.user).selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, raw_token: str) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(raw_token))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> None:
        """Revoke all active refresh tokens for a user (e.g., on password change)."""
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------
    async def create_email_verification_token(self, user_id: uuid.UUID) -> str:
        # Purge old tokens first
        await self.db.execute(
            delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
        )
        raw = generate_secure_token()
        token = EmailVerificationToken(
            user_id=user_id,
            token=raw,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(token)
        await self.db.flush()
        return raw

    async def consume_email_verification_token(self, raw_token: str) -> Optional[uuid.UUID]:
        """Returns the user_id if valid, then deletes the token."""
        result = await self.db.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token == raw_token,
                EmailVerificationToken.expires_at > datetime.now(timezone.utc),
            )
        )
        ev = result.scalar_one_or_none()
        if not ev:
            return None
        user_id = ev.user_id
        await self.db.delete(ev)
        await self.db.flush()
        return user_id

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------
    async def create_password_reset_token(self, user_id: uuid.UUID) -> str:
        # Invalidate any existing tokens
        await self.db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used == False)  # noqa: E712
            .values(used=True)
        )
        raw = generate_secure_token()
        token = PasswordResetToken(
            user_id=user_id,
            token=raw,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        self.db.add(token)
        await self.db.flush()
        return raw

    async def consume_password_reset_token(self, raw_token: str) -> Optional[uuid.UUID]:
        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token == raw_token,
                PasswordResetToken.used == False,  # noqa: E712
                PasswordResetToken.expires_at > datetime.now(timezone.utc),
            )
        )
        prt = result.scalar_one_or_none()
        if not prt:
            return None
        user_id = prt.user_id
        prt.used = True
        await self.db.flush()
        return user_id

    # ------------------------------------------------------------------
    # OAuth accounts
    # ------------------------------------------------------------------
    async def get_oauth_account(
        self, provider: str, provider_user_id: str
    ) -> Optional[OAuthAccount]:
        result = await self.db.execute(
            select(OAuthAccount)
            .where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
            .options(selectinload(OAuthAccount.user).selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def upsert_oauth_account(
        self,
        user_id: uuid.UUID,
        provider: str,
        provider_user_id: str,
        provider_email: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> OAuthAccount:
        existing = await self.get_oauth_account(provider, provider_user_id)
        if existing:
            existing.provider_email = provider_email
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.expires_at = expires_at
            existing.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return existing

        account = OAuthAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        self.db.add(account)
        await self.db.flush()
        return account
