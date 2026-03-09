"""
Unit tests for ResourceService.

UserRepo is mocked — these tests verify service logic in isolation,
without touching the database. Only the product repo uses the real DB.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.products.product_alpha.repos.resource_repo import ResourceRepo
from app.products.product_alpha.schemas.resource import (
    CreateResourceRequest,
    UpdateResourceRequest,
)
from app.products.product_alpha.services.resource_service import ResourceService


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _mock_user(user_id: uuid.UUID | None = None) -> MagicMock:
    """Return a mock User object."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "mock@example.com"
    user.is_active = True
    return user


def _make_service(db: AsyncSession, user_mock=None) -> tuple[ResourceService, AsyncMock]:
    """
    Build ResourceService with a mocked UserRepo and a real ResourceRepo.
    Returns (service, mock_user_repo).
    """
    mock_user_repo = AsyncMock()
    if user_mock is not None:
        mock_user_repo.get_by_id.return_value = user_mock
    else:
        mock_user_repo.get_by_id.return_value = None  # default: user not found

    resource_repo = ResourceRepo(db)
    svc = ResourceService(user_repo=mock_user_repo, resource_repo=resource_repo)
    return svc, mock_user_repo


# ─────────────────────────────────────────────────────────────────────────────
# create_resource
# ─────────────────────────────────────────────────────────────────────────────

async def test_create_resource_user_not_found(db: AsyncSession):
    """
    CROSS-SCHEMA PATTERN: UserRepo.get_by_id returns None
    → service raises NotFoundError before writing any product data.
    """
    user_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=None)

    with pytest.raises(NotFoundError, match="User not found"):
        await svc.create_resource(
            user_id,
            CreateResourceRequest(title="Should not be created"),
        )


async def test_create_resource_success(db: AsyncSession):
    """
    With a valid user (from mocked shared repo), resource is created in
    the product_alpha schema.
    """
    user_id = uuid.uuid4()
    svc, mock_repo = _make_service(db, user_mock=_mock_user(user_id))

    result = await svc.create_resource(
        user_id,
        CreateResourceRequest(title="My Resource", description="desc"),
    )

    # Verify UserRepo was queried (cross-schema lookup happened)
    mock_repo.get_by_id.assert_awaited_once_with(user_id)

    assert result.title == "My Resource"
    assert result.description == "desc"
    assert result.user_id == user_id
    assert result.is_active is True


async def test_create_resource_with_data(db: AsyncSession):
    """JSONB data field is stored and returned correctly."""
    user_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(user_id))

    payload = {"key": "value", "nested": {"n": 1}}
    result = await svc.create_resource(
        user_id,
        CreateResourceRequest(title="Data Resource", data=payload),
    )
    assert result.data == payload


# ─────────────────────────────────────────────────────────────────────────────
# get_resource
# ─────────────────────────────────────────────────────────────────────────────

async def test_get_resource_not_found(db: AsyncSession):
    user_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(user_id))

    with pytest.raises(NotFoundError):
        await svc.get_resource(user_id, uuid.uuid4())


async def test_get_resource_wrong_owner_raises_403(db: AsyncSession):
    """Ownership check — another user's resource raises AuthorizationError."""
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(owner_id))

    # Create a resource owned by owner_id
    created = await svc.create_resource(
        owner_id,
        CreateResourceRequest(title="Owner's Resource"),
    )
    await db.flush()

    # Attacker tries to get it
    with pytest.raises(AuthorizationError):
        await svc.get_resource(attacker_id, created.id)


async def test_get_resource_success(db: AsyncSession):
    user_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(user_id))

    created = await svc.create_resource(
        user_id, CreateResourceRequest(title="Findable")
    )
    await db.flush()

    fetched = await svc.get_resource(user_id, created.id)
    assert fetched.id == created.id
    assert fetched.title == "Findable"


# ─────────────────────────────────────────────────────────────────────────────
# list_resources
# ─────────────────────────────────────────────────────────────────────────────

async def test_list_resources_empty(db: AsyncSession):
    user_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(user_id))

    results = await svc.list_resources(user_id)
    assert results == []


async def test_list_resources_returns_only_own(db: AsyncSession):
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    svc_a, _ = _make_service(db, user_mock=_mock_user(user_a))
    svc_b, _ = _make_service(db, user_mock=_mock_user(user_b))

    await svc_a.create_resource(user_a, CreateResourceRequest(title="A1"))
    await svc_a.create_resource(user_a, CreateResourceRequest(title="A2"))
    await svc_b.create_resource(user_b, CreateResourceRequest(title="B1"))
    await db.flush()

    results_a = await svc_a.list_resources(user_a)
    results_b = await svc_b.list_resources(user_b)

    assert len(results_a) == 2
    assert len(results_b) == 1
    assert all(r.user_id == user_a for r in results_a)


# ─────────────────────────────────────────────────────────────────────────────
# update_resource
# ─────────────────────────────────────────────────────────────────────────────

async def test_update_resource_success(db: AsyncSession):
    user_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(user_id))

    created = await svc.create_resource(
        user_id, CreateResourceRequest(title="Original")
    )
    await db.flush()

    updated = await svc.update_resource(
        user_id,
        created.id,
        UpdateResourceRequest(title="Updated Title"),
    )
    assert updated.title == "Updated Title"


async def test_update_resource_wrong_owner(db: AsyncSession):
    owner = uuid.uuid4()
    other = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(owner))

    created = await svc.create_resource(owner, CreateResourceRequest(title="Mine"))
    await db.flush()

    with pytest.raises(AuthorizationError):
        await svc.update_resource(other, created.id, UpdateResourceRequest(title="Stolen"))


# ─────────────────────────────────────────────────────────────────────────────
# delete_resource
# ─────────────────────────────────────────────────────────────────────────────

async def test_delete_resource_soft_deletes(db: AsyncSession):
    user_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(user_id))

    created = await svc.create_resource(user_id, CreateResourceRequest(title="ToDelete"))
    await db.flush()

    result = await svc.delete_resource(user_id, created.id)
    assert result["status"] == "success"

    # Resource no longer appears in list (active_only=True is default)
    resources = await svc.list_resources(user_id)
    assert not any(r.id == created.id for r in resources)


async def test_delete_nonexistent_raises(db: AsyncSession):
    user_id = uuid.uuid4()
    svc, _ = _make_service(db, user_mock=_mock_user(user_id))

    with pytest.raises(NotFoundError):
        await svc.delete_resource(user_id, uuid.uuid4())
