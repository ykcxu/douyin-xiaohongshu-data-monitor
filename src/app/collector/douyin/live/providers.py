from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.collector.douyin.live.exceptions import (
    DouyinAuthenticationRequired,
    DouyinRoomDataUnavailable,
)
from app.collector.douyin.live.request_context import (
    DouyinLiveRequestContext,
    load_storage_state_cookies,
)
from app.collector.douyin.live.status_collector import DouyinLiveStatusCollector, LiveRoomStatus
from app.models.douyin_live_room import DouyinLiveRoom
from app.services.login_state_service import LoginStateService


class HttpDouyinLiveStatusCollector(DouyinLiveStatusCollector):
    """First-pass real Douyin provider based on authenticated room-page parsing."""

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds
        self.login_state_service = LoginStateService()

    def fetch_room_status(self, room: DouyinLiveRoom) -> LiveRoomStatus:
        request_context = self._build_request_context(room)
        now = datetime.now(timezone.utc)

        if room.account_id and not request_context.is_authenticated:
            raise DouyinAuthenticationRequired(
                f"Douyin login state is missing for account {room.account_id} and room {room.room_id}."
            )

        with self.build_client() as client:
            response = client.get(
                self._resolve_room_url(room),
                headers=request_context.headers,
                cookies=request_context.cookies,
            )
            response.raise_for_status()

        page_state = self._extract_page_state(response.text)
        room_store = page_state.get("roomStore", {})
        room_info = room_store.get("roomInfo", {})
        web_rid = self._normalize_text(room_info.get("web_rid") or room_info.get("roomId"))
        live_status = self._normalize_text(room_store.get("liveStatus") or page_state.get("liveStatus"))
        if web_rid is None and live_status is None:
            raise DouyinRoomDataUnavailable(
                f"Could not extract roomStore data from room page {response.url} for room {room.room_id}."
            )

        raw_payload = {
            "collector": "http-page",
            "fetched_at": now.isoformat(),
            "request": {
                "room_id": room.room_id,
                "room_url": str(response.url),
                "account_id": room.account_id,
                "storage_state_path": (
                    str(request_context.storage_state_path)
                    if request_context.storage_state_path
                    else None
                ),
                "has_cookies": bool(request_context.cookies),
            },
            "page_state": page_state,
        }
        resolved_live_status = live_status or "unknown"
        resolved_room_id = web_rid or room.room_id
        return LiveRoomStatus(
            room_id=resolved_room_id,
            fetched_at=now,
            live_status=resolved_live_status,
            is_live=resolved_live_status == "normal" and web_rid is not None,
            account_id=room.account_id,
            nickname=self._extract_nickname(page_state) or room.nickname,
            live_title=self._normalize_text(room_info.get("title")) or room.live_title,
            source_url=str(response.url),
            online_count=self._extract_int(room_info.get("user_count")),
            total_viewer_count=self._extract_int(room_info.get("total_user_count")),
            like_count=self._extract_int(room_info.get("like_count")),
            comment_count=self._extract_int(room_info.get("comment_count")),
            share_count=self._extract_int(room_info.get("share_count")),
            raw_payload=raw_payload,
        )

    def build_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds, follow_redirects=True)

    def build_debug_bundle(self, room: DouyinLiveRoom) -> dict[str, Any]:
        request_context = self._build_request_context(room)
        with self.build_client() as client:
            room_response = client.get(
                self._resolve_room_url(room),
                headers=request_context.headers,
                cookies=request_context.cookies,
            )
            room_response.raise_for_status()
            page_state = self._extract_page_state(room_response.text)
            room_store = page_state.get("roomStore", {})
            room_info = room_store.get("roomInfo", {})
            web_rid = self._normalize_text(room_info.get("web_rid") or room.room_id) or room.room_id

            result: dict[str, Any] = {
                "room_url": str(room_response.url),
                "page_state": page_state,
                "request_context": {
                    "account_id": request_context.account_id,
                    "storage_state_path": (
                        str(request_context.storage_state_path)
                        if request_context.storage_state_path
                        else None
                    ),
                    "has_cookies": bool(request_context.cookies),
                },
                "api_samples": {},
            }
            for name, url in self._known_debug_urls(room=room, web_rid=web_rid).items():
                result["api_samples"][name] = self._fetch_json_sample(
                    client=client,
                    url=url,
                    request_context=request_context,
                )
            return result

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

    def _resolve_room_url(self, room: DouyinLiveRoom) -> str:
        if room.room_url:
            return room.room_url
        return f"https://live.douyin.com/{room.room_id}"

    def _build_common_query_params(self) -> dict[str, str]:
        return {
            "aid": "6383",
            "app_name": "douyin_web",
            "live_id": "1",
            "device_platform": "web",
            "language": "zh-CN",
            "enter_from": "link_share",
            "cookie_enabled": "true",
            "screen_width": "1280",
            "screen_height": "720",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "145.0.0.0",
        }

    def _known_debug_urls(self, *, room: DouyinLiveRoom, web_rid: str) -> dict[str, str]:
        common = self._build_common_query_params()
        return {
            "webcast_setting": "https://live.douyin.com/webcast/setting/?" + urlencode(common),
            "webcast_user_me": "https://live.douyin.com/webcast/user/me/?"
            + urlencode({**common, "room_id": "0"}),
            "room_web_enter": "https://live.douyin.com/webcast/room/web/enter/?"
            + urlencode(
                {
                    **common,
                    "web_rid": web_rid,
                    "room_id_str": room.room_id,
                    "enter_source": "web_live",
                    "is_need_double_stream": "true",
                    "enter_type": "1",
                    "prefetch": "0",
                    "version_code": "251700",
                }
            ),
            "similar_room_by_anchor": "https://live.douyin.com/webcast/web/similar_room_by_anchor/?"
            + urlencode({**common, "web_rid": web_rid, "count": "5", "offset": "0"}),
        }

    def _fetch_json_sample(
        self,
        *,
        client: httpx.Client,
        url: str,
        request_context: DouyinLiveRequestContext,
    ) -> dict[str, Any]:
        response = client.get(
            url,
            headers=request_context.headers,
            cookies=request_context.cookies,
        )
        result: dict[str, Any] = {
            "url": str(response.url),
            "status_code": response.status_code,
        }
        try:
            body = response.json()
            result["body"] = body
            summary = self._summarize_debug_body(str(response.url), body)
            if summary:
                result["body_summary"] = summary
        except json.JSONDecodeError:
            result["body_preview"] = response.text[:5000]
        return result

    def _summarize_debug_body(self, url: str, body: Any) -> dict[str, Any] | None:
        if not isinstance(body, dict):
            return None

        summary: dict[str, Any] = {}
        if "status_code" in body:
            summary["api_status_code"] = body.get("status_code")
        if "message" in body:
            summary["message"] = body.get("message")
        if "prompts" in body:
            summary["prompts"] = body.get("prompts")

        if "/webcast/room/web/enter/" in url:
            summary.update(self._extract_room_web_enter_summary(body))
        return summary or None

    def _extract_room_web_enter_summary(self, body: dict[str, Any]) -> dict[str, Any]:
        data = body.get("data")
        room_payload = self._find_nested_dict(data, {"room", "roomInfo", "room_data"})
        owner_payload = self._find_nested_dict(data, {"owner", "anchor"})
        stream_payload = self._find_nested_dict(data, {"stream_url", "streamUrl", "web_stream_url"})

        summary: dict[str, Any] = {
            "data_keys": sorted(data.keys()) if isinstance(data, dict) else None,
            "room_payload_keys": sorted(room_payload.keys()) if isinstance(room_payload, dict) else None,
            "has_stream_payload": isinstance(stream_payload, dict),
        }
        if isinstance(room_payload, dict):
            summary["room_id"] = self._normalize_text(
                room_payload.get("id_str")
                or room_payload.get("room_id")
                or room_payload.get("roomId")
                or room_payload.get("web_rid")
            )
            summary["title"] = self._normalize_text(room_payload.get("title"))
            summary["status"] = self._normalize_text(
                room_payload.get("status")
                or room_payload.get("live_status")
                or room_payload.get("liveStatus")
            )
            summary["user_count"] = self._extract_int(
                room_payload.get("user_count")
                or room_payload.get("room_view_stats", {}).get("display_value")
            )
            summary["total_user_count"] = self._extract_int(room_payload.get("total_user_count"))
            summary["like_count"] = self._extract_int(room_payload.get("like_count"))
        if isinstance(owner_payload, dict):
            summary["owner_id"] = self._normalize_text(owner_payload.get("id_str") or owner_payload.get("id"))
            summary["owner_nickname"] = self._normalize_text(
                owner_payload.get("nickname") or owner_payload.get("nick_name")
            )
        return {key: value for key, value in summary.items() if value is not None}

    def _find_nested_dict(self, value: Any, candidate_keys: set[str]) -> dict[str, Any] | None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in candidate_keys and isinstance(nested, dict):
                    return nested
            for nested in value.values():
                found = self._find_nested_dict(nested, candidate_keys)
                if found is not None:
                    return found
        if isinstance(value, list):
            for item in value:
                found = self._find_nested_dict(item, candidate_keys)
                if found is not None:
                    return found
        return None

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
        if room_store is None:
            raise DouyinRoomDataUnavailable("roomStore block was not found in the Douyin room page HTML.")

        result: dict[str, Any] = {
            "roomStore": room_store,
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
        odin = self._extract_escaped_json_between(
            html,
            start_marker='\\"odin\\":',
            end_marker=',\\"userHandlerPause\\":',
        )
        if odin is None:
            odin = self._extract_escaped_json_between(
                html,
                start_marker='"odin":',
                end_marker=',"userHandlerPause":',
            )
        if odin is not None:
            result["odin"] = odin
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
