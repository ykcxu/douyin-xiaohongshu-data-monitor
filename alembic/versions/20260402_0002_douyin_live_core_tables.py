"""douyin live core tables

Revision ID: 20260402_0002
Revises: 20260402_0001
Create Date: 2026-04-02 10:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0002"
down_revision = "20260402_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "douyin_live_room",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_account_id", sa.Integer(), nullable=True),
        sa.Column("room_id", sa.String(length=128), nullable=False),
        sa.Column("room_handle", sa.String(length=128), nullable=True),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("sec_account_id", sa.String(length=128), nullable=True),
        sa.Column("nickname", sa.String(length=255), nullable=True),
        sa.Column("live_title", sa.Text(), nullable=True),
        sa.Column("room_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("is_monitor_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("monitor_priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("last_live_status", sa.String(length=32), nullable=True),
        sa.Column("last_live_start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_live_end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["platform_account_id"], ["platform_account.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("room_id"),
    )
    op.create_index("ix_douyin_live_room_account_id", "douyin_live_room", ["account_id"], unique=False)
    op.create_index("ix_douyin_live_room_platform_account_id", "douyin_live_room", ["platform_account_id"], unique=False)
    op.create_index("ix_douyin_live_room_room_id", "douyin_live_room", ["room_id"], unique=True)

    op.create_table(
        "douyin_live_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("live_room_id", sa.Integer(), nullable=False),
        sa.Column("session_no", sa.String(length=128), nullable=False),
        sa.Column("room_id", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="live"),
        sa.Column("live_title", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("end_reason", sa.String(length=64), nullable=True),
        sa.Column("first_snapshot_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_snapshot_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["live_room_id"], ["douyin_live_room.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_no"),
    )
    op.create_index("ix_douyin_live_session_account_id", "douyin_live_session", ["account_id"], unique=False)
    op.create_index("ix_douyin_live_session_end_time", "douyin_live_session", ["end_time"], unique=False)
    op.create_index("ix_douyin_live_session_live_room_id", "douyin_live_session", ["live_room_id"], unique=False)
    op.create_index("ix_douyin_live_session_room_id", "douyin_live_session", ["room_id"], unique=False)
    op.create_index("ix_douyin_live_session_session_no", "douyin_live_session", ["session_no"], unique=True)
    op.create_index("ix_douyin_live_session_start_time", "douyin_live_session", ["start_time"], unique=False)
    op.create_index("ix_douyin_live_session_status", "douyin_live_session", ["status"], unique=False)

    op.create_table(
        "douyin_live_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("live_room_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("live_status", sa.String(length=32), nullable=False),
        sa.Column("online_count", sa.BigInteger(), nullable=True),
        sa.Column("total_viewer_count", sa.BigInteger(), nullable=True),
        sa.Column("new_viewer_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("new_like_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("new_comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("gift_count", sa.BigInteger(), nullable=True),
        sa.Column("gift_amount", sa.BigInteger(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["live_room_id"], ["douyin_live_room.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["douyin_live_session.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_douyin_live_snapshot_live_room_id", "douyin_live_snapshot", ["live_room_id"], unique=False)
    op.create_index("ix_douyin_live_snapshot_live_status", "douyin_live_snapshot", ["live_status"], unique=False)
    op.create_index("ix_douyin_live_snapshot_session_id", "douyin_live_snapshot", ["session_id"], unique=False)
    op.create_index("ix_douyin_live_snapshot_snapshot_time", "douyin_live_snapshot", ["snapshot_time"], unique=False)

    op.create_table(
        "douyin_live_comment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("live_room_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetch_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("sec_user_id", sa.String(length=128), nullable=True),
        sa.Column("nickname", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("province", sa.String(length=128), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("fan_level", sa.Integer(), nullable=True),
        sa.Column("user_level", sa.Integer(), nullable=True),
        sa.Column("is_anchor", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_room_manager", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_fans_group_member", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_new_fan", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_plain", sa.Text(), nullable=True),
        sa.Column("emoji_text", sa.Text(), nullable=True),
        sa.Column("mentioned_users", sa.Text(), nullable=True),
        sa.Column("extra_badges", sa.Text(), nullable=True),
        sa.Column("device_info", sa.Text(), nullable=True),
        sa.Column("ip_location", sa.String(length=255), nullable=True),
        sa.Column("risk_flags", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("raw_file_path", sa.Text(), nullable=True),
        sa.Column("raw_line_no", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["live_room_id"], ["douyin_live_room.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["douyin_live_session.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index("ix_douyin_live_comment_event_time", "douyin_live_comment", ["event_time"], unique=False)
    op.create_index("ix_douyin_live_comment_fetch_time", "douyin_live_comment", ["fetch_time"], unique=False)
    op.create_index("ix_douyin_live_comment_live_room_id", "douyin_live_comment", ["live_room_id"], unique=False)
    op.create_index("ix_douyin_live_comment_message_id", "douyin_live_comment", ["message_id"], unique=True)
    op.create_index("ix_douyin_live_comment_message_type", "douyin_live_comment", ["message_type"], unique=False)
    op.create_index("ix_douyin_live_comment_session_id", "douyin_live_comment", ["session_id"], unique=False)
    op.create_index("ix_douyin_live_comment_user_id", "douyin_live_comment", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_douyin_live_comment_user_id", table_name="douyin_live_comment")
    op.drop_index("ix_douyin_live_comment_session_id", table_name="douyin_live_comment")
    op.drop_index("ix_douyin_live_comment_message_type", table_name="douyin_live_comment")
    op.drop_index("ix_douyin_live_comment_message_id", table_name="douyin_live_comment")
    op.drop_index("ix_douyin_live_comment_live_room_id", table_name="douyin_live_comment")
    op.drop_index("ix_douyin_live_comment_fetch_time", table_name="douyin_live_comment")
    op.drop_index("ix_douyin_live_comment_event_time", table_name="douyin_live_comment")
    op.drop_table("douyin_live_comment")

    op.drop_index("ix_douyin_live_snapshot_snapshot_time", table_name="douyin_live_snapshot")
    op.drop_index("ix_douyin_live_snapshot_session_id", table_name="douyin_live_snapshot")
    op.drop_index("ix_douyin_live_snapshot_live_status", table_name="douyin_live_snapshot")
    op.drop_index("ix_douyin_live_snapshot_live_room_id", table_name="douyin_live_snapshot")
    op.drop_table("douyin_live_snapshot")

    op.drop_index("ix_douyin_live_session_status", table_name="douyin_live_session")
    op.drop_index("ix_douyin_live_session_start_time", table_name="douyin_live_session")
    op.drop_index("ix_douyin_live_session_session_no", table_name="douyin_live_session")
    op.drop_index("ix_douyin_live_session_room_id", table_name="douyin_live_session")
    op.drop_index("ix_douyin_live_session_live_room_id", table_name="douyin_live_session")
    op.drop_index("ix_douyin_live_session_end_time", table_name="douyin_live_session")
    op.drop_index("ix_douyin_live_session_account_id", table_name="douyin_live_session")
    op.drop_table("douyin_live_session")

    op.drop_index("ix_douyin_live_room_room_id", table_name="douyin_live_room")
    op.drop_index("ix_douyin_live_room_platform_account_id", table_name="douyin_live_room")
    op.drop_index("ix_douyin_live_room_account_id", table_name="douyin_live_room")
    op.drop_table("douyin_live_room")
