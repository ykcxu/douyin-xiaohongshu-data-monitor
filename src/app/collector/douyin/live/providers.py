from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.collector.douyin.live.exceptions import (
    DouyinAuthenticationRequired,
    DouyinProviderNotReady,
)
from app.collector.douyin.live.request_context import (
    DouyinLiveRequestContext,
    load_storage_state_cookies,
)
from app.collector.douyin.live.status_collector import DouyinLiveStatusCollector, LiveRoomStatus
from app.models.douyin_live_room import DouyinLiveRoom
from app.services.login_state_service import LoginStateService


class HttpDouyinLiveStatusCollector(DouyinLiveStatusCollector):
    """
    Placeholder for the real Douyin provider.

    This class is intentionally narrow: once cookies, headers, signing, and the
    exact endpoint are confirmed, we only need to fill in `_build_request` and
    `_parse_response` without changing service or scheduler code.
    """

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds
        self.login_state_service = LoginStateService()

    def fetch_room_status(self, room: DouyinLiveRoom) -> LiveRoomStatus:
        request_context = self._build_request_context(room)
        request_payload = self._build_request(room, request_context)
        now = datetime.now(timezone.utc)

        if room.account_id and not request_context.is_authenticated:
            raise DouyinAuthenticationRequired(
                f"Douyin login state is missing for account {room.account_id} and room {room.room_id}."
            )

        raise DouyinProviderNotReady(
            "HttpDouyinLiveStatusCollector is a placeholder. "
            f"Prepared request context for room {room.room_id}: {request_payload} at {now.isoformat()}."
        )

    def build_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds, follow_redirects=True)

    def _build_request_context(self, room: DouyinLiveRoom) -> DouyinLiveRequestContext:
        storage_state_path = None
        if room.account_id:
            storage_state_path = self.login_state_service.resolve_storage_state_path(
                platform="douyin",
                account_id=room.account_id,
            )

        cookies = load_storage_state_cookies(storage_state_path)
        headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "referer": room.room_url or "https://live.douyin.com/",
        }
        return DouyinLiveRequestContext(
            account_id=room.account_id,
            storage_state_path=storage_state_path,
            cookies=cookies,
            headers=headers,
            metadata={"room_pk": room.id, "room_id": room.room_id},
        )

    def _build_request(
        self,
        room: DouyinLiveRoom,
        request_context: DouyinLiveRequestContext,
    ) -> dict[str, object]:
        return {
            "room_id": room.room_id,
            "room_url": room.room_url,
            "account_id": room.account_id,
            "sec_account_id": room.sec_account_id,
            "storage_state_path": str(request_context.storage_state_path) if request_context.storage_state_path else None,
            "has_cookies": bool(request_context.cookies),
            "header_keys": sorted(request_context.headers.keys()),
            "metadata": request_context.metadata,
        }
