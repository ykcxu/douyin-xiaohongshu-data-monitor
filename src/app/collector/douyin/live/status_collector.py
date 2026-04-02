from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from app.models.douyin_live_room import DouyinLiveRoom


@dataclass(slots=True)
class LiveRoomStatus:
    room_id: str
    fetched_at: datetime
    live_status: str
    is_live: bool
    account_id: str | None = None
    nickname: str | None = None
    live_title: str | None = None
    source_url: str | None = None
    online_count: int | None = None
    total_viewer_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    raw_payload: dict[str, object] = field(default_factory=dict)


class DouyinLiveStatusCollector(Protocol):
    def fetch_room_status(self, room: DouyinLiveRoom) -> LiveRoomStatus:
        ...


class StubDouyinLiveStatusCollector:
    """Temporary collector until a real Douyin integration is wired in."""

    def fetch_room_status(self, room: DouyinLiveRoom) -> LiveRoomStatus:
        now = datetime.now(timezone.utc)
        raw_payload = {
            "room_id": room.room_id,
            "status": "offline",
            "collector": "stub",
            "fetched_at": now.isoformat(),
        }
        return LiveRoomStatus(
            room_id=room.room_id,
            fetched_at=now,
            live_status="offline",
            is_live=False,
            account_id=room.account_id,
            nickname=room.nickname,
            live_title=room.live_title,
            source_url=room.room_url,
            raw_payload=raw_payload,
        )
