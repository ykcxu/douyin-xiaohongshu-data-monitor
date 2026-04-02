from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.collector.douyin.live.status_collector import DouyinLiveStatusCollector, LiveRoomStatus
from app.models.douyin_live_room import DouyinLiveRoom


class HttpDouyinLiveStatusCollector(DouyinLiveStatusCollector):
    """
    Placeholder for the real Douyin provider.

    This class is intentionally narrow: once cookies, headers, signing, and the
    exact endpoint are confirmed, we only need to fill in `_build_request` and
    `_parse_response` without changing service or scheduler code.
    """

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_room_status(self, room: DouyinLiveRoom) -> LiveRoomStatus:
        request_payload = self._build_request(room)
        now = datetime.now(timezone.utc)

        raise NotImplementedError(
            "HttpDouyinLiveStatusCollector is a placeholder. "
            f"Prepared request context for room {room.room_id}: {request_payload} at {now.isoformat()}."
        )

    def build_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds, follow_redirects=True)

    def _build_request(self, room: DouyinLiveRoom) -> dict[str, object]:
        return {
            "room_id": room.room_id,
            "room_url": room.room_url,
            "account_id": room.account_id,
            "sec_account_id": room.sec_account_id,
        }
