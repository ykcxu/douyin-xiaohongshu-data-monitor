from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import sync_playwright

from app.browser.browser_sidecar import get_browser_sidecar
from app.collector.douyin.live.exceptions import DouyinRoomDataUnavailable
from app.collector.douyin.live.status_collector import DouyinLiveStatusCollector, LiveRoomStatus
from app.models.douyin_live_room import DouyinLiveRoom
from app.services.login_state_service import LoginStateService


class BrowserDouyinLiveStatusCollector(DouyinLiveStatusCollector):
    """Browser-based Douyin provider.

    Strategy:
    1. Prefer authenticated sidecar context when a saved storage_state exists.
    2. If the authenticated page lands on a challenge / captcha / empty shell page,
       fall back to an anonymous one-off browser page.
    3. Extract status primarily from JS runtime state (`window.roomStore` or
       `window.__STORE__.roomStore`), with HTML parsing as a best-effort fallback.
    """

    def __init__(self, timeout_seconds: int = 30, headless: bool = True) -> None:
        self.timeout_seconds = timeout_seconds
        self.headless = headless
        self.login_state_service = LoginStateService()

    def fetch_room_status(self, room: DouyinLiveRoom) -> LiveRoomStatus:
        now = datetime.now(timezone.utc)
        room_url = self._resolve_room_url(room)

        storage_state_path = None
        if room.account_id:
            storage_state_path = self.login_state_service.resolve_storage_state_path(
                platform="douyin",
                account_id=room.account_id,
            )

        attempts: list[dict[str, str]] = []
        payload: dict[str, Any] | None = None

        if room.account_id and storage_state_path:
            try:
                payload = self._fetch_page_payload_via_sidecar(
                    room_id=room.room_id,
                    room_url=room_url,
                    account_id=room.account_id,
                )
                attempts.append({"mode": "authenticated-sidecar", "result": "ok"})
            except Exception as e:
                attempts.append({
                    "mode": "authenticated-sidecar",
                    "result": f"error:{type(e).__name__}",
                    "message": str(e),
                })

        if not self._has_usable_room_data(payload):
            try:
                anonymous_payload = self._fetch_page_payload_anonymous(room_url=room_url)
                payload = anonymous_payload
                attempts.append({"mode": "anonymous-browser", "result": "ok"})
            except Exception as e:
                attempts.append({
                    "mode": "anonymous-browser",
                    "result": f"error:{type(e).__name__}",
                    "message": str(e),
                })

        if payload is None:
            raise DouyinRoomDataUnavailable(
                f"Failed to fetch room page for {room.room_id}. attempts={attempts}"
            )

        return self._build_status_from_payload(
            room=room,
            room_url=room_url,
            now=now,
            storage_state_path=storage_state_path,
            payload=payload,
            attempts=attempts,
        )

    def build_debug_bundle(self, room: DouyinLiveRoom) -> dict[str, Any]:
        storage_state_path = None
        if room.account_id:
            storage_state_path = self.login_state_service.resolve_storage_state_path(
                platform="douyin",
                account_id=room.account_id,
            )

        room_url = self._resolve_room_url(room)
        payloads: list[dict[str, Any]] = []

        if room.account_id and storage_state_path:
            try:
                payloads.append(self._fetch_page_payload_via_sidecar(
                    room_id=room.room_id,
                    room_url=room_url,
                    account_id=room.account_id,
                ))
            except Exception as e:
                payloads.append({"mode": "authenticated-sidecar", "error": f"{type(e).__name__}: {e}"})

        try:
            payloads.append(self._fetch_page_payload_anonymous(room_url=room_url))
        except Exception as e:
            payloads.append({"mode": "anonymous-browser", "error": f"{type(e).__name__}: {e}"})

        return {
            "room_id": room.room_id,
            "room_url": room_url,
            "storage_state_path": str(storage_state_path) if storage_state_path else None,
            "payloads": payloads,
        }

    def _fetch_page_payload_via_sidecar(
        self,
        *,
        room_id: str,
        room_url: str,
        account_id: str,
    ) -> dict[str, Any]:
        sidecar = get_browser_sidecar()
        sidecar.watch_room(
            room_id=room_id,
            account_id=account_id,
            platform="douyin",
            room_url=room_url,
        )
        status_payload = sidecar.get_room_status(room_id)
        if status_payload and status_payload.get("error") == "room session inactive":
            sidecar.stop_watching(room_id)
            sidecar.watch_room(
                room_id=room_id,
                account_id=account_id,
                platform="douyin",
                room_url=room_url,
            )
            status_payload = sidecar.get_room_status(room_id)
        if not status_payload or status_payload.get("error"):
            sidecar.refresh_room(room_id)
            status_payload = sidecar.get_room_status(room_id)
        if not status_payload:
            raise DouyinRoomDataUnavailable(f"Empty sidecar status payload for room {room_id}")
        status_payload["mode"] = "authenticated-sidecar"
        return status_payload

    def _fetch_page_payload_anonymous(self, *, room_url: str) -> dict[str, Any]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(room_url, wait_until="domcontentloaded", timeout=self.timeout_seconds * 1000)
                page.wait_for_timeout(4000)
                html = page.content()
                page_state = self._extract_page_state_from_browser(page=page, html=html)
                payload = {
                    "mode": "anonymous-browser",
                    "room_id": self._extract_room_id_from_url(page.url),
                    "status": page_state,
                    "title": page.title(),
                    "url": page.url,
                    "websocket_frames_count": 0,
                }
                return payload
            finally:
                context.close()
                browser.close()

    def _build_status_from_payload(
        self,
        *,
        room: DouyinLiveRoom,
        room_url: str,
        now: datetime,
        storage_state_path: Any,
        payload: dict[str, Any],
        attempts: list[dict[str, str]],
    ) -> LiveRoomStatus:
        page_state = payload.get("status", {}) if isinstance(payload, dict) else {}
        websocket_frames_count = int(payload.get("websocket_frames_count") or 0) if isinstance(payload, dict) else 0
        room_store = page_state.get("roomStore", {}) if isinstance(page_state, dict) else {}
        room_info = room_store.get("roomInfo", {}) if isinstance(room_store, dict) else {}
        nested_room = room_info.get("room", {}) if isinstance(room_info, dict) else {}
        body_text = self._normalize_text(page_state.get("bodyText")) or ""
        page_title = self._normalize_text(page_state.get("pageTitle") or payload.get("title"))

        challenge = self._is_challenge_page(page_title=page_title, body_text=body_text)

        web_rid = self._normalize_text(
            room_info.get("web_rid")
            or room_info.get("roomId")
            or nested_room.get("id_str")
            or nested_room.get("room_id")
        )
        live_status = self._normalize_text(
            room_store.get("liveStatus")
            or nested_room.get("status_str")
            or page_state.get("liveStatus")
        )
        room_status_code = self._extract_int(nested_room.get("status"))

        has_stream_url = bool(
            room_info.get("web_stream_url")
            or room_info.get("stream_url")
            or room_info.get("streamUrl")
        )

        resolved_room_id = web_rid or room.room_id
        resolved_title = (
            self._normalize_text(nested_room.get("title"))
            or self._normalize_text(room_info.get("title"))
            or self._normalize_text(page_state.get("anchorTitle"))
            or self._title_to_live_title(page_title)
            or room.live_title
        )
        resolved_nickname = (
            self._extract_nickname(page_state)
            or self._normalize_text(room_info.get("nickname"))
            or self._normalize_text((nested_room.get("owner") or {}).get("nickname") if isinstance(nested_room.get("owner"), dict) else None)
            or self._extract_anchor_name_from_body(body_text)
            or room.nickname
        )

        online_count = self._extract_int(
            nested_room.get("user_count")
            or nested_room.get("user_count_str")
            or room_info.get("user_count")
            or room_info.get("userCount")
            or self._extract_metric_from_body(body_text, "在线观众")
        )
        like_count = self._extract_int(
            nested_room.get("like_count")
            or room_info.get("like_count")
            or room_info.get("likeCount")
            or self._extract_metric_from_body(body_text, "本场点赞")
        )

        if challenge:
            resolved_live_status = "challenge"
            is_live = False
        elif websocket_frames_count > 0:
            resolved_live_status = live_status or "live"
            is_live = True
        elif has_stream_url:
            resolved_live_status = live_status or "live"
            is_live = True
        elif room_status_code is not None:
            if room_status_code == 2:
                resolved_live_status = live_status or "live"
                is_live = True
            elif room_status_code == 4:
                resolved_live_status = live_status or "offline"
                is_live = False
            else:
                resolved_live_status = live_status or str(room_status_code)
                is_live = False
        elif online_count is not None and online_count > 0:
            resolved_live_status = live_status or "live_partial"
            is_live = True
        elif room_store:
            resolved_live_status = live_status or "partial"
            is_live = False
        else:
            raise DouyinRoomDataUnavailable(
                f"Could not extract roomStore/public status data from room page for room {room.room_id}. attempts={attempts}"
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
            "mode": payload.get("mode"),
            "attempts": attempts,
            "page_state": page_state,
            "page_title": page_title,
            "challenge": challenge,
            "websocket_frames_count": websocket_frames_count,
        }

        return LiveRoomStatus(
            room_id=resolved_room_id,
            fetched_at=now,
            live_status=resolved_live_status,
            is_live=is_live,
            account_id=room.account_id,
            nickname=resolved_nickname,
            live_title=resolved_title,
            source_url=str(payload.get("url") or room_url),
            online_count=online_count,
            total_viewer_count=self._extract_int(room_info.get("total_user_count")),
            like_count=like_count,
            comment_count=self._extract_int(room_info.get("comment_count")),
            share_count=self._extract_int(room_info.get("share_count")),
            raw_payload=raw_payload,
        )

    def _resolve_room_url(self, room: DouyinLiveRoom) -> str:
        if room.room_url:
            return room.room_url
        return f"https://live.douyin.com/{room.room_id}"

    def _extract_page_state_from_browser(self, *, page: Any, html: str) -> dict[str, Any]:
        result = self._extract_page_state(html)

        js_state = page.evaluate(
            """() => {
                const store = window.__STORE__ || null;
                const roomStore = window.roomStore || store?.roomStore || null;
                const header = window.defaultHeaderUserInfo || store?.userStore?.defaultHeaderUserInfo || null;
                return {
                    pageTitle: document.title || '',
                    bodyText: document.body && document.body.innerText ? document.body.innerText.slice(0, 4000) : '',
                    roomStore,
                    defaultHeaderUserInfo: header,
                    storeKeys: store ? Object.keys(store).slice(0, 40) : [],
                };
            }"""
        )

        if isinstance(js_state, dict):
            if isinstance(js_state.get("roomStore"), dict):
                result["roomStore"] = js_state["roomStore"]
            if isinstance(js_state.get("defaultHeaderUserInfo"), dict):
                result["defaultHeaderUserInfo"] = js_state["defaultHeaderUserInfo"]
            if js_state.get("pageTitle"):
                result["pageTitle"] = js_state["pageTitle"]
            if js_state.get("bodyText"):
                result["bodyText"] = js_state["bodyText"]
            if js_state.get("storeKeys"):
                result["storeKeys"] = js_state["storeKeys"]

        return result

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

    def _has_usable_room_data(self, payload: dict[str, Any] | None) -> bool:
        if not isinstance(payload, dict):
            return False
        page_state = payload.get("status")
        if not isinstance(page_state, dict):
            return False
        room_store = page_state.get("roomStore")
        if isinstance(room_store, dict) and room_store:
            return True
        body_text = self._normalize_text(page_state.get("bodyText")) or ""
        page_title = self._normalize_text(page_state.get("pageTitle") or payload.get("title")) or ""
        if self._is_challenge_page(page_title=page_title, body_text=body_text):
            return True
        if body_text and ("在线观众" in body_text or "本场点赞" in body_text):
            return True
        return False

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
            nested_room = room_info.get("room") if isinstance(room_info.get("room"), dict) else {}
            user_count = nested_room.get("user_count") or room_info.get("user_count")
            return (1 if web_rid else 0, 1 if user_count else 0, len(candidate))

        return max(candidates, key=score)

    def _extract_nickname(self, page_state: dict[str, Any]) -> str | None:
        default_header = page_state.get("defaultHeaderUserInfo")
        if isinstance(default_header, dict):
            info = default_header.get("info")
            if isinstance(info, dict):
                nickname = self._normalize_text(info.get("nickname"))
                if nickname:
                    return nickname

        room_store = page_state.get("roomStore")
        if isinstance(room_store, dict):
            room_info = room_store.get("roomInfo")
            if isinstance(room_info, dict):
                room = room_info.get("room")
                if isinstance(room, dict):
                    owner = room.get("owner")
                    if isinstance(owner, dict):
                        nickname = self._normalize_text(owner.get("nickname"))
                        if nickname:
                            return nickname
        return None

    def _extract_anchor_name_from_body(self, body_text: str) -> str | None:
        if not body_text:
            return None
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        if len(lines) >= 3 and lines[0] == "开启读屏标签" and lines[1] == "读屏标签已关闭":
            candidate = self._normalize_text(lines[2])
            if candidate and len(candidate) <= 40:
                return candidate
        return None

    def _extract_metric_from_body(self, body_text: str, label: str) -> int | None:
        if not body_text:
            return None
        pattern = rf"([0-9]+(?:\.[0-9]+)?[万千]?)\s*{re.escape(label)}|{re.escape(label)}\s*[·:]?\s*([0-9]+(?:\.[0-9]+)?[万千]?)"
        match = re.search(pattern, body_text)
        if not match:
            return None
        return self._extract_int(match.group(1) or match.group(2))

    def _title_to_live_title(self, page_title: str | None) -> str | None:
        title = self._normalize_text(page_title)
        if not title:
            return None
        suffix = " - 抖音直播"
        if title.endswith(suffix):
            title = title[: -len(suffix)]
        title = title.replace("的抖音直播间", "").strip()
        return title or None

    def _is_challenge_page(self, *, page_title: str | None, body_text: str | None) -> bool:
        text = f"{page_title or ''}\n{body_text or ''}"
        markers = [
            "验证码中间页",
            "验证码",
            "请完成下列验证",
            "安全验证",
            "人机验证",
            "请使用已登录账号的设备扫码",
        ]
        return any(marker in text for marker in markers)

    def _extract_room_id_from_url(self, url: str) -> str | None:
        match = re.search(r"live\.douyin\.com/(\d+)", url)
        return match.group(1) if match else None

    def _extract_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            multiplier = 1
            if text.endswith("万"):
                multiplier = 10000
                text = text[:-1]
            elif text.endswith("千"):
                multiplier = 1000
                text = text[:-1]
            digits = re.sub(r"[^\d.]", "", text)
            if digits:
                return int(float(digits) * multiplier)
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
