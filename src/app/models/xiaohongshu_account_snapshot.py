from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class XiaohongshuAccountSnapshot(Base):
    __tablename__ = "xiaohongshu_account_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("platform_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    follower_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    following_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    liked_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
