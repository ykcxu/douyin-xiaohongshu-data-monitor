from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XiaohongshuNoteSnapshot(Base):
    __tablename__ = "xiaohongshu_note_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note_pk: Mapped[int] = mapped_column(
        ForeignKey("xiaohongshu_note.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    like_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    favorite_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    share_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    view_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
