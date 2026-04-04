"""Drop obsolete trades.price column (replaced by execution_price + limit_price).

Revision ID: 004_drop_trades_price_column
Revises: 003_add_user_accounts
Create Date: 2026-04-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004_drop_trades_price_column"
down_revision = "003_add_user_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode required by SQLite to drop/alter columns
    with op.batch_alter_table("trades") as batch_op:
        batch_op.drop_column("price")


def downgrade() -> None:
    with op.batch_alter_table("trades") as batch_op:
        batch_op.add_column(sa.Column("price", sa.Float, nullable=True))
