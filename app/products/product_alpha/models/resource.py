"""
product_alpha model: Resource.

This is a template model demonstrating the product schema pattern.

KEY RULES (never break these):
  1. __table_args__ schema = "product_alpha" — NOT "shared".
  2. user_id is a plain UUID column — NO ForeignKey to shared.users.
     This keeps schemas decoupled for future extraction.
  3. All monetary values in cents (Integer), all timestamps TIMESTAMPTZ.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Resource(Base):
    """
    A generic resource owned by a user.
    Replace with your actual domain entity (e.g. Project, Document, Workspace).
    """
    __tablename__ = "resources"
    # Every product uses its own schema — this is what keeps products isolated.
    __table_args__ = {"schema": "product_alpha"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Plain UUID — NO ForeignKey. Products reference shared data by UUID only.
    # This is intentional: it allows the product schema to be extracted to a
    # separate database without breaking FK constraints.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSONB for flexible structured data — avoids premature schema rigidity.
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        # Use server_default so DB-generated rows are consistent too.
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
        server_default=func.now(),
    )
