"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Schemas ────────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS market")
    op.execute("CREATE SCHEMA IF NOT EXISTS trading")

    # ── public.users (managed by fastapi-users) ────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        schema="public",
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True, schema="public")

    # ── market.instruments ─────────────────────────────────────
    op.create_table(
        "instruments",
        sa.Column("symbol", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(100)),
        sa.Column("name_en", sa.String(100)),
        sa.Column("exchange", sa.String(10)),
        sa.Column("market", sa.String(10)),
        sa.Column("industry", sa.String(50)),
        sa.Column("security_type", sa.String(20)),
        sa.Column("board_lot", sa.Integer),
        sa.Column("trading_currency", sa.String(10)),
        sa.Column("can_day_trade", sa.Boolean),
        sa.Column("can_buy_day_trade", sa.Boolean),
        sa.Column("limit_up_price", sa.Numeric(10, 2)),
        sa.Column("limit_down_price", sa.Numeric(10, 2)),
        sa.Column("reference_price", sa.Numeric(10, 2)),
        sa.Column("is_attention", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_disposition", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_synced", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="market",
    )

    # ── market.market_quotes ───────────────────────────────────
    op.create_table(
        "market_quotes",
        sa.Column("symbol", sa.String(10), sa.ForeignKey("market.instruments.symbol"), primary_key=True),
        sa.Column("reference_price", sa.Numeric(10, 2)),
        sa.Column("prev_close", sa.Numeric(10, 2)),
        sa.Column("open_price", sa.Numeric(10, 2)),
        sa.Column("high_price", sa.Numeric(10, 2)),
        sa.Column("low_price", sa.Numeric(10, 2)),
        sa.Column("close_price", sa.Numeric(10, 2)),
        sa.Column("last_price", sa.Numeric(10, 2)),
        sa.Column("last_size", sa.Integer),
        sa.Column("avg_price", sa.Numeric(10, 2)),
        sa.Column("change", sa.Numeric(10, 2)),
        sa.Column("change_pct", sa.Numeric(8, 4)),
        sa.Column("amplitude", sa.Numeric(8, 4)),
        sa.Column("bids", JSONB),
        sa.Column("asks", JSONB),
        sa.Column("total", JSONB),
        sa.Column("is_limit_up", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_limit_down", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_trial", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="market",
    )

    # ── market.intraday_candles ────────────────────────────────
    op.create_table(
        "intraday_candles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(10, 2)),
        sa.Column("high", sa.Numeric(10, 2)),
        sa.Column("low", sa.Numeric(10, 2)),
        sa.Column("close", sa.Numeric(10, 2)),
        sa.Column("volume", sa.BigInteger),
        sa.Column("average", sa.Numeric(10, 2)),
        sa.UniqueConstraint("symbol", "timeframe", "ts"),
        schema="market",
    )
    op.create_index(
        "idx_intraday_symbol_tf", "intraday_candles",
        ["symbol", "timeframe", sa.text("ts DESC")], schema="market",
    )

    # ── market.historical_candles ──────────────────────────────
    op.create_table(
        "historical_candles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("open", sa.Numeric(10, 2)),
        sa.Column("high", sa.Numeric(10, 2)),
        sa.Column("low", sa.Numeric(10, 2)),
        sa.Column("close", sa.Numeric(10, 2)),
        sa.Column("volume", sa.BigInteger),
        sa.Column("turnover", sa.Numeric(20, 2)),
        sa.Column("change", sa.Numeric(10, 2)),
        sa.UniqueConstraint("symbol", "timeframe", "date"),
        schema="market",
    )
    op.create_index(
        "idx_historical_symbol_tf", "historical_candles",
        ["symbol", "timeframe", sa.text("date DESC")], schema="market",
    )

    # ── trading.portfolios ─────────────────────────────────────
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("initial_capital", sa.Numeric(15, 2), nullable=False),
        sa.Column("cash", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id"),
        schema="trading",
    )

    # ── trading.holdings (含 GENERATED ALWAYS AS) ──────────────
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("company_name", sa.String(100)),
        sa.Column("shares", sa.Integer, sa.CheckConstraint("shares > 0"), nullable=False),
        sa.Column("avg_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("current_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "symbol"),
        schema="trading",
    )
    op.execute("""
        ALTER TABLE trading.holdings
        ADD COLUMN market_value   NUMERIC(15,2) GENERATED ALWAYS AS (shares * current_price) STORED,
        ADD COLUMN unrealized_pnl NUMERIC(15,2) GENERATED ALWAYS AS (shares * (current_price - avg_cost)) STORED
    """)

    # ── trading.trades ─────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("company_name", sa.String(100)),
        sa.Column("action", sa.String(4), sa.CheckConstraint("action IN ('BUY', 'SELL')"), nullable=False),
        sa.Column("shares", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("decision_reason", sa.Text),
        sa.Column("realized_pnl", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("realized_pnl_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="trading",
    )
    op.create_index("idx_trades_user_symbol", "trades", ["user_id", "symbol"], schema="trading")
    op.create_index(
        "idx_trades_created_at", "trades", [sa.text("created_at DESC")], schema="trading"
    )

    # ── trading.ai_decisions ───────────────────────────────────
    op.create_table(
        "ai_decisions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("analysis", sa.Text),
        sa.Column("decisions", JSONB),
        sa.Column("market_summary", sa.Text),
        sa.Column("model_used", sa.String(100)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("execution_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("agent_reports", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="trading",
    )
    op.create_index(
        "idx_ai_decisions_user", "ai_decisions",
        ["user_id", sa.text("created_at DESC")], schema="trading",
    )

    # ── trading.daily_performance ──────────────────────────────
    op.create_table(
        "daily_performance",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("total_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("cash", sa.Numeric(15, 2), nullable=False),
        sa.Column("holdings_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("daily_return_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("cumulative_return_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("total_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column("winning_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "date"),
        schema="trading",
    )


def downgrade() -> None:
    op.drop_table("daily_performance", schema="trading")
    op.drop_table("ai_decisions", schema="trading")
    op.drop_table("trades", schema="trading")
    op.drop_table("holdings", schema="trading")
    op.drop_table("portfolios", schema="trading")
    op.drop_table("historical_candles", schema="market")
    op.drop_table("intraday_candles", schema="market")
    op.drop_table("market_quotes", schema="market")
    op.drop_table("instruments", schema="market")
    op.drop_table("users", schema="public")
    op.execute("DROP SCHEMA IF EXISTS trading")
    op.execute("DROP SCHEMA IF EXISTS market")
