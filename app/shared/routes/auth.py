"""
Auth routes: POST /register, /login, /refresh, /logout, /logout-all,
             /oauth/{provider}, /forgot-password, /reset-password, /verify-email
"""
import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import AuthenticationError
from app.shared.models.user import User
from app.shared.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    OAuthCallback,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    ResendOtpRequest,
    VerifyEmailRequest,
)
from app.shared.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    result = await svc.register(payload, request)
    return {
        "status": "success",
        "message": result["message"],
        "user": result["user"],
    }


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.login(payload, response, request)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise AuthenticationError("Refresh token missing")
    svc = AuthService(db)
    return await svc.refresh_token(raw_refresh, response, request)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh = request.cookies.get("refresh_token")
    svc = AuthService(db)
    return await svc.logout(raw_refresh, response)


@router.post("/logout-all")
async def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.logout_all_devices(current_user.id, response)


@router.post("/oauth/{provider}", response_model=AuthResponse)
async def oauth_login(
    provider: str,
    payload: OAuthCallback,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """OAuth callback — exchange provider code for tokens.

    The actual OAuth code exchange should happen on the frontend.
    This endpoint receives the provider user info and creates/links the account.
    """
    # In a real implementation, you'd exchange the code for tokens here.
    # For now, this is a placeholder that expects provider_user_id in the code field.
    svc = AuthService(db)
    return await svc.oauth_login(
        provider=provider,
        provider_user_id=payload.code,
        provider_email=None,
        access_token_value=None,
        refresh_token_value=None,
        response=response,
        request=request,
    )


@router.post("/forgot-password")
async def forgot_password(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.request_password_reset(payload.email)


@router.post("/reset-password")
async def reset_password(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.reset_password(payload.token, payload.new_password)


@router.post("/verify-email")
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.verify_email(payload.email, payload.otp)


@router.post("/resend-otp")
async def resend_otp(
    payload: ResendOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    return await svc.resend_verification_otp(payload.email)
