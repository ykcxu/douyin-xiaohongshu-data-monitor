from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DouyinLiveSnapshot(Base):
    __tablename__ = "douyin_live_snapshot"

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
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    live_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    online_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    total_viewer_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    new_viewer_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    like_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    new_like_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    new_comment_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    share_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    gift_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    gift_amount: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
