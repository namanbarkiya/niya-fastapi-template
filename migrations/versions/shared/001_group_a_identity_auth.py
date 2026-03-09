"""Group A — Identity & Auth tables

Create shared schema and all Group A tables:
users, user_profiles, user_emails, auth_sessions, auth_providers, email_verification_tokens

Revision ID: 001_group_a
Revises: None
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001_group_a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create shared schema
    op.execute("CREATE SCHEMA IF NOT EXISTS shared")

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # --- user_profiles ---
    op.create_table(
        "user_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("shared.users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(50), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en"),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("banner_url", sa.Text, nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("website", sa.Text, nullable=True),
        sa.Column("twitter_url", sa.Text, nullable=True),
        sa.Column("linkedin_url", sa.Text, nullable=True),
        sa.Column("github_url", sa.Text, nullable=True),
        sa.Column("company", sa.String(100), nullable=True),
        sa.Column("job_title", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(50), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("email_notifications", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("push_notifications", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("marketing_emails", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # --- user_emails ---
    op.create_table(
        "user_emails",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("shared.users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # --- auth_sessions ---
    op.create_table(
        "auth_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("shared.users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token_hash", sa.Text, unique=True, nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # --- auth_providers ---
    op.create_table(
        "auth_providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("shared.users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_auth_provider_user"),
        schema="shared",
    )

    # --- email_verification_tokens ---
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("shared.users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token", sa.Text, nullable=False, index=True),
        sa.Column("token_type", sa.String(20), nullable=False, server_default="email_verify"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )


def downgrade() -> None:
    op.drop_table("email_verification_tokens", schema="shared")
    op.drop_table("auth_providers", schema="shared")
    op.drop_table("auth_sessions", schema="shared")
    op.drop_table("user_emails", schema="shared")
    op.drop_table("user_profiles", schema="shared")
    op.drop_table("users", schema="shared")
    op.execute("DROP SCHEMA IF EXISTS shared CASCADE")
