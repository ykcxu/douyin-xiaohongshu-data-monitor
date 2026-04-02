from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import sync_playwright

from app.browser.browser_sidecar import get_browser_sidecar
from app.collector.douyin.live.exceptions import (
    DouyinAuthenticationRequired,
    DouyinRoomDataUnavailable,
)
from app.collector.douyin.live.status_collector import DouyinLiveStatusCollector, LiveRoomStatus
from app.models.douyin_live_room import DouyinLiveRoom
from app.services.login_state_service import LoginStateService


class BrowserDouyinLiveStatusCollector(DouyinLiveStatusCollector):
    """Browser-based Douyin provider using Playwright for authentic page access."""

    def __init__(self, timeout_seconds: int = 30, headless: bool = True) -> None:
        self.timeout_seconds = timeout_seconds
        self.headless = headless
        self.login_state_service = LoginStateService()

    def fetch_room_status(self, room: DouyinLiveRoom) -> LiveRoomStatus:
        now = datetime.now(timezone.utc)

        storage_state_path = None
        if room.account_id:
            storage_state_path = self.login_state_service.resolve_storage_state_path(
                platform="douyin",
                account_id=room.account_id,
            )

        if room.account_id and not storage_state_path:
            raise DouyinAuthenticationRequired(
                f"Douyin login state is missing for account {room.account_id} and room {room.room_id}."
            )

        room_url = self._resolve_room_url(room)
        sidecar = get_browser_sidecar()

        try:
            sidecar.watch_room(
                room_id=room.room_id,
                account_id=room.account_id or "douyin_demo",
                platform="douyin",
                room_url=room_url,
            )
            status_payload = sidecar.get_room_status(room.room_id)
            if not status_payload or status_payload.get("error"):
                sidecar.refresh_room(room.room_id)
                status_payload = sidecar.get_room_status(room.room_id)
        except Exception as e:
            raise DouyinRoomDataUnavailable(
                f"Failed to fetch room page via sidecar for {room.room_id}: {str(e)}"
            )

        if not status_payload or status_payload.get("error"):
            raise DouyinRoomDataUnavailable(
                f"Failed to fetch room page state for {room.room_id}: {status_payload}"
            )

        page_state = status_payload.get("status", {}) if isinstance(status_payload, dict) else {}
        websocket_frames_count = 0
        if isinstance(status_payload, dict):
            websocket_frames_count = int(status_payload.get("websocket_frames_count") or 0)
        room_store = page_state.get("roomStore", {})
        room_info = room_store.get("roomInfo", {}) if isinstance(room_store, dict) else {}
        nested_room = room_info.get("room", {}) if isinstance(room_info, dict) else {}

        web_rid = self._normalize_text(room_info.get("web_rid") or room_info.get("roomId"))
        live_status = self._normalize_text(room_store.get("liveStatus") or page_state.get("liveStatus"))
        room_status_code = self._extract_int(nested_room.get("status"))
        room_status_text = self._normalize_text(nested_room.get("status_str"))

        if web_rid is None and live_status is None and room_status_code is None:
            raise DouyinRoomDataUnavailable(
                f"Could not extract roomStore data from room page for room {room.room_id}."
            )

        # Determine live status: roomInfo.room.status is more reliable than roomStore.liveStatus
        has_stream_url = bool(
            room_info.get("web_stream_url") or room_info.get("stream_url") or room_info.get("streamUrl")
        )
        resolved_room_id = web_rid or self._normalize_text(nested_room.get("id_str")) or room.room_id
        resolved_title = (
            self._normalize_text(nested_room.get("title"))
            or self._normalize_text(room_info.get("title"))
            or room.live_title
        )
        resolved_live_status = room_status_text or live_status or (str(room_status_code) if room_status_code is not None else "unknown")

        if websocket_frames_count > 0:
            is_live = True
        elif has_stream_url:
            is_live = True
        elif room_status_code in {2, 4}:
            is_live = True
        else:
            is_live = resolved_live_status in {"live", "online", "4", "2"}

        # Extract counts
        online_count = self._extract_int(
            nested_room.get("user_count") or nested_room.get("user_count_str") or room_info.get("user_count") or room_info.get("userCount")
        )
        like_count = self._extract_int(
            nested_room.get("like_count") or room_info.get("like_count") or room_info.get("likeCount")
        )
        
        raw_payload = {
            "collector": "browser-page",
            "fetched_at": now.isoformat(),
            "request": {
                "room_id": room.room_id,
                "room_url": room_url,
                "account_id": room.account_id,
                "storage_state_path": str(storage_state_path) if storage_state_path else None,
                "headless": self.headless,
            },
            "page_state": page_state,
            "websocket_frames_count": websocket_frames_count,
        }
        
        return LiveRoomStatus(
            room_id=resolved_room_id,
            fetched_at=now,
            live_status=resolved_live_status,
            is_live=is_live,
            account_id=room.account_id,
            nickname=self._extract_nickname(page_state) or room.nickname,
            live_title=resolved_title,
            source_url=room_url,
            online_count=online_count,
            total_viewer_count=self._extract_int(room_info.get("total_user_count")),
            like_count=like_count,
            comment_count=self._extract_int(room_info.get("comment_count")),
            share_count=self._extract_int(room_info.get("share_count")),
            raw_payload=raw_payload,
        )

    def build_debug_bundle(self, room: DouyinLiveRoom) -> dict[str, Any]:
        """Build a debug bundle with page state and traces."""
        storage_state_path = None
        if room.account_id:
            storage_state_path = self.login_state_service.resolve_storage_state_path(
                platform="douyin",
                account_id=room.account_id,
            )
        
        room_url = self._resolve_room_url(room)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            
            context_options = {}
            if storage_state_path:
                context_options["storage_state"] = str(storage_state_path)
            
            context = browser.new_context(**context_options)
            page = context.new_page()
            
            try:
                page.goto(room_url, wait_until="networkidle", timeout=self.timeout_seconds * 1000)
                page.wait_for_timeout(3000)
                
                html = page.content()
                page_state = self._extract_page_state(html)
                
                result = {
                    "room_url": room_url,
                    "page_state": page_state,
                    "request_context": {
                        "account_id": room.account_id,
                        "storage_state_path": str(storage_state_path) if storage_state_path else None,
                        "headless": self.headless,
                    },
                    "title": page.title(),
                }
                
            finally:
                context.close()
                browser.close()
        
        return result

    def _resolve_room_url(self, room: DouyinLiveRoom) -> str:
        if room.room_url:
            return room.room_url
        return f"https://live.douyin.com/{room.room_id}"

    def _extract_page_state(self, html: str) -> dict[str, Any]:
        room_store_candidates = self._extract_all_escaped_json_between(
            html,
            start_marker='\\"roomStore\\":',
            end_marker=',\\"linkmicStore\\":',
        )
        room_store_candidates.extend(
            self._extract_all_escaped_json_between(
                html,
                start_marker='"roomStore":',
                end_marker=',"linkmicStore":',
            )
        )
        room_store = self._select_best_room_store(room_store_candidates)
        
        result: dict[str, Any] = {
            "roomStore": room_store or {},
        }
        
        default_user_info = self._extract_escaped_json_between(
            html,
            start_marker='\\"defaultHeaderUserInfo\\":',
            end_marker=',\\"domain\\":',
        )
        if default_user_info is None:
            default_user_info = self._extract_escaped_json_between(
                html,
                start_marker='"defaultHeaderUserInfo":',
                end_marker=',"domain":',
            )
        if default_user_info is not None:
            result["defaultHeaderUserInfo"] = default_user_info
            
        return result

    def _extract_escaped_json_between(
        self,
        html: str,
        *,
        start_marker: str,
        end_marker: str,
    ) -> dict[str, Any] | None:
        items = self._extract_all_escaped_json_between(
            html,
            start_marker=start_marker,
            end_marker=end_marker,
        )
        return items[0] if items else None

    def _extract_all_escaped_json_between(
        self,
        html: str,
        *,
        start_marker: str,
        end_marker: str,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        search_from = 0
        while True:
            marker_index = html.find(start_marker, search_from)
            if marker_index == -1:
                break
            start = html.find("{", marker_index)
            if start == -1:
                break
            end = html.find(end_marker, start)
            if end == -1:
                break

            fragment = html[start:end]
            normalized = fragment.replace('\\"', '"')
            try:
                items.append(json.loads(normalized))
            except json.JSONDecodeError:
                pass
            search_from = end + len(end_marker)
        return items

    def _select_best_room_store(self, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None

        def score(candidate: dict[str, Any]) -> tuple[int, int]:
            room_info = candidate.get("roomInfo")
            if not isinstance(room_info, dict):
                return (0, len(candidate))
            web_rid = room_info.get("web_rid") or room_info.get("roomId")
            return (1 if web_rid else 0, len(candidate))

        return max(candidates, key=score)

    def _extract_nickname(self, page_state: dict[str, Any]) -> str | None:
        default_header = page_state.get("defaultHeaderUserInfo")
        if not isinstance(default_header, dict):
            return None
        info = default_header.get("info")
        if not isinstance(info, dict):
            return None
        return self._normalize_text(info.get("nickname"))

    def _extract_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            digits = re.sub(r"[^\d]", "", value)
            if digits:
                return int(digits)
        return None

    def _normalize_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text == "$undefined":
            return None
        return text
