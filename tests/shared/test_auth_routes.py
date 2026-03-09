"""
Integration tests for auth HTTP routes.
Uses AsyncClient against the live FastAPI app with a test DB session.
"""
import pytest
from unittest.mock import patch
from httpx import AsyncClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_REGISTER_PAYLOAD = {
    "email": "routeuser@example.com",
    "password": "RoutePass123!",
    "name": "Route User",
}

_LOGIN_PAYLOAD = {
    "email": "routeuser@example.com",
    "password": "RoutePass123!",
}


async def _register_and_login(client: AsyncClient, email_suffix: str = "") -> dict:
    """Register a user and return the login response dict + cookies."""
    email = f"route{email_suffix}@example.com"
    with patch("app.shared.services.auth_service.send_verification_otp"):
        reg = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "Pass123!", "name": "Test"},
        )
    assert reg.status_code == 201

    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Pass123!"},
    )
    assert login.status_code == 200
    return login.json()


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/register
# ─────────────────────────────────────────────────────────────────────────────

async def test_register_returns_201(client: AsyncClient):
    with patch("app.shared.services.auth_service.send_verification_otp"):
        resp = await client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "Valid123!", "name": "New"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert body["user"]["email"] == "new@example.com"


async def test_register_duplicate_returns_409(client: AsyncClient):
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "Valid123!", "name": "Dup"},
        )
        resp = await client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "Valid123!", "name": "Dup"},
        )
    assert resp.status_code == 409


async def test_register_invalid_email_returns_422(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "Valid123!", "name": "X"},
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/login
# ─────────────────────────────────────────────────────────────────────────────

async def test_login_returns_access_token(client: AsyncClient):
    data = await _register_and_login(client, email_suffix="login1")
    assert "access_token" in data


async def test_login_sets_cookies(client: AsyncClient):
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await client.post(
            "/api/auth/register",
            json={"email": "cookietest@example.com", "password": "Pass123!", "name": "C"},
        )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "cookietest@example.com", "password": "Pass123!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password_returns_401(client: AsyncClient):
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await client.post(
            "/api/auth/register",
            json={"email": "wrongpw@example.com", "password": "Pass123!", "name": "W"},
        )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "wrongpw@example.com", "password": "Wrong!"},
    )
    assert resp.status_code == 401


async def test_login_unknown_user_returns_401(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "any"},
    )
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/refresh
# ─────────────────────────────────────────────────────────────────────────────

async def test_refresh_returns_new_token(client: AsyncClient):
    """The httpx client preserves cookies set by login, so refresh works."""
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await client.post(
            "/api/auth/register",
            json={"email": "refresh@example.com", "password": "Pass123!", "name": "R"},
        )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "refresh@example.com", "password": "Pass123!"},
    )
    first_token = login_resp.json()["access_token"]

    refresh_resp = await client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 200
    second_token = refresh_resp.json()["access_token"]
    assert second_token != first_token


async def test_refresh_without_cookie_returns_401(client: AsyncClient):
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/logout
# ─────────────────────────────────────────────────────────────────────────────

async def test_logout_succeeds(client: AsyncClient):
    with patch("app.shared.services.auth_service.send_verification_otp"):
        await client.post(
            "/api/auth/register",
            json={"email": "logoutrt@example.com", "password": "Pass123!", "name": "L"},
        )
    await client.post(
        "/api/auth/login",
        json={"email": "logoutrt@example.com", "password": "Pass123!"},
    )

    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


async def test_logout_without_session_still_200(client: AsyncClient):
    """Logout is idempotent — no refresh cookie should still return 200."""
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
