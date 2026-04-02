from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XiaohongshuNote(Base):
    __tablename__ = "xiaohongshu_note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    note_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
