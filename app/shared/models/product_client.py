"""
Shared schema model: ProductClient.
Maps a public client key (sent as X-Product-Client-Key header by each frontend)
to a product identifier. Used by middleware to identify which product a request
belongs to without trusting user-supplied input.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, ARRAY, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class ProductClient(Base):
    __tablename__ = "product_clients"
    __table_args__ = {"schema": "shared"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    client_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    allowed_origins: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
