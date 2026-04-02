from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DouyinLiveRoom(Base):
    __tablename__ = "douyin_live_room"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    room_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    room_handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    sec_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    live_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    is_monitor_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    monitor_priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    last_live_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_live_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_live_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
