"""
Shared schema model: ProviderLink.
Maps internal entities to external payment provider IDs (Razorpay, Stripe, etc.).
Keeps core billing tables provider-agnostic.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProviderLink(Base):
    __tablename__ = "provider_links"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "provider", name="uq_provider_link_entity"
        ),
        {"schema": "shared"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # e.g. "customer", "subscription", "payment_method"
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # e.g. "razorpay", "stripe"
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_data: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Extra JSON from the provider
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
