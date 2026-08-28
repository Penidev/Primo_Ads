"""Add payment tables: credit_purchases and processed_webhooks.

Revision ID: 0002_payments
Revises: 0001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_payments"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credit_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reference", sa.String(100), nullable=False, unique=True),
        sa.Column("gateway", sa.String(50), nullable=False),
        sa.Column("gateway_session_id", sa.String(255), nullable=True),
        sa.Column("package_slug", sa.String(50), nullable=True),
        sa.Column("plan_slug", sa.String(50), nullable=True),
        sa.Column("amount_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_credit_purchases_user", "credit_purchases", ["user_id"])
    op.create_index("ix_credit_purchases_reference", "credit_purchases", ["reference"])

    op.create_table(
        "processed_webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("gateway", sa.String(50), nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("gateway", "event_id", name="uq_webhook_gateway_event"),
    )


def downgrade() -> None:
    op.drop_table("processed_webhooks")
    op.drop_table("credit_purchases")
