"""Add market_price column to trades (market price at time of booking).

Revision ID: 005_add_market_price_to_trades
Revises: 004_drop_trades_price_column
Create Date: 2026-04-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005_add_market_price_to_trades"
down_revision = "004_drop_trades_price_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trades") as batch_op:
        batch_op.add_column(sa.Column("market_price", sa.Float, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("trades") as batch_op:
        batch_op.drop_column("market_price")
