"""add external data tables: us_market_daily, institutional_flows, margin_trading

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── market.us_market_daily ──────────────────────────────────────────────
    op.create_table(
        "us_market_daily",
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("sp500_close", sa.Numeric(10, 2), nullable=True),
        sa.Column("sp500_change", sa.Numeric(8, 4), nullable=True),
        sa.Column("nasdaq_close", sa.Numeric(10, 2), nullable=True),
        sa.Column("nasdaq_change", sa.Numeric(8, 4), nullable=True),
        sa.Column("tsm_adr_close", sa.Numeric(10, 2), nullable=True),
        sa.Column("tsm_adr_change", sa.Numeric(8, 4), nullable=True),
        sa.Column("sox_close", sa.Numeric(10, 2), nullable=True),
        sa.Column("sox_change", sa.Numeric(8, 4), nullable=True),
        sa.Column("dxy_close", sa.Numeric(8, 4), nullable=True),
        sa.Column("dxy_change", sa.Numeric(8, 4), nullable=True),
        sa.Column("us10y_yield", sa.Numeric(6, 3), nullable=True),
        sa.Column("us10y_change_bps", sa.Numeric(6, 1), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        schema="market",
    )

    # ── market.institutional_flows ─────────────────────────────────────────
    op.create_table(
        "institutional_flows",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("foreign_net", sa.BigInteger, nullable=True),
        sa.Column("trust_buy", sa.BigInteger, nullable=True),
        sa.Column("trust_sell", sa.BigInteger, nullable=True),
        sa.Column("trust_net", sa.BigInteger, nullable=True),
        sa.Column("dealer_net", sa.BigInteger, nullable=True),
        sa.Column("total_net", sa.BigInteger, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("date", "symbol"),
        schema="market",
    )
    op.create_index(
        "idx_institutional_flows_date",
        "institutional_flows",
        ["date"],
        schema="market",
    )
    op.create_index(
        "idx_institutional_flows_symbol",
        "institutional_flows",
        ["symbol"],
        schema="market",
    )

    # ── market.margin_trading ──────────────────────────────────────────────
    op.create_table(
        "margin_trading",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("margin_buy", sa.BigInteger, nullable=True),
        sa.Column("margin_sell", sa.BigInteger, nullable=True),
        sa.Column("margin_balance_prev", sa.BigInteger, nullable=True),
        sa.Column("margin_balance", sa.BigInteger, nullable=True),
        sa.Column("short_buy", sa.BigInteger, nullable=True),
        sa.Column("short_sell", sa.BigInteger, nullable=True),
        sa.Column("short_balance_prev", sa.BigInteger, nullable=True),
        sa.Column("short_balance", sa.BigInteger, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint("date", "symbol"),
        schema="market",
    )
    op.create_index(
        "idx_margin_trading_date",
        "margin_trading",
        ["date"],
        schema="market",
    )
    op.create_index(
        "idx_margin_trading_symbol",
        "margin_trading",
        ["symbol"],
        schema="market",
    )


def downgrade() -> None:
    op.drop_index("idx_margin_trading_symbol", table_name="margin_trading", schema="market")
    op.drop_index("idx_margin_trading_date", table_name="margin_trading", schema="market")
    op.drop_table("margin_trading", schema="market")

    op.drop_index(
        "idx_institutional_flows_symbol",
        table_name="institutional_flows",
        schema="market",
    )
    op.drop_index(
        "idx_institutional_flows_date",
        table_name="institutional_flows",
        schema="market",
    )
    op.drop_table("institutional_flows", schema="market")

    op.drop_table("us_market_daily", schema="market")
