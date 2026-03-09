"""
Integration tests for product_alpha resource routes.
Tests the full HTTP stack: middleware → routes → service → DB.

Demonstrates:
  - Unauthenticated requests → 401
  - Authenticated but no product access (missing "alpha" in JWT) → 403
  - Valid authenticated requests → 2xx
"""
import uuid

import pytest
from httpx import AsyncClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def _resource_payload(**kwargs) -> dict:
    return {"title": "Test Resource", "description": "A test", **kwargs}


# ─────────────────────────────────────────────────────────────────────────────
# Authentication / authorization enforcement
# ─────────────────────────────────────────────────────────────────────────────

async def test_list_resources_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.get("/api/alpha/resources")
    assert resp.status_code == 401


async def test_create_resource_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.post("/api/alpha/resources", json=_resource_payload())
    assert resp.status_code == 401


async def test_product_access_denied_returns_403(
    client: AsyncClient, test_user: dict
):
    """
    JWT with no 'alpha' product claim → ProductIdentificationMiddleware returns 403.
    The test_user fixture grants all products, so we craft a minimal token here.
    """
    from app.core.security import create_access_token

    # Token that explicitly has NO products
    restricted_token = create_access_token(
        subject=str(test_user["user"].id),
        extra={"email": test_user["email"], "products": [], "orgs": []},
    )
    resp = await client.get(
        "/api/alpha/resources",
        headers=_auth_headers(restricted_token),
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/alpha/resources
# ─────────────────────────────────────────────────────────────────────────────

async def test_list_resources_empty(client: AsyncClient, test_user: dict):
    resp = await client.get(
        "/api/alpha/resources",
        headers=_auth_headers(test_user["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/alpha/resources
# ─────────────────────────────────────────────────────────────────────────────

async def test_create_resource_returns_201(client: AsyncClient, test_user: dict):
    resp = await client.post(
        "/api/alpha/resources",
        json=_resource_payload(title="Created via API"),
        headers=_auth_headers(test_user["access_token"]),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Created via API"
    assert body["user_id"] == str(test_user["user"].id)
    assert body["is_active"] is True
    assert "id" in body


async def test_create_resource_missing_title_returns_422(
    client: AsyncClient, test_user: dict
):
    resp = await client.post(
        "/api/alpha/resources",
        json={"description": "no title"},
        headers=_auth_headers(test_user["access_token"]),
    )
    assert resp.status_code == 422


async def test_create_resource_with_data(client: AsyncClient, test_user: dict):
    payload = _resource_payload(data={"meta": "value", "count": 42})
    resp = await client.post(
        "/api/alpha/resources",
        json=payload,
        headers=_auth_headers(test_user["access_token"]),
    )
    assert resp.status_code == 201
    assert resp.json()["data"] == {"meta": "value", "count": 42}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/alpha/resources/{id}
# ─────────────────────────────────────────────────────────────────────────────

async def test_get_resource_success(client: AsyncClient, test_user: dict):
    create_resp = await client.post(
        "/api/alpha/resources",
        json=_resource_payload(title="Get Me"),
        headers=_auth_headers(test_user["access_token"]),
    )
    resource_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/api/alpha/resources/{resource_id}",
        headers=_auth_headers(test_user["access_token"]),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Get Me"


async def test_get_resource_not_found_returns_404(
    client: AsyncClient, test_user: dict
):
    resp = await client.get(
        f"/api/alpha/resources/{uuid.uuid4()}",
        headers=_auth_headers(test_user["access_token"]),
    )
    assert resp.status_code == 404


async def test_get_resource_wrong_owner_returns_403(
    client: AsyncClient, test_user: dict, db
):
    """Resource owned by one user — another user's token → 403."""
    from app.core.security import create_access_token

    other_user_id = uuid.uuid4()
    # Create resource as test_user
    create_resp = await client.post(
        "/api/alpha/resources",
        json=_resource_payload(title="Not Yours"),
        headers=_auth_headers(test_user["access_token"]),
    )
    resource_id = create_resp.json()["id"]

    # Try to get it as a different user
    other_token = create_access_token(
        subject=str(other_user_id),
        extra={"email": "other@example.com", "products": ["alpha"], "orgs": []},
    )
    resp = await client.get(
        f"/api/alpha/resources/{resource_id}",
        headers=_auth_headers(other_token),
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/alpha/resources/{id}
# ─────────────────────────────────────────────────────────────────────────────

async def test_update_resource(client: AsyncClient, test_user: dict):
    create_resp = await client.post(
        "/api/alpha/resources",
        json=_resource_payload(title="Before"),
        headers=_auth_headers(test_user["access_token"]),
    )
    resource_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/alpha/resources/{resource_id}",
        json={"title": "After"},
        headers=_auth_headers(test_user["access_token"]),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "After"


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/alpha/resources/{id}
# ─────────────────────────────────────────────────────────────────────────────

async def test_delete_resource(client: AsyncClient, test_user: dict):
    create_resp = await client.post(
        "/api/alpha/resources",
        json=_resource_payload(title="Delete Me"),
        headers=_auth_headers(test_user["access_token"]),
    )
    resource_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/alpha/resources/{resource_id}",
        headers=_auth_headers(test_user["access_token"]),
    )
    assert del_resp.status_code == 200

    # Verify soft-deleted resource no longer returns in list
    list_resp = await client.get(
        "/api/alpha/resources",
        headers=_auth_headers(test_user["access_token"]),
    )
    ids = [r["id"] for r in list_resp.json()]
    assert resource_id not in ids
