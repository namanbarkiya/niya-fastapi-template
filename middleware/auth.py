"""
Auth middleware / dependencies — pure JWT, no Supabase.

Access token: short-lived JWT in HttpOnly cookie "access_token"
Refresh token: opaque random string in HttpOnly cookie "refresh_token"
"""
import logging
import uuid
from typing import Any, Optional

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from config.settings import settings
from core.exceptions import AuthenticationError
from core.security import decode_access_token
from models.db_models import User
from repositorys.user_repo import UserRepository

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Write access + refresh tokens as secure HttpOnly cookies."""
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
        path="/api/v1/auth/refresh",   # only sent to the refresh endpoint
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")


# ---------------------------------------------------------------------------
# Token extraction helpers
# ---------------------------------------------------------------------------
def _extract_token_from_request(request: Request) -> Optional[str]:
    """Try cookie first, then Authorization Bearer header."""
    token = request.cookies.get("access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def _resolve_user(token: str, db: AsyncSession) -> User:
    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub", "")
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise AuthenticationError("Invalid or expired access token")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid access token. Raises 401 if missing/invalid."""
    token = _extract_token_from_request(request)
    if not token:
        raise AuthenticationError("Authentication required")
    return await _resolve_user(token, db)


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return current user or None — never raises."""
    token = _extract_token_from_request(request)
    if not token:
        return None
    try:
        return await _resolve_user(token, db)
    except AuthenticationError:
        return None


# ---------------------------------------------------------------------------
# Typed dict payload (for controllers that just need the raw JWT claims)
# ---------------------------------------------------------------------------
def get_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    token = None
    if credentials:
        token = credentials.credentials
    elif request:
        token = request.cookies.get("access_token")
    if not token:
        raise AuthenticationError("Authentication required")
    try:
        return decode_access_token(token)
    except JWTError:
        raise AuthenticationError("Invalid or expired access token")
