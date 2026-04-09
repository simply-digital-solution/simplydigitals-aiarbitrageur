"""Add filled_qty column to trades (quantity actually filled by broker).

Revision ID: 006_add_filled_qty_to_trades
Revises: 005_add_market_price_to_trades
Create Date: 2026-04-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006_add_filled_qty_to_trades"
down_revision = "005_add_market_price_to_trades"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trades") as batch_op:
        batch_op.add_column(sa.Column("filled_qty", sa.Float, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("trades") as batch_op:
        batch_op.drop_column("filled_qty")
