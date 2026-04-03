"""Add user_accounts table for local cash tracking.

Revision ID: 003_add_user_accounts
Revises: 002_alpaca_integration
Create Date: 2026-04-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "003_add_user_accounts"
down_revision = "002_alpaca_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, unique=True),
        sa.Column("cash", sa.Float, nullable=False, server_default="100000.0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_accounts_user_id", "user_accounts", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_accounts_user_id", table_name="user_accounts")
    op.drop_table("user_accounts")
