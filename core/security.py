"""
Security utilities: password hashing, JWT creation/validation, token generation.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from config.settings import settings

# ---------------------------------------------------------------------------
# Password hashing (bcrypt directly — avoids passlib/bcrypt 4.x incompatibility)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token_value() -> str:
    """Generate a cryptographically random opaque refresh token (URL-safe, 64 bytes)."""
    return secrets.token_urlsafe(64)


def hash_token(raw: str) -> str:
    """SHA-256 hash of a raw token for safe DB storage."""
    return hashlib.sha256(raw.encode()).hexdigest()


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises jose.JWTError on any failure.
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


# ---------------------------------------------------------------------------
# Misc secure token generation (email verify / password reset)
# ---------------------------------------------------------------------------
def generate_secure_token(nbytes: int = 32) -> str:
    """URL-safe random token for email verification and password reset."""
    return secrets.token_urlsafe(nbytes)
