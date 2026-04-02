"""xiaohongshu core tables

Revision ID: 20260402_0003
Revises: 20260402_0002
Create Date: 2026-04-02 11:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_0003"
down_revision = "20260402_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "xiaohongshu_account_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_account_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("account_handle", sa.String(length=128), nullable=True),
        sa.Column("nickname", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("follower_count", sa.BigInteger(), nullable=True),
        sa.Column("following_count", sa.BigInteger(), nullable=True),
        sa.Column("liked_count", sa.BigInteger(), nullable=True),
        sa.Column("note_count", sa.BigInteger(), nullable=True),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["platform_account_id"], ["platform_account.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_xiaohongshu_account_snapshot_account_id",
        "xiaohongshu_account_snapshot",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_xiaohongshu_account_snapshot_platform_account_id",
        "xiaohongshu_account_snapshot",
        ["platform_account_id"],
        unique=False,
    )
    op.create_index(
        "ix_xiaohongshu_account_snapshot_snapshot_time",
        "xiaohongshu_account_snapshot",
        ["snapshot_time"],
        unique=False,
    )

    op.create_table(
        "xiaohongshu_note",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_account_id", sa.Integer(), nullable=True),
        sa.Column("note_id", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("note_title", sa.Text(), nullable=True),
        sa.Column("note_summary", sa.Text(), nullable=True),
        sa.Column("note_url", sa.Text(), nullable=True),
        sa.Column("note_type", sa.String(length=64), nullable=True),
        sa.Column("publish_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("topics", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["platform_account_id"], ["platform_account.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("note_id"),
    )
    op.create_index("ix_xiaohongshu_note_account_id", "xiaohongshu_note", ["account_id"], unique=False)
    op.create_index("ix_xiaohongshu_note_note_id", "xiaohongshu_note", ["note_id"], unique=True)
    op.create_index("ix_xiaohongshu_note_platform_account_id", "xiaohongshu_note", ["platform_account_id"], unique=False)
    op.create_index("ix_xiaohongshu_note_publish_time", "xiaohongshu_note", ["publish_time"], unique=False)
    op.create_index("ix_xiaohongshu_note_status", "xiaohongshu_note", ["status"], unique=False)

    op.create_table(
        "xiaohongshu_note_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_pk", sa.Integer(), nullable=False),
        sa.Column("note_id", sa.Text(), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("favorite_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["note_pk"], ["xiaohongshu_note.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_xiaohongshu_note_snapshot_note_pk", "xiaohongshu_note_snapshot", ["note_pk"], unique=False)
    op.create_index("ix_xiaohongshu_note_snapshot_note_id", "xiaohongshu_note_snapshot", ["note_id"], unique=False)
    op.create_index("ix_xiaohongshu_note_snapshot_snapshot_time", "xiaohongshu_note_snapshot", ["snapshot_time"], unique=False)

    op.create_table(
        "xiaohongshu_note_comment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_pk", sa.Integer(), nullable=False),
        sa.Column("note_id", sa.String(length=128), nullable=False),
        sa.Column("comment_id", sa.String(length=128), nullable=False),
        sa.Column("parent_comment_id", sa.String(length=128), nullable=True),
        sa.Column("comment_level", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("nickname", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="visible"),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["note_pk"], ["xiaohongshu_note.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("comment_id"),
    )
    op.create_index("ix_xiaohongshu_note_comment_comment_id", "xiaohongshu_note_comment", ["comment_id"], unique=True)
    op.create_index("ix_xiaohongshu_note_comment_comment_time", "xiaohongshu_note_comment", ["comment_time"], unique=False)
    op.create_index("ix_xiaohongshu_note_comment_note_id", "xiaohongshu_note_comment", ["note_id"], unique=False)
    op.create_index("ix_xiaohongshu_note_comment_note_pk", "xiaohongshu_note_comment", ["note_pk"], unique=False)
    op.create_index("ix_xiaohongshu_note_comment_parent_comment_id", "xiaohongshu_note_comment", ["parent_comment_id"], unique=False)
    op.create_index("ix_xiaohongshu_note_comment_status", "xiaohongshu_note_comment", ["status"], unique=False)
    op.create_index("ix_xiaohongshu_note_comment_user_id", "xiaohongshu_note_comment", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_xiaohongshu_note_comment_user_id", table_name="xiaohongshu_note_comment")
    op.drop_index("ix_xiaohongshu_note_comment_status", table_name="xiaohongshu_note_comment")
    op.drop_index("ix_xiaohongshu_note_comment_parent_comment_id", table_name="xiaohongshu_note_comment")
    op.drop_index("ix_xiaohongshu_note_comment_note_pk", table_name="xiaohongshu_note_comment")
    op.drop_index("ix_xiaohongshu_note_comment_note_id", table_name="xiaohongshu_note_comment")
    op.drop_index("ix_xiaohongshu_note_comment_comment_time", table_name="xiaohongshu_note_comment")
    op.drop_index("ix_xiaohongshu_note_comment_comment_id", table_name="xiaohongshu_note_comment")
    op.drop_table("xiaohongshu_note_comment")

    op.drop_index("ix_xiaohongshu_note_snapshot_snapshot_time", table_name="xiaohongshu_note_snapshot")
    op.drop_index("ix_xiaohongshu_note_snapshot_note_id", table_name="xiaohongshu_note_snapshot")
    op.drop_index("ix_xiaohongshu_note_snapshot_note_pk", table_name="xiaohongshu_note_snapshot")
    op.drop_table("xiaohongshu_note_snapshot")

    op.drop_index("ix_xiaohongshu_note_status", table_name="xiaohongshu_note")
    op.drop_index("ix_xiaohongshu_note_publish_time", table_name="xiaohongshu_note")
    op.drop_index("ix_xiaohongshu_note_platform_account_id", table_name="xiaohongshu_note")
    op.drop_index("ix_xiaohongshu_note_note_id", table_name="xiaohongshu_note")
    op.drop_index("ix_xiaohongshu_note_account_id", table_name="xiaohongshu_note")
    op.drop_table("xiaohongshu_note")

    op.drop_index("ix_xiaohongshu_account_snapshot_snapshot_time", table_name="xiaohongshu_account_snapshot")
    op.drop_index("ix_xiaohongshu_account_snapshot_platform_account_id", table_name="xiaohongshu_account_snapshot")
    op.drop_index("ix_xiaohongshu_account_snapshot_account_id", table_name="xiaohongshu_account_snapshot")
    op.drop_table("xiaohongshu_account_snapshot")
