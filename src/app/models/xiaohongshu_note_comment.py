from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XiaohongshuNoteComment(Base):
    __tablename__ = "xiaohongshu_note_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note_pk: Mapped[int] = mapped_column(
        ForeignKey("xiaohongshu_note.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    comment_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    parent_comment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    comment_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="visible", nullable=False, index=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
