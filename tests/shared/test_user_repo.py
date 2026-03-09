"""
Tests for UserRepo — CRUD operations on users, profiles, emails.
These are pure DB tests: no HTTP, no service layer.
"""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.repos.user_repo import UserRepo


# ─────────────────────────────────────────────────────────────────────────────
# User CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def test_create_and_get_by_id(db: AsyncSession):
    repo = UserRepo(db)
    user = await repo.create(email="alice@example.com", email_verified=False)
    await db.flush()

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.id == user.id
    assert fetched.email == "alice@example.com"


async def test_create_normalises_email(db: AsyncSession):
    """Emails are stored lower-cased regardless of input case."""
    repo = UserRepo(db)
    user = await repo.create(email="UPPER@Example.COM")
    assert user.email == "upper@example.com"


async def test_get_by_email(db: AsyncSession):
    repo = UserRepo(db)
    await repo.create(email="bob@example.com")
    await db.flush()

    found = await repo.get_by_email("BOB@EXAMPLE.COM")  # case-insensitive
    assert found is not None
    assert found.email == "bob@example.com"


async def test_get_by_email_not_found(db: AsyncSession):
    repo = UserRepo(db)
    result = await repo.get_by_email("nobody@example.com")
    assert result is None


async def test_get_by_id_not_found(db: AsyncSession):
    repo = UserRepo(db)
    result = await repo.get_by_id(uuid.uuid4())
    assert result is None


async def test_update_user(db: AsyncSession):
    repo = UserRepo(db)
    user = await repo.create(email="carol@example.com")
    await db.flush()

    updated = await repo.update(user.id, email_verified=True)
    assert updated.email_verified is True


async def test_verify_email(db: AsyncSession):
    repo = UserRepo(db)
    user = await repo.create(email="dan@example.com", email_verified=False)
    await db.flush()

    await repo.verify_email(user.id)
    await db.flush()

    fetched = await repo.get_by_id(user.id)
    assert fetched.email_verified is True


# ─────────────────────────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────────────────────────

async def test_create_and_get_profile(db: AsyncSession):
    repo = UserRepo(db)
    user = await repo.create(email="eve@example.com")
    await db.flush()

    profile = await repo.create_profile(user.id, full_name="Eve Smith")
    await db.flush()

    fetched = await repo.get_profile(user.id)
    assert fetched is not None
    assert fetched.full_name == "Eve Smith"
    assert fetched.user_id == user.id


async def test_update_profile(db: AsyncSession):
    repo = UserRepo(db)
    user = await repo.create(email="frank@example.com")
    await db.flush()
    await repo.create_profile(user.id)
    await db.flush()

    updated = await repo.update_profile(user.id, {"bio": "Hello world"})
    assert updated.bio == "Hello world"


# ─────────────────────────────────────────────────────────────────────────────
# Emails
# ─────────────────────────────────────────────────────────────────────────────

async def test_add_and_list_emails(db: AsyncSession):
    repo = UserRepo(db)
    user = await repo.create(email="grace@example.com")
    await db.flush()

    primary = await repo.add_email(user.id, "grace@example.com", is_primary=True)
    secondary = await repo.add_email(user.id, "grace2@example.com", is_primary=False)
    await db.flush()

    emails = await repo.get_emails(user.id)
    assert len(emails) == 2
    # Primary comes first (ordered by is_primary DESC)
    assert emails[0].is_primary is True


async def test_verify_user_email(db: AsyncSession):
    repo = UserRepo(db)
    user = await repo.create(email="henry@example.com")
    await db.flush()
    email_rec = await repo.add_email(user.id, "henry@example.com", is_primary=True)
    await db.flush()

    await repo.verify_user_email(email_rec.id)
    await db.flush()

    fetched = await repo.get_email_by_address("henry@example.com")
    assert fetched.is_verified is True


async def test_get_email_by_address_not_found(db: AsyncSession):
    repo = UserRepo(db)
    result = await repo.get_email_by_address("notexist@example.com")
    assert result is None
