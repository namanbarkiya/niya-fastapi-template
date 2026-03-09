"""Shared — product_clients table

Stores public client keys issued to each frontend app.
Used by middleware to identify which product a request belongs to,
without trusting user-supplied input.

Revision ID: 005_product_clients
Revises: 004_group_d
Create Date: 2026-03-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision: str = "005_product_clients"
down_revision: Union[str, None] = "004_group_d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product", sa.String(50), nullable=False),
        sa.Column("client_key", sa.String(100), nullable=False),
        sa.Column(
            "allowed_origins",
            ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="shared",
    )
    op.create_index(
        "ix_shared_product_clients_client_key",
        "product_clients",
        ["client_key"],
        unique=True,
        schema="shared",
    )
    op.create_index(
        "ix_shared_product_clients_product",
        "product_clients",
        ["product"],
        schema="shared",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shared_product_clients_product",
        table_name="product_clients",
        schema="shared",
    )
    op.drop_index(
        "ix_shared_product_clients_client_key",
        table_name="product_clients",
        schema="shared",
    )
    op.drop_table("product_clients", schema="shared")
