from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformAccount(Base):
    __tablename__ = "platform_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    account_id: Mapped[str] = mapped_column(String(128), index=True)
    account_handle: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_competitor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    homepage_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    live_room_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discover_source: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tags: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
