"""initial schema

Revision ID: 20260402_0001
Revises: None
Create Date: 2026-04-02 09:50:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260402_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "browser_login_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("login_type", sa.String(length=32), nullable=True),
        sa.Column("storage_state_path", sa.Text(), nullable=False),
        sa.Column("cookie_hash", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("expire_risk_level", sa.String(length=32), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("operator", sa.String(length=128), nullable=True),
        sa.Column("last_login_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_valid_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_browser_login_state_account_id", "browser_login_state", ["account_id"], unique=False)
    op.create_index("ix_browser_login_state_platform", "browser_login_state", ["platform"], unique=False)

    op.create_table(
        "platform_account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_no", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("account_handle", sa.String(length=128), nullable=True),
        sa.Column("nickname", sa.String(length=255), nullable=True),
        sa.Column("account_type", sa.String(length=64), nullable=True),
        sa.Column("is_competitor", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("homepage_url", sa.Text(), nullable=True),
        sa.Column("live_room_url", sa.Text(), nullable=True),
        sa.Column("discover_source", sa.String(length=128), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("account_no"),
    )
    op.create_index("ix_platform_account_account_id", "platform_account", ["account_id"], unique=False)
    op.create_index("ix_platform_account_account_no", "platform_account", ["account_no"], unique=True)
    op.create_index("ix_platform_account_platform", "platform_account", ["platform"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_platform_account_platform", table_name="platform_account")
    op.drop_index("ix_platform_account_account_no", table_name="platform_account")
    op.drop_index("ix_platform_account_account_id", table_name="platform_account")
    op.drop_table("platform_account")

    op.drop_index("ix_browser_login_state_platform", table_name="browser_login_state")
    op.drop_index("ix_browser_login_state_account_id", table_name="browser_login_state")
    op.drop_table("browser_login_state")
