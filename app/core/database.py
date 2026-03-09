"""
Async SQLAlchemy engine, session factory, and schema-aware Base.

Supports schema routing via search_path for multi-product architecture.
Each product gets its own Postgres schema; shared tables live in the "shared" schema.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Engine — created once at startup
# ---------------------------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Schema routing — set search_path on each new connection
# ---------------------------------------------------------------------------
def _build_search_path() -> str:
    """Build a Postgres search_path that includes shared + all product schemas."""
    schemas = ["shared"] + list(settings.products) + ["public"]
    return ", ".join(schemas)


@event.listens_for(engine.sync_engine, "connect")
def _set_search_path(dbapi_connection, connection_record):
    """Set the default search_path for every new raw connection."""
    search_path = _build_search_path()
    cursor = dbapi_connection.cursor()
    cursor.execute(f"SET search_path TO {search_path}")
    cursor.close()


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
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health-check failed: {e}")
        return False
