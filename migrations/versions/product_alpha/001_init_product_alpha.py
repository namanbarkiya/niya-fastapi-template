"""product_alpha — initial schema and tables

Creates the product_alpha schema and the resources table.
When adding more tables for this product, create a new migration file
in this directory (002_..., 003_...).

Revision ID: product_alpha_001
Revises: 004_group_d   (runs after all shared migrations)
Create Date: 2026-03-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "product_alpha_001"
down_revision: Union[str, None] = "004_group_d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the product schema — every product gets its own namespace.
    op.execute("CREATE SCHEMA IF NOT EXISTS product_alpha")

    # resources table — template entity demonstrating the product model pattern.
    # NOTE: user_id has NO ForeignKey to shared.users — this is intentional.
    #       Cross-schema FKs would prevent future extraction of this product
    #       to its own database. Use application-level lookups instead.
    op.create_table(
        "resources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            nullable=False,
            index=True,
            # No ForeignKey here — plain UUID reference to shared.users.id
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("data", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="product_alpha",
    )


def downgrade() -> None:
    op.drop_table("resources", schema="product_alpha")
    op.execute("DROP SCHEMA IF EXISTS product_alpha CASCADE")
