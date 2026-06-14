"""add pgvector extension and trading.settings table

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-08
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE IF NOT EXISTS trading.settings (
            key        VARCHAR(100) PRIMARY KEY,
            value      TEXT         NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("""
        INSERT INTO trading.settings (key, value)
        VALUES ('ai_interval_minutes', '30')
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS trading.settings")
    op.execute("DROP EXTENSION IF EXISTS vector")
