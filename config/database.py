"""
Async SQLAlchemy engine and session factory.

Works with any PostgreSQL instance — local or cloud — by reading DATABASE_URL
from the environment. Switch databases by updating that single env var.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings

import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Engine — created once at startup
# ---------------------------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,          # log SQL queries in debug mode
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,           # verify connections before use
    pool_recycle=3600,            # recycle stale connections after 1 h
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,       # keep objects usable after commit
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Dependency — yields a session per request, always closes it
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Convenience context manager (for background tasks / scripts)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Ping the database. Returns True if the connection is healthy."""
    try:
        from sqlalchemy import text
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health-check failed: {e}")
        return False
