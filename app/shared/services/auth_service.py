"""
Auth service — register, login, refresh, logout, OAuth, password reset.

JWT payload: {sub: user_id, email, products: [...], orgs: [{id, role}]}
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token_value,
    generate_otp,
    generate_secure_token,
    hash_password,
    verify_password,
)
from app.shared.models.user import User, UserProfile
from app.shared.repos.auth_repo import AuthRepo
from app.shared.repos.product_access_repo import ProductAccessRepo
from app.shared.repos.user_repo import UserRepo
from app.shared.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.shared.schemas.user import MeResponse, ProfileResponse, ProfileUpdate, UserResponse
from app.shared.services.email_service import (
    send_password_reset_email,
    send_verification_otp,
    send_welcome_email,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
def set_auth_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth/refresh",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth/refresh")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _user_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def _profile_response(profile: Optional[UserProfile]) -> Optional[ProfileResponse]:
    if profile is None:
        return None
    return ProfileResponse.model_validate(profile)


async def _build_jwt_extra(user: User, product_access_repo: ProductAccessRepo) -> dict:
    """Build the extra claims for the JWT: email, products, orgs."""
    products = await product_access_repo.get_user_product_names(user.id)
    return {
        "email": user.email,
        "products": products,
        "orgs": [],
    }


def _extract_request_meta(request: Optional[Request]) -> tuple[str | None, str | None]:
    if not request:
        return None, None
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.user_repo = UserRepo(db)
        self.auth_repo = AuthRepo(db)
        self.product_access_repo = ProductAccessRepo(db)

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------
    async def register(
        self, payload: RegisterRequest, request: Optional[Request] = None, product: Optional[str] = None
    ) -> dict:
        existing = await self.user_repo.get_by_email(payload.email)
        if existing:
            raise ConflictError("An account with this email already exists")

        pw_hash = hash_password(payload.password)
        user = await self.user_repo.create(
            email=payload.email,
            password_hash=pw_hash,
            email_verified=False,
        )

        # Create profile
        profile_kwargs = {}
        if payload.name:
            profile_kwargs["full_name"] = payload.name
        await self.user_repo.create_profile(user.id, **profile_kwargs)

        # Create primary email record
        await self.user_repo.add_email(user.id, user.email, is_primary=True)

        # Grant product access — product comes from middleware, never from user input
        if product:
            await self.product_access_repo.grant_access(user.id, product)

        # Send verification OTP
        otp = generate_otp()
        await self.auth_repo.create_verification_token(
            user_id=user.id,
            email=user.email,
            token_value=otp,
            token_type="email_verify",
            expire_hours=24,
        )
        send_verification_otp(user.email, otp)

        logger.info(f"New user registered: {user.id}")
        return {
            "status": "success",
            "message": "Account created. Please check your email for the verification code.",
            "user": _user_response(user),
        }

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    async def login(
        self,
        payload: LoginRequest,
        response: Response,
        request: Optional[Request] = None,
        product: Optional[str] = None,
    ) -> AuthResponse:
        user = await self.user_repo.get_by_email(payload.email)
        if not user or not user.password_hash:
            raise AuthenticationError("Invalid email or password")
        if not verify_password(payload.password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated")

        # Verify the user has signed up for this product
        if product:
            has_access = await self.product_access_repo.has_access(user.id, product)
            if not has_access:
                raise AuthorizationError(
                    "No account found for this product. Please sign up first."
                )

        await self.user_repo.update_last_login(user.id)

        access_token = create_access_token(
            subject=str(user.id), extra=await _build_jwt_extra(user, self.product_access_repo)
        )
        raw_refresh = create_refresh_token_value()
        ip, ua = _extract_request_meta(request)
        await self.auth_repo.create_session(
            user_id=user.id,
            raw_token=raw_refresh,
            expire_days=settings.refresh_token_expire_days,
            ip_address=ip,
            user_agent=ua,
        )

        set_auth_cookies(response, access_token, raw_refresh)
        logger.info(f"User signed in: {user.id}")

        return AuthResponse(
            access_token=access_token,
            user=_user_response(user),
            profile=_profile_response(user.profile),
        )

    # ------------------------------------------------------------------
    # Refresh token
    # ------------------------------------------------------------------
    async def refresh_token(
        self,
        raw_refresh: str,
        response: Response,
        request: Optional[Request] = None,
    ) -> AuthResponse:
        session = await self.auth_repo.get_session(raw_refresh)
        if not session:
            raise AuthenticationError("Refresh token is invalid or expired")

        user = session.user
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated")

        # Rotate: revoke old, issue new
        await self.auth_repo.delete_session(raw_refresh)
        new_access = create_access_token(
            subject=str(user.id), extra=await _build_jwt_extra(user, self.product_access_repo)
        )
        new_raw_refresh = create_refresh_token_value()
        ip, ua = _extract_request_meta(request)
        await self.auth_repo.create_session(
            user_id=user.id,
            raw_token=new_raw_refresh,
            expire_days=settings.refresh_token_expire_days,
            ip_address=ip,
            user_agent=ua,
        )

        set_auth_cookies(response, new_access, new_raw_refresh)
        await self.user_repo.update_last_login(user.id)

        return AuthResponse(
            access_token=new_access,
            user=_user_response(user),
            profile=_profile_response(user.profile),
        )

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------
    async def logout(
        self, raw_refresh_token: Optional[str], response: Response
    ) -> dict:
        if raw_refresh_token:
            await self.auth_repo.delete_session(raw_refresh_token)
        clear_auth_cookies(response)
        return {"status": "success", "message": "Signed out successfully"}

    # ------------------------------------------------------------------
    # Logout all devices
    # ------------------------------------------------------------------
    async def logout_all_devices(
        self, user_id: UUID, response: Response
    ) -> dict:
        await self.auth_repo.delete_all_user_sessions(user_id)
        clear_auth_cookies(response)
        return {"status": "success", "message": "Signed out from all devices"}

    # ------------------------------------------------------------------
    # OAuth login
    # ------------------------------------------------------------------
    async def oauth_login(
        self,
        provider: str,
        provider_user_id: str,
        provider_email: Optional[str],
        access_token_value: Optional[str],
        refresh_token_value: Optional[str],
        response: Response,
        request: Optional[Request] = None,
    ) -> AuthResponse:
        # Check if provider already linked
        existing_provider = await self.auth_repo.get_provider(
            provider, provider_user_id
        )

        if existing_provider:
            # Update tokens
            await self.auth_repo.update_provider_tokens(
                existing_provider.id,
                access_token=access_token_value,
                refresh_token=refresh_token_value,
            )
            user = existing_provider.user
        else:
            # Try to find user by email, or create new
            user = None
            if provider_email:
                user = await self.user_repo.get_by_email(provider_email)

            if not user:
                user = await self.user_repo.create(
                    email=provider_email or f"{provider}_{provider_user_id}@oauth.local",
                    email_verified=bool(provider_email),
                )
                await self.user_repo.create_profile(user.id)
                if provider_email:
                    await self.user_repo.add_email(
                        user.id, provider_email, is_primary=True
                    )

            await self.auth_repo.create_provider(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                access_token=access_token_value,
                refresh_token=refresh_token_value,
            )

        await self.user_repo.update_last_login(user.id)

        jwt_token = create_access_token(
            subject=str(user.id), extra=await _build_jwt_extra(user, self.product_access_repo)
        )
        raw_refresh = create_refresh_token_value()
        ip, ua = _extract_request_meta(request)
        await self.auth_repo.create_session(
            user_id=user.id,
            raw_token=raw_refresh,
            expire_days=settings.refresh_token_expire_days,
            ip_address=ip,
            user_agent=ua,
        )

        set_auth_cookies(response, jwt_token, raw_refresh)

        # Re-fetch user with profile
        user = await self.user_repo.get_by_id(user.id)

        return AuthResponse(
            access_token=jwt_token,
            user=_user_response(user),
            profile=_profile_response(user.profile) if user else None,
        )

    # ------------------------------------------------------------------
    # Verify email (OTP)
    # ------------------------------------------------------------------
    async def verify_email(self, email: str, otp: str) -> dict:
        token = await self.auth_repo.use_verification_otp(email, otp)
        if not token:
            raise ValidationError("OTP is invalid or expired")

        await self.user_repo.verify_email(token.user_id)

        # Mark the UserEmail record as verified too
        user_email = await self.user_repo.get_email_by_address(email)
        if user_email:
            await self.user_repo.verify_user_email(user_email.id)

        user = await self.user_repo.get_by_id(token.user_id)
        if user:
            profile = await self.user_repo.get_profile(token.user_id)
            name = profile.full_name if profile else None
            send_welcome_email(user.email, name)

        logger.info(f"Email verified via OTP for user {token.user_id}")
        return {"status": "success", "message": "Email verified successfully"}

    # ------------------------------------------------------------------
    # Resend verification OTP
    # ------------------------------------------------------------------
    async def resend_verification_otp(self, email: str) -> dict:
        user = await self.user_repo.get_by_email(email)
        if user and not user.email_verified:
            otp = generate_otp()
            await self.auth_repo.create_verification_token(
                user_id=user.id,
                email=user.email,
                token_value=otp,
                token_type="email_verify",
                expire_hours=24,
            )
            send_verification_otp(user.email, otp)
        # Always return success to prevent enumeration
        return {
            "status": "success",
            "message": "If this email is pending verification, a new code has been sent.",
        }

    # ------------------------------------------------------------------
    # Request password reset
    # ------------------------------------------------------------------
    async def request_password_reset(self, email: str) -> dict:
        user = await self.user_repo.get_by_email(email)
        if user:
            token = generate_secure_token()
            await self.auth_repo.create_verification_token(
                user_id=user.id,
                email=user.email,
                token_value=token,
                token_type="password_reset",
                expire_hours=1,
            )
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
        vt = await self.auth_repo.use_verification_token(token, "password_reset")
        if not vt:
            raise ValidationError("Password reset token is invalid or expired")
        new_hash = hash_password(new_password)
        await self.user_repo.update_password(vt.user_id, new_hash)
        await self.auth_repo.delete_all_user_sessions(vt.user_id)
        logger.info(f"Password reset for user {vt.user_id}")
        return {"status": "success", "message": "Password updated successfully"}

    # ------------------------------------------------------------------
    # Change password (authenticated)
    # ------------------------------------------------------------------
    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
        response: Response,
    ) -> dict:
        if not user.password_hash or not verify_password(
            current_password, user.password_hash
        ):
            raise AuthenticationError("Current password is incorrect")
        new_hash = hash_password(new_password)
        await self.user_repo.update_password(user.id, new_hash)
        await self.auth_repo.delete_all_user_sessions(user.id)
        clear_auth_cookies(response)
        logger.info(f"Password changed for user {user.id}")
        return {
            "status": "success",
            "message": "Password changed successfully. Please sign in again.",
        }

    # ------------------------------------------------------------------
    # Get me
    # ------------------------------------------------------------------
    async def get_me(self, user: User) -> MeResponse:
        await self.user_repo.update_last_seen(user.id)
        return MeResponse(
            user=_user_response(user),
            profile=_profile_response(user.profile),
        )

    # ------------------------------------------------------------------
    # Update profile
    # ------------------------------------------------------------------
    async def update_profile(
        self, user: User, payload: ProfileUpdate
    ) -> MeResponse:
        updates = payload.model_dump(exclude_none=True)
        if updates:
            await self.user_repo.update_profile(user.id, updates)
        updated_profile = await self.user_repo.get_profile(user.id)
        return MeResponse(
            user=_user_response(user),
            profile=_profile_response(updated_profile),
        )
