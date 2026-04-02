from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from app.config.settings import get_settings
from app.services.login_state_service import LoginStateService


@dataclass
class RoomWatchSession:
    """Represents a single room being watched."""
    room_id: str
    account_id: str
    page: Page | None = None
    last_status: dict[str, Any] = field(default_factory=dict)
    last_update: datetime | None = None
    websocket_frames: list[dict[str, Any]] = field(default_factory=list)
    is_active: bool = True


@dataclass
class BrowserContextPoolEntry:
    """Manages a persistent browser context for an account."""
    account_id: str
    platform: str
    context: BrowserContext | None = None
    pages: dict[str, Page] = field(default_factory=dict)
    last_used: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_valid: bool = True


class BrowserSidecar:
    """Long-running browser sidecar for efficient live room monitoring."""

    def __init__(
        self,
        headless: bool = True,
        context_ttl_seconds: int = 300,
        max_contexts: int = 5,
    ) -> None:
        self.settings = get_settings()
        self.login_state_service = LoginStateService()
        self.headless = headless
        self.context_ttl_seconds = context_ttl_seconds
        self.max_contexts = max_contexts

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContextPoolEntry] = {}
        self._rooms: dict[str, RoomWatchSession] = {}
        self._lock = threading.RLock()
        self._running = False
        self._cleanup_thread: threading.Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._running = True

        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

            for entry in self._contexts.values():
                if entry.context:
                    entry.context.close()
            self._contexts.clear()
            self._rooms.clear()

            if self._browser:
                self._browser.close()
                self._browser = None

            if self._playwright:
                self._playwright.stop()
                self._playwright = None

    def _cleanup_loop(self) -> None:
        while self._running:
            time.sleep(60)
            self._cleanup_stale_contexts()

    def _cleanup_stale_contexts(self) -> None:
        with self._lock:
            now = datetime.now(timezone.utc)
            stale_keys: list[str] = []
            for key, entry in self._contexts.items():
                age = (now - entry.last_used).total_seconds()
                if age > self.context_ttl_seconds:
                    stale_keys.append(key)
            for key in stale_keys:
                entry = self._contexts.pop(key)
                if entry.context:
                    entry.context.close()

    def _get_or_create_context(self, platform: str, account_id: str) -> BrowserContext:
        with self._lock:
            key = f"{platform}:{account_id}"
            if key in self._contexts:
                entry = self._contexts[key]
                if entry.is_valid and entry.context:
                    entry.last_used = datetime.now(timezone.utc)
                    return entry.context

            if len(self._contexts) >= self.max_contexts:
                oldest_key = min(self._contexts.keys(), key=lambda k: self._contexts[k].last_used)
                oldest_entry = self._contexts.pop(oldest_key)
                if oldest_entry.context:
                    oldest_entry.context.close()

            storage_state_path = self.login_state_service.resolve_storage_state_path(
                platform=platform,
                account_id=account_id,
            )
            context_options: dict[str, Any] = {}
            if storage_state_path and Path(storage_state_path).exists():
                context_options["storage_state"] = str(storage_state_path)

            if self._browser is None:
                raise RuntimeError("BrowserSidecar has not been started")
            context = self._browser.new_context(**context_options)
            entry = BrowserContextPoolEntry(
                account_id=account_id,
                platform=platform,
                context=context,
            )
            self._contexts[key] = entry
            return context

    def watch_room(
        self,
        room_id: str,
        account_id: str,
        platform: str = "douyin",
        room_url: str | None = None,
    ) -> RoomWatchSession:
        with self._lock:
            if room_id in self._rooms:
                return self._rooms[room_id]

            session = RoomWatchSession(room_id=room_id, account_id=account_id)
            context = self._get_or_create_context(platform, account_id)
            page = context.new_page()
            cdp_session = context.new_cdp_session(page)
            cdp_session.send("Network.enable")
            session.cdp_session = cdp_session

            self._setup_websocket_monitoring(session, page)

            url = room_url or f"https://live.douyin.com/{room_id}"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            session.page = page
            session.last_update = datetime.now(timezone.utc)
            self._rooms[room_id] = session
            return session

    def _setup_websocket_monitoring(self, session: RoomWatchSession, page: Page) -> None:
        cdp = session.cdp_session
        if cdp is None:
            return

        def on_websocket_created(params: dict[str, Any]) -> None:
            request_id = params.get("requestId")
            if request_id:
                session.ws_request_ids.add(str(request_id))

        def on_websocket_frame_received(params: dict[str, Any]) -> None:
            if str(params.get("requestId") or "") not in session.ws_request_ids:
                return
            response_payload = params.get("response", {})
            self._on_cdp_ws_frame(session, response_payload, "received")

        def on_websocket_frame_sent(params: dict[str, Any]) -> None:
            if str(params.get("requestId") or "") not in session.ws_request_ids:
                return
            response_payload = params.get("response", {})
            self._on_cdp_ws_frame(session, response_payload, "sent")

        cdp.on("Network.webSocketCreated", on_websocket_created)
        cdp.on("Network.webSocketFrameReceived", on_websocket_frame_received)
        cdp.on("Network.webSocketFrameSent", on_websocket_frame_sent)

    def _on_cdp_ws_frame(self, session: RoomWatchSession, frame: dict[str, Any], direction: str) -> None:
        try:
            opcode = frame.get("opcode")
            payload = frame.get("payloadData")
            item: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "direction": direction,
                "opcode": opcode,
            }
            if opcode == 2 and payload:
                item["is_binary"] = True
                item["data_b64"] = str(payload)
            else:
                item["is_binary"] = False
                item["text"] = str(payload or "")

            session.websocket_frames.append(item)
            if len(session.websocket_frames) > 1000:
                session.websocket_frames = session.websocket_frames[-1000:]
        except Exception:
            pass

    def get_websocket_frames(
        self,
        room_id: str,
        *,
        since: int = 0,
        direction: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            session = self._rooms.get(room_id)
            if session is None:
                return [], since
            frames = session.websocket_frames[since:]
            if direction is not None:
                frames = [f for f in frames if f.get("direction") == direction]
            return frames, len(session.websocket_frames)

    def get_room_status(self, room_id: str) -> dict[str, Any] | None:
        with self._lock:
            session = self._rooms.get(room_id)
            if session is None or session.page is None:
                return None
            try:
                html = session.page.content()
                page_state = self._extract_page_state(html)

                # Prefer live page runtime state when available; HTML may contain stale/partial roomStore.
                try:
                    js_room_store = session.page.evaluate("""() => {
                        if (window.roomStore) return window.roomStore;
                        return null;
                    }""")
                    if js_room_store:
                        page_state["roomStore"] = js_room_store
                except Exception:
                    pass

                try:
                    js_user_info = session.page.evaluate("""() => {
                        if (window.defaultHeaderUserInfo) return window.defaultHeaderUserInfo;
                        return null;
                    }""")
                    if js_user_info and "defaultHeaderUserInfo" not in page_state:
                        page_state["defaultHeaderUserInfo"] = js_user_info
                except Exception:
                    pass

                session.last_status = page_state
                session.last_update = datetime.now(timezone.utc)
                return {
                    "room_id": room_id,
                    "status": page_state,
                    "last_update": session.last_update.isoformat(),
                    "websocket_frames_count": len(session.websocket_frames),
                }
            except Exception as e:
                return {"error": str(e), "room_id": room_id}

    def refresh_room(self, room_id: str) -> bool:
        with self._lock:
            session = self._rooms.get(room_id)
            if session is None or session.page is None:
                return False
            try:
                session.page.reload(wait_until="domcontentloaded", timeout=30000)
                session.page.wait_for_timeout(3000)
                session.last_update = datetime.now(timezone.utc)
                return True
            except Exception:
                session.is_active = False
                return False

    def stop_watching(self, room_id: str) -> bool:
        with self._lock:
            session = self._rooms.pop(room_id, None)
            if session is None:
                return False
            if session.page:
                session.page.close()
            return True

    def _extract_page_state(self, html: str) -> dict[str, Any]:
        import re

        result: dict[str, Any] = {}
        patterns = [
            (r'"roomStore":({.*?}),"linkmicStore":', "roomStore"),
            (r'\\"roomStore\\":({.*?}),\\"linkmicStore\\":', "roomStore"),
        ]
        for pattern, key in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    normalized = match.replace('\\"', '"')
                    result[key] = json.loads(normalized)
                    break
                except json.JSONDecodeError:
                    continue
        return result

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "contexts_count": len(self._contexts),
                "rooms_count": len(self._rooms),
                "contexts": [
                    {
                        "account_id": entry.account_id,
                        "platform": entry.platform,
                        "last_used": entry.last_used.isoformat(),
                        "is_valid": entry.is_valid,
                    }
                    for entry in self._contexts.values()
                ],
                "rooms": [
                    {
                        "room_id": session.room_id,
                        "account_id": session.account_id,
                        "is_active": session.is_active,
                        "last_update": session.last_update.isoformat() if session.last_update else None,
                        "websocket_frames": len(session.websocket_frames),
                    }
                    for session in self._rooms.values()
                ],
            }


_sidecar_instance: BrowserSidecar | None = None
_sidecar_lock = threading.Lock()


def get_browser_sidecar() -> BrowserSidecar:
    global _sidecar_instance
    with _sidecar_lock:
        if _sidecar_instance is None:
            settings = get_settings()
            _sidecar_instance = BrowserSidecar(headless=settings.douyin_browser_headless)
            _sidecar_instance.start()
        return _sidecar_instance


def shutdown_browser_sidecar() -> None:
    global _sidecar_instance
    with _sidecar_lock:
        if _sidecar_instance is not None:
            _sidecar_instance.stop()
            _sidecar_instance = None
