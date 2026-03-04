"""
Auth + User controllers.

All auth routes: /api/v1/auth/*
All user routes: /api/v1/users/*
"""
import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from core.exceptions import AuthenticationError, ValidationError
from middleware.auth import get_current_user
from models.db_models import User
from models.user_model import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    MeResponse,
    ResetPasswordRequest,
    SignInRequest,
    SignUpRequest,
    UpdateProfileRequest,
    VerifyOtpRequest,
    ResendOtpRequest,
)
from services.user_service import UserService

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["authentication"])
users_router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

@auth_router.post("/signup", status_code=201)
async def signup(
    payload: SignUpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new account. Returns user + sends verification email."""
    svc = UserService(db)
    result = await svc.sign_up(payload)
    # Strip verification_token from response (only for internal/email use)
    return {
        "status": "success",
        "message": result["message"],
        "user": result["user"],
    }


@auth_router.post("/signin", response_model=AuthResponse)
async def signin(
    payload: SignInRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Sign in with email + password. Sets auth cookies."""
    svc = UserService(db)
    return await svc.sign_in(payload, response)


@auth_router.post("/signout")
async def signout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Sign out — revokes refresh token and clears cookies."""
    raw_refresh = request.cookies.get("refresh_token")
    svc = UserService(db)
    return await svc.sign_out(raw_refresh, response)


@auth_router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    The old refresh token is revoked (rotation).
    """
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise AuthenticationError("Refresh token missing")
    svc = UserService(db)
    return await svc.refresh_tokens(raw_refresh, response)


@auth_router.post("/verify-otp")
async def verify_otp(
    payload: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify email with a 6-digit OTP code."""
    svc = UserService(db)
    return await svc.verify_otp(payload.email, payload.otp)


@auth_router.post("/resend-otp")
async def resend_otp(
    payload: ResendOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resend the email verification OTP."""
    svc = UserService(db)
    return await svc.resend_verification_otp(payload.email)


@auth_router.get("/confirm-email")
async def confirm_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Confirm email address via URL token (legacy/fallback)."""
    svc = UserService(db)
    return await svc.confirm_email(token)


@auth_router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password-reset email."""
    svc = UserService(db)
    return await svc.forgot_password(payload.email)


@auth_router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using the token from the reset email."""
    svc = UserService(db)
    return await svc.reset_password(payload.token, payload.new_password)


# ---------------------------------------------------------------------------
# User Routes  (all require authentication)
# ---------------------------------------------------------------------------

@users_router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user + their profile."""
    svc = UserService(db)
    return await svc.get_me(current_user)


@users_router.put("/me", response_model=MeResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile."""
    svc = UserService(db)
    return await svc.update_profile(current_user, payload)


@users_router.put("/me/password")
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password. All sessions are revoked on success."""
    svc = UserService(db)
    return await svc.change_password(
        current_user, payload.current_password, payload.new_password, response
    )


# ---------------------------------------------------------------------------
# Legacy health-check  (kept from original template)
# ---------------------------------------------------------------------------
router = APIRouter()   # backward-compat alias used in main.py


@router.get("/")
async def index():
    return {"status": "ok", "message": "Hello World"}
