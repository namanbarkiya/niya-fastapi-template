"""
UserService — business logic layer between controllers and repository.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from core.security import generate_otp
from services.email_service import (
    send_password_reset_email,
    send_verification_otp,
    send_welcome_email,
)
from core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from core.security import (
    create_access_token,
    create_refresh_token_value,
    hash_password,
    verify_password,
)
from middleware.auth import clear_auth_cookies, set_auth_cookies
from models.db_models import User, UserProfile
from models.user_model import (
    AuthResponse,
    MeResponse,
    ProfileResponse,
    SignInRequest,
    SignUpRequest,
    UpdateProfileRequest,
    UserResponse,
)
from repositorys.user_repo import UserRepository

logger = logging.getLogger(__name__)


def _user_to_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def _profile_to_response(profile: Optional[UserProfile]) -> Optional[ProfileResponse]:
    if profile is None:
        return None
    return ProfileResponse.model_validate(profile)


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = UserRepository(db)

    # ------------------------------------------------------------------
    # Sign up
    # ------------------------------------------------------------------
    async def sign_up(self, payload: SignUpRequest) -> dict:
        existing = await self.repo.get_by_email(payload.email)
        if existing:
            raise ConflictError("An account with this email already exists")

        pw_hash = hash_password(payload.password)
        user = await self.repo.create_user(
            email=payload.email,
            password_hash=pw_hash,
            email_verified=False,
        )

        # Seed name into profile if provided (profile was just created in create_user)
        if payload.name:
            await self.repo.update_profile(user.id, {"full_name": payload.name})

        # Generate OTP and send verification email
        otp = generate_otp()
        await self.repo.create_email_verification_token(user.id, otp)
        send_verification_otp(user.email, otp)

        logger.info(f"New user registered: {user.id}")
        return {
            "status": "success",
            "message": "Account created. Please check your email for the verification code.",
            "user": _user_to_response(user),
        }

    # ------------------------------------------------------------------
    # Sign in
    # ------------------------------------------------------------------
    async def sign_in(self, payload: SignInRequest, response: Response) -> AuthResponse:
        user = await self.repo.get_by_email(payload.email)
        if not user or not user.password_hash:
            raise AuthenticationError("Invalid email or password")
        if not verify_password(payload.password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated")

        await self.repo.update_last_login(user.id)

        access_token = create_access_token(subject=str(user.id))
        raw_refresh = create_refresh_token_value()
        await self.repo.create_refresh_token(
            user_id=user.id,
            raw_token=raw_refresh,
            expire_days=settings.refresh_token_expire_days,
        )

        set_auth_cookies(response, access_token, raw_refresh)
        logger.info(f"User signed in: {user.id}")

        return AuthResponse(
            access_token=access_token,
            user=_user_to_response(user),
            profile=_profile_to_response(user.profile),
        )

    # ------------------------------------------------------------------
    # Sign out
    # ------------------------------------------------------------------
    async def sign_out(self, raw_refresh_token: Optional[str], response: Response) -> dict:
        if raw_refresh_token:
            await self.repo.revoke_refresh_token(raw_refresh_token)
        clear_auth_cookies(response)
        logger.info("User signed out")
        return {"status": "success", "message": "Signed out successfully"}

    # ------------------------------------------------------------------
    # Refresh access token
    # ------------------------------------------------------------------
    async def refresh_tokens(self, raw_refresh: str, response: Response) -> AuthResponse:
        token_record = await self.repo.get_refresh_token(raw_refresh)
        if not token_record:
            raise AuthenticationError("Refresh token is invalid or expired")

        user = token_record.user
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated")

        # Rotate: revoke old, issue new
        await self.repo.revoke_refresh_token(raw_refresh)
        new_access = create_access_token(subject=str(user.id))
        new_raw_refresh = create_refresh_token_value()
        await self.repo.create_refresh_token(
            user_id=user.id,
            raw_token=new_raw_refresh,
            expire_days=settings.refresh_token_expire_days,
        )

        set_auth_cookies(response, new_access, new_raw_refresh)
        await self.repo.update_last_login(user.id)

        return AuthResponse(
            access_token=new_access,
            user=_user_to_response(user),
            profile=_profile_to_response(user.profile),
        )

    # ------------------------------------------------------------------
    # Email confirmation (OTP — 6 digits)
    # ------------------------------------------------------------------
    async def verify_otp(self, email: str, otp: str) -> dict:
        user_id = await self.repo.consume_email_otp(email, otp)
        if not user_id:
            raise ValidationError("OTP is invalid or expired")
        await self.repo.verify_email(user_id)
        user = await self.repo.get_by_id(user_id)
        if user:
            profile = await self.repo.get_profile(user_id)
            name = profile.full_name if profile else None
            send_welcome_email(user.email, name)
        logger.info(f"Email verified via OTP for user {user_id}")
        return {"status": "success", "message": "Email verified successfully"}

    # ------------------------------------------------------------------
    # Email confirmation (URL token — legacy / API route fallback)
    # ------------------------------------------------------------------
    async def confirm_email(self, token: str) -> dict:
        user_id = await self.repo.consume_email_verification_token(token)
        if not user_id:
            raise ValidationError("Email verification token is invalid or expired")
        await self.repo.verify_email(user_id)
        logger.info(f"Email verified for user {user_id}")
        return {"status": "success", "message": "Email verified successfully"}

    # ------------------------------------------------------------------
    # Resend OTP
    # ------------------------------------------------------------------
    async def resend_verification_otp(self, email: str) -> dict:
        user = await self.repo.get_by_email(email)
        # Always return success to prevent enumeration
        if user and not user.email_verified:
            otp = generate_otp()
            await self.repo.create_email_verification_token(user.id, otp)
            send_verification_otp(user.email, otp)
        return {
            "status": "success",
            "message": "If this email is pending verification, a new code has been sent.",
        }

    # ------------------------------------------------------------------
    # Forgot password
    # ------------------------------------------------------------------
    async def forgot_password(self, email: str) -> dict:
        user = await self.repo.get_by_email(email)
        # Always return success to prevent user enumeration
        if user:
            token = await self.repo.create_password_reset_token(user.id)
            send_password_reset_email(user.email, token)
            logger.info(f"Password reset requested for {email}")
        return {
            "status": "success",
            "message": "If this email is registered you will receive reset instructions.",
        }

    # ------------------------------------------------------------------
    # Reset password
    # ------------------------------------------------------------------
    async def reset_password(self, token: str, new_password: str) -> dict:
        user_id = await self.repo.consume_password_reset_token(token)
        if not user_id:
            raise ValidationError("Password reset token is invalid or expired")
        new_hash = hash_password(new_password)
        await self.repo.update_password(user_id, new_hash)
        await self.repo.revoke_all_user_tokens(user_id)
        logger.info(f"Password reset for user {user_id}")
        return {"status": "success", "message": "Password updated successfully"}

    # ------------------------------------------------------------------
    # Change password (authenticated)
    # ------------------------------------------------------------------
    async def change_password(
        self, user: User, current_password: str, new_password: str, response: Response
    ) -> dict:
        if not user.password_hash or not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")
        new_hash = hash_password(new_password)
        await self.repo.update_password(user.id, new_hash)
        await self.repo.revoke_all_user_tokens(user.id)
        clear_auth_cookies(response)
        logger.info(f"Password changed for user {user.id}")
        return {"status": "success", "message": "Password changed successfully. Please sign in again."}

    # ------------------------------------------------------------------
    # Get me
    # ------------------------------------------------------------------
    async def get_me(self, user: User) -> MeResponse:
        await self.repo.update_last_seen(user.id)
        return MeResponse(
            user=_user_to_response(user),
            profile=_profile_to_response(user.profile),
        )

    # ------------------------------------------------------------------
    # Update profile
    # ------------------------------------------------------------------
    async def update_profile(self, user: User, payload: UpdateProfileRequest) -> MeResponse:
        updates = payload.model_dump(exclude_none=True)
        if updates:
            await self.repo.update_profile(user.id, updates)
        updated_profile = await self.repo.get_profile(user.id)
        return MeResponse(
            user=_user_to_response(user),
            profile=_profile_to_response(updated_profile),
        )
