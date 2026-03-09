"""Group C — Billing & Payments tables

customers, plans, subscriptions, payment_methods, transactions,
invoices, invoice_items, provider_links, webhook_events

Revision ID: 003_group_c
Revises: 002_group_b
Create Date: 2026-03-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003_group_c"
down_revision: Union[str, None] = "002_group_b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Customers --
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("shared.users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("shared.organizations.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # -- Plans --
    op.create_table(
        "plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price_amount", sa.Integer, nullable=False),
        sa.Column("price_currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("billing_interval", sa.String(20), nullable=False),
        sa.Column("trial_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("features", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # -- Subscriptions --
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("shared.customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("shared.plans.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("product", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="inactive"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # -- Payment Methods --
    op.create_table(
        "payment_methods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("shared.customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("last_four", sa.String(4), nullable=True),
        sa.Column("brand", sa.String(50), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # -- Transactions --
    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("shared.customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("shared.subscriptions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_method_id", UUID(as_uuid=True), sa.ForeignKey("shared.payment_methods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # -- Invoices --
    op.create_table(
        "invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("shared.customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("shared.subscriptions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("invoice_number", sa.String(100), unique=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Integer, nullable=False),
        sa.Column("tax", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # -- Invoice Items --
    op.create_table(
        "invoice_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("shared.invoices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price", sa.Integer, nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )

    # -- Provider Links --
    op.create_table(
        "provider_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("provider", sa.String(50), nullable=False, index=True),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("provider_data", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entity_type", "entity_id", "provider", name="uq_provider_link_entity"),
        schema="shared",
    )

    # -- Webhook Events --
    op.create_table(
        "webhook_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False, index=True),
        sa.Column("event_id", sa.String(255), unique=True, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="shared",
    )


def downgrade() -> None:
    op.drop_table("webhook_events", schema="shared")
    op.drop_table("provider_links", schema="shared")
    op.drop_table("invoice_items", schema="shared")
    op.drop_table("invoices", schema="shared")
    op.drop_table("transactions", schema="shared")
    op.drop_table("payment_methods", schema="shared")
    op.drop_table("subscriptions", schema="shared")
    op.drop_table("plans", schema="shared")
    op.drop_table("customers", schema="shared")
