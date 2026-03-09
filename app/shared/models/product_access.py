"""
Shared schema model: ProductAccess.
Maps which products a user (or org) has access to.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProductAccess(Base):
    __tablename__ = "product_access"
    __table_args__ = (
        UniqueConstraint("user_id", "product", name="uq_user_product_access"),
        {"schema": "shared"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shared.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shared.organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user"
    )  # user, admin, etc.
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
