"""
FastAPI dependency injection: get_db, get_current_user, get_current_user_optional.
"""
import logging
import uuid
from typing import Optional

from fastapi import Depends, Request
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.shared.models.user import User  # noqa: F401 — also registers all models
from app.shared.repos.user_repo import UserRepo

# Ensure all models are imported so SQLAlchemy resolves relationships
import app.shared.models  # noqa: F401

from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token extraction
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

    repo = UserRepo(db)
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


def get_product(request: Request) -> str:
    """
    Dependency that returns the product identifier set by ProductIdentificationMiddleware.
    Alias: use get_current_product for new code.
    """
    product = getattr(request.state, "product", None)
    if not product:
        raise ValidationError("Could not determine product from request path")
    return product


# Preferred alias — use this in all routes
get_current_product = get_product


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
