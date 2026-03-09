"""
taskboard model: Project.

A project groups tasks and belongs to a user.

KEY RULES:
  - schema = "taskboard", never "shared"
  - user_id is a plain UUID — NO ForeignKey to shared.users
  - All timestamps UTC (TIMESTAMPTZ)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"schema": "taskboard"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Plain UUID — no FK to shared.users (intentional decoupling)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(
        String(7), nullable=True
    )  # hex color, e.g. "#3b82f6"
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    # Relationship — within product schema, FKs are fine
    tasks: Mapped[list["Task"]] = relationship(  # type: ignore[name-defined]
        "Task", back_populates="project", lazy="raise", passive_deletes=True
    )
