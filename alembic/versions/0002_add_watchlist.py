"""add watchlist table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(10),
            sa.ForeignKey("market.instruments.symbol"),
            nullable=False,
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "symbol"),
        schema="trading",
    )
    op.create_index(
        "idx_watchlist_user", "watchlist", ["user_id"], schema="trading"
    )


def downgrade() -> None:
    op.drop_index("idx_watchlist_user", table_name="watchlist", schema="trading")
    op.drop_table("watchlist", schema="trading")
