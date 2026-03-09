"""taskboard — initial schema and tables

Creates the taskboard schema, projects table, and tasks table.

Revision ID: taskboard_001
Revises: product_alpha_001
Create Date: 2026-03-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "taskboard_001"
down_revision: Union[str, None] = "product_alpha_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS taskboard")

    # -- Projects --
    # user_id: plain UUID, no FK to shared.users (intentional decoupling)
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="taskboard",
    )

    # -- Tasks --
    # created_by / assigned_to: plain UUIDs, no FK to shared.users
    # project_id: FK within the same schema — this is fine
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("taskboard.projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("assigned_to", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="todo"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="taskboard",
    )


def downgrade() -> None:
    op.drop_table("tasks", schema="taskboard")
    op.drop_table("projects", schema="taskboard")
    op.execute("DROP SCHEMA IF EXISTS taskboard CASCADE")
