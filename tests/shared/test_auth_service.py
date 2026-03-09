"""
Tests for AuthService — register, login, token refresh, logout.

All external I/O is either:
  - Email sending: no-ops (SMTP not configured, falls back to console print)
  - DB: real SQLAlchemy session against the test database
"""
import pytest
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import decode_access_token
from app.shared.schemas.auth import LoginRequest, RegisterRequest
from app.shared.services.auth_service import AuthService


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_register(email: str = "user@example.com", password: str = "Pass123!") -> RegisterRequest:
    return RegisterRequest(email=email, password=password, name="Test User")


def _make_login(email: str = "user@example.com", password: str = "Pass123!") -> LoginRequest:
    return LoginRequest(email=email, password=password)


class _FakeResponse:
    """Minimal stand-in for FastAPI Response (used to capture cookies)."""
    def __init__(self):
        self.cookies: dict[str, str] = {}

    def set_cookie(self, key, value, **kwargs):
        self.cookies[key] = value

    def delete_cookie(self, key, **kwargs):
        self.cookies.pop(key, None)


# ─────────────────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────────────────

async def test_register_success(db: AsyncSession):
    svc = AuthService(db)
    with patch("app.shared.services.auth_service.send_verification_otp"):
        result = await svc.register(_make_register())

    assert result["status"] == "success"
    assert result["user"].email == "user@example.com"


async def test_register_duplicate_email_raises(db: AsyncSession):
    svc = AuthService(db)
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await svc.register(_make_register())
        await db.flush()

        with pytest.raises(ConflictError, match="already exists"):
            await svc.register(_make_register())


async def test_register_creates_profile(db: AsyncSession):
    from app.shared.repos.user_repo import UserRepo

    svc = AuthService(db)
    with patch("app.shared.services.auth_service.send_verification_otp"):
        result = await svc.register(_make_register(email="profuser@example.com"))
    await db.flush()

    repo = UserRepo(db)
    profile = await repo.get_profile(result["user"].id)
    assert profile is not None
    assert profile.full_name == "Test User"


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

async def test_login_success(db: AsyncSession):
    svc = AuthService(db)
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await svc.register(_make_register(email="login@example.com"))
    await db.flush()

    resp = _FakeResponse()
    auth = await svc.login(_make_login(email="login@example.com"), resp)

    assert auth.access_token
    # JWT should decode correctly
    payload = decode_access_token(auth.access_token)
    assert payload["email"] == "login@example.com"
    # Cookies should be set
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password_raises(db: AsyncSession):
    svc = AuthService(db)
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await svc.register(_make_register(email="wrongpw@example.com"))
    await db.flush()

    resp = _FakeResponse()
    with pytest.raises(AuthenticationError, match="Invalid"):
        await svc.login(
            LoginRequest(email="wrongpw@example.com", password="BadPassword!"),
            resp,
        )


async def test_login_unknown_email_raises(db: AsyncSession):
    svc = AuthService(db)
    resp = _FakeResponse()
    with pytest.raises(AuthenticationError, match="Invalid"):
        await svc.login(LoginRequest(email="ghost@example.com", password="any"), resp)


# ─────────────────────────────────────────────────────────────────────────────
# Token refresh
# ─────────────────────────────────────────────────────────────────────────────

async def test_refresh_token_rotates_session(db: AsyncSession):
    svc = AuthService(db)
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await svc.register(_make_register(email="refresh@example.com"))
    await db.flush()

    resp1 = _FakeResponse()
    auth1 = await svc.login(_make_login(email="refresh@example.com"), resp1)
    await db.flush()

    raw_refresh = resp1.cookies["refresh_token"]
    resp2 = _FakeResponse()
    auth2 = await svc.refresh_token(raw_refresh, resp2)

    # New tokens issued
    assert auth2.access_token != auth1.access_token
    assert resp2.cookies["refresh_token"] != raw_refresh


async def test_refresh_invalid_token_raises(db: AsyncSession):
    svc = AuthService(db)
    resp = _FakeResponse()
    with pytest.raises(AuthenticationError, match="invalid or expired"):
        await svc.refresh_token("bad-token-value", resp)


# ─────────────────────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────────────────────

async def test_logout_clears_cookies(db: AsyncSession):
    svc = AuthService(db)
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await svc.register(_make_register(email="logout@example.com"))
    await db.flush()

    resp_login = _FakeResponse()
    await svc.login(_make_login(email="logout@example.com"), resp_login)
    await db.flush()

    resp_logout = _FakeResponse()
    # Seed the refresh token cookie (simulating a browser)
    resp_logout.cookies["refresh_token"] = resp_login.cookies["refresh_token"]

    result = await svc.logout(resp_login.cookies["refresh_token"], resp_logout)
    assert result["status"] == "success"
    # access_token cookie deleted
    assert "access_token" not in resp_logout.cookies


async def test_logout_with_no_token_is_safe(db: AsyncSession):
    """Logging out without a refresh token should not raise."""
    svc = AuthService(db)
    resp = _FakeResponse()
    result = await svc.logout(None, resp)
    assert result["status"] == "success"
