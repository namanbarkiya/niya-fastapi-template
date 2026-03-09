"""Group B — Organizations tables

organizations, org_memberships, org_invites, product_access

Revision ID: 002_group_b
Revises: 001_group_a
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002_group_b"
down_revision: Union[str, None] = "001_group_a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    op.create_table(
        "org_memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("shared.organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("shared.users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_membership"),
        schema="shared",
    )

    op.create_table(
        "org_invites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("shared.organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("token", sa.Text, unique=True, nullable=False, index=True),
        sa.Column("invited_by", UUID(as_uuid=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    op.create_table(
        "product_access",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("shared.users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("shared.organizations.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("product", sa.String(50), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "product", name="uq_user_product_access"),
        schema="shared",
    )


def downgrade() -> None:
    op.drop_table("product_access", schema="shared")
    op.drop_table("org_invites", schema="shared")
    op.drop_table("org_memberships", schema="shared")
    op.drop_table("organizations", schema="shared")
