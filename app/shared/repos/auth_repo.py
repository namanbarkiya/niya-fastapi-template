"""
Auth repository — sessions, providers, verification tokens.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_token
from app.shared.models.auth import AuthProvider, AuthSession, EmailVerificationToken
from app.shared.models.user import User

logger = logging.getLogger(__name__)


class AuthRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Sessions (refresh tokens)
    # ------------------------------------------------------------------
    async def create_session(
        self,
        user_id: uuid.UUID,
        raw_token: str,
        expire_days: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSession:
        auth_session = AuthSession(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expire_days),
        )
        self.session.add(auth_session)
        await self.session.flush()
        return auth_session

    async def get_session(self, raw_token: str) -> Optional[AuthSession]:
        result = await self.session.execute(
            select(AuthSession)
            .where(
                AuthSession.token_hash == hash_token(raw_token),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(timezone.utc),
            )
            .options(selectinload(AuthSession.user).selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def delete_session(self, raw_token: str) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == hash_token(raw_token))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def delete_all_user_sessions(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )

    # ------------------------------------------------------------------
    # Auth Providers (OAuth)
    # ------------------------------------------------------------------
    async def create_provider(
        self,
        user_id: uuid.UUID,
        provider: str,
        provider_user_id: str,
        provider_email: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires_at: datetime | None = None,
    ) -> AuthProvider:
        auth_provider = AuthProvider(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
        )
        self.session.add(auth_provider)
        await self.session.flush()
        return auth_provider

    async def get_provider(
        self, provider: str, provider_user_id: str
    ) -> Optional[AuthProvider]:
        result = await self.session.execute(
            select(AuthProvider)
            .where(
                AuthProvider.provider == provider,
                AuthProvider.provider_user_id == provider_user_id,
            )
            .options(selectinload(AuthProvider.user).selectinload(User.profile))
        )
        return result.scalar_one_or_none()

    async def get_user_providers(self, user_id: uuid.UUID) -> list[AuthProvider]:
        result = await self.session.execute(
            select(AuthProvider).where(AuthProvider.user_id == user_id)
        )
        return list(result.scalars().all())

    async def update_provider_tokens(
        self,
        provider_id: uuid.UUID,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires_at: datetime | None = None,
    ) -> None:
        values: dict = {"updated_at": datetime.now(timezone.utc)}
        if access_token is not None:
            values["access_token"] = access_token
        if refresh_token is not None:
            values["refresh_token"] = refresh_token
        if token_expires_at is not None:
            values["token_expires_at"] = token_expires_at
        await self.session.execute(
            update(AuthProvider)
            .where(AuthProvider.id == provider_id)
            .values(**values)
        )

    # ------------------------------------------------------------------
    # Verification Tokens (email verify + password reset)
    # ------------------------------------------------------------------
    async def create_verification_token(
        self,
        user_id: uuid.UUID,
        email: str,
        token_value: str,
        token_type: str = "email_verify",
        expire_hours: int = 24,
    ) -> EmailVerificationToken:
        # Purge existing tokens of same type for this user
        await self.session.execute(
            delete(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.token_type == token_type,
                EmailVerificationToken.used_at.is_(None),
            )
        )
        token = EmailVerificationToken(
            user_id=user_id,
            email=email.lower(),
            token=token_value,
            token_type=token_type,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expire_hours),
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def use_verification_token(
        self, token_value: str, token_type: str = "email_verify"
    ) -> Optional[EmailVerificationToken]:
        """Find a valid token, mark it as used, and return it."""
        result = await self.session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token == token_value,
                EmailVerificationToken.token_type == token_type,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.expires_at > datetime.now(timezone.utc),
            )
        )
        token = result.scalar_one_or_none()
        if not token:
            return None
        token.used_at = datetime.now(timezone.utc)
        await self.session.flush()
        return token

    async def use_verification_otp(
        self, email: str, otp: str
    ) -> Optional[EmailVerificationToken]:
        """Consume an OTP by matching email + token value."""
        result = await self.session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.email == email.lower(),
                EmailVerificationToken.token == otp,
                EmailVerificationToken.token_type == "email_verify",
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.expires_at > datetime.now(timezone.utc),
            )
        )
        token = result.scalar_one_or_none()
        if not token:
            return None
        token.used_at = datetime.now(timezone.utc)
        await self.session.flush()
        return token
