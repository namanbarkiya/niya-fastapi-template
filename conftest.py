"""
Root conftest.py — test infrastructure for the entire project.

ISOLATION STRATEGY:
  - One test engine (session-scoped) pointing at TEST_DATABASE_URL.
  - All schemas + tables are created once per session, dropped at teardown.
  - Each test gets a fresh AsyncSession. The session is never committed —
    it is rolled back after the test, reverting all changes.
  - The FastAPI `get_db` dependency is overridden per test to yield
    the same session, so all requests within one test share one transaction.

REQUIRED ENV VAR (optional):
  TEST_DATABASE_URL  — defaults to localhost niya_test DB.
"""
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ── import the app + its database dependency ─────────────────────────────────
from app.main import app
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password

# ── import ALL models so Base.metadata knows every table ─────────────────────
import app.shared.models  # noqa: F401
import app.products.product_alpha.models  # noqa: F401
import app.products.taskboard.models  # noqa: F401

# ── test database URL ─────────────────────────────────────────────────────────
TEST_DATABASE_URL: str = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/niya_test",
)

# Product schemas that must exist before create_all()
_PRODUCT_SCHEMAS = ["shared", "product_alpha", "taskboard"]


# ─────────────────────────────────────────────────────────────────────────────
# Session-scoped engine — created once for the entire test run
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create the test engine, create all schemas + tables, yield, then drop all.
    Scope: session — runs once for the entire pytest session.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=0,
    )

    async with engine.begin() as conn:
        # Create schemas before creating tables
        for schema in _PRODUCT_SCHEMAS:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        # Create all tables from metadata
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        for schema in reversed(_PRODUCT_SCHEMAS):
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

    await engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Function-scoped session — rolls back after every test
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession for one test. Always rolled back at the end —
    no data from this test persists to the next.

    Using flush() (not commit()) throughout the service layer means rollback
    cleanly reverts everything written during the test.
    """
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# HTTP client — overrides get_db to use the test session
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    httpx.AsyncClient that talks to the real FastAPI app but uses the test
    session for all database access. Cookies are preserved across requests
    within the same test (useful for login → refresh flows).
    """
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=True,
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ─────────────────────────────────────────────────────────────────────────────
# Test user — a persisted user + valid JWT ready for authenticated tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> dict:
    """
    Create a test user, profile, and primary email record.
    Returns a dict with keys: user, access_token, refresh_token, password.

    The access_token's 'products' claim includes all registered products so
    product-access middleware passes without needing a real auth flow.
    """
    from app.shared.repos.user_repo import UserRepo

    email = f"testuser+{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"
    repo = UserRepo(db)

    user = await repo.create(
        email=email,
        password_hash=hash_password(password),
        email_verified=True,
    )
    await repo.create_profile(user.id, full_name="Test User")
    await repo.add_email(user.id, email, is_primary=True)
    await db.flush()

    access_token = create_access_token(
        subject=str(user.id),
        extra={
            "email": user.email,
            # Include all known products so middleware never blocks test requests
            "products": ["alpha", "taskboard"],
            "orgs": [],
        },
    )

    return {
        "user": user,
        "access_token": access_token,
        "password": password,
        "email": email,
    }
