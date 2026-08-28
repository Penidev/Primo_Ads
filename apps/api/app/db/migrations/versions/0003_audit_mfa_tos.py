"""Audit log, security events, MFA recovery codes, and ToS acceptance.

Revision ID: 0003_audit_mfa_tos
Revises: 0002_payments
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_audit_mfa_tos"
down_revision: str | None = "0002_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- audit_logs (append-only by policy) ---
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.String(255), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index(
        "ix_audit_logs_created", "audit_logs", [sa.text("created_at DESC")]
    )

    # --- security_events (alerting signals) ---
    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_security_events_type", "security_events", ["event_type"])
    op.create_index(
        "ix_security_events_created", "security_events", [sa.text("created_at DESC")]
    )

    # --- user columns for MFA recovery and legal acceptance ---
    op.add_column(
        "users",
        sa.Column("mfa_recovery_codes", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "users", sa.Column("tos_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("tos_version", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "tos_version")
    op.drop_column("users", "tos_accepted_at")
    op.drop_column("users", "mfa_recovery_codes")
    op.drop_table("security_events")
    op.drop_table("audit_logs")
