from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DouyinLiveComment(Base):
    __tablename__ = "douyin_live_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("douyin_live_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    live_room_id: Mapped[int] = mapped_column(
        ForeignKey("douyin_live_room.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fetch_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sequence_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    sec_user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    follower_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fan_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_anchor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_room_manager: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_fans_group_member: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_new_fan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_plain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emoji_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mentioned_users: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_badges: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    risk_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_line_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
