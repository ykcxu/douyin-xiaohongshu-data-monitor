from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from app.browser.cdp_websocket_trace import attach_cdp_websocket_trace
from app.config.settings import get_settings
from app.services.login_state_service import LoginStateService

T = TypeVar("T")


@dataclass
class RoomWatchSession:
    """Represents a single room being watched."""
    room_id: str
    account_id: str
    platform: str = "douyin"
    page: Page | None = None
    cdp_session: Any | None = None
    ws_request_ids: set[str] = field(default_factory=set)
    ws_request_urls: dict[str, str] = field(default_factory=dict)
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
    """Long-running browser sidecar for efficient live room monitoring.

    Playwright sync API objects are thread-affine. To avoid greenlet/thread errors,
    all browser operations run on a dedicated owner thread and public methods marshal
    work to that thread.
    """

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

        self._running = False
        self._worker_thread: threading.Thread | None = None
        self._owner_thread_id: int | None = None
        self._command_queue: queue.Queue[tuple[Callable[[], Any] | None, Future[Any] | None]] = queue.Queue()
        self._ready = threading.Event()
        self._init_error: BaseException | None = None
        self._state_lock = threading.Lock()

    def start(self) -> None:
        with self._state_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            self._running = True
            self._init_error = None
            self._ready.clear()
            self._worker_thread = threading.Thread(
                target=self._thread_main,
                name="browser-sidecar",
                daemon=True,
            )
            self._worker_thread.start()

        if not self._ready.wait(timeout=30):
            raise RuntimeError("BrowserSidecar start timed out")
        if self._init_error is not None:
            raise RuntimeError(f"BrowserSidecar failed to start: {self._init_error}") from self._init_error

    def stop(self) -> None:
        with self._state_lock:
            worker = self._worker_thread
            if worker is None:
                return
            self._running = False
            self._command_queue.put((None, None))

        if threading.get_ident() != self._owner_thread_id:
            worker.join(timeout=15)

        with self._state_lock:
            self._worker_thread = None
            self._owner_thread_id = None

    def _thread_main(self) -> None:
        last_cleanup = time.monotonic()
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._owner_thread_id = threading.get_ident()
            self._ready.set()

            while self._running:
                try:
                    job, future = self._command_queue.get(timeout=0.2)
                except queue.Empty:
                    self._pump_room_events()
                    now = time.monotonic()
                    if now - last_cleanup >= 60:
                        self._cleanup_stale_contexts()
                        last_cleanup = now
                    continue

                if job is None:
                    break

                try:
                    result = job()
                except BaseException as exc:
                    if future and not future.done():
                        future.set_exception(exc)
                else:
                    if future and not future.done():
                        future.set_result(result)
        except BaseException as exc:
            self._init_error = exc
            self._ready.set()
            self._fail_pending_futures(exc)
        finally:
            self._shutdown_owner_resources()
            self._owner_thread_id = None
            self._running = False
            self._ready.set()

    def _fail_pending_futures(self, exc: BaseException) -> None:
        while True:
            try:
                _, future = self._command_queue.get_nowait()
            except queue.Empty:
                break
            if future and not future.done():
                future.set_exception(exc)

    def _shutdown_owner_resources(self) -> None:
        for session in list(self._rooms.values()):
            try:
                if session.page:
                    session.page.close()
            except Exception:
                pass
        self._rooms.clear()

        for entry in list(self._contexts.values()):
            try:
                if entry.context:
                    entry.context.close()
            except Exception:
                pass
        self._contexts.clear()

        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        self._browser = None

        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._playwright = None

    def _run_on_owner(self, fn: Callable[[], T], timeout: float | None = 60) -> T:
        if threading.get_ident() == self._owner_thread_id:
            return fn()
        if not self._running:
            raise RuntimeError("BrowserSidecar has not been started")

        future: Future[T] = Future()
        self._command_queue.put((fn, future))
        return future.result(timeout=timeout)

    def _pump_room_events(self) -> None:
        sessions = list(self._rooms.values())
        for session in sessions:
            page = session.page
            if page is None or not session.is_active:
                continue
            try:
                page.wait_for_timeout(50)
                session.last_update = datetime.now(timezone.utc)
            except Exception:
                session.is_active = False

    def _cleanup_stale_contexts(self) -> None:
        now = datetime.now(timezone.utc)
        active_keys = {
            f"{session.platform}:{session.account_id}"
            for session in self._rooms.values()
            if session.is_active
        }
        stale_keys: list[str] = []
        for key, entry in self._contexts.items():
            if key in active_keys:
                continue
            age = (now - entry.last_used).total_seconds()
            if age > self.context_ttl_seconds:
                stale_keys.append(key)
        for key in stale_keys:
            entry = self._contexts.pop(key)
            try:
                if entry.context:
                    entry.context.close()
            except Exception:
                pass

    def _get_or_create_context(self, platform: str, account_id: str) -> BrowserContext:
        key = f"{platform}:{account_id}"
        entry = self._contexts.get(key)
        if entry and entry.is_valid and entry.context:
            entry.last_used = datetime.now(timezone.utc)
            return entry.context

        if len(self._contexts) >= self.max_contexts:
            oldest_key = min(self._contexts.keys(), key=lambda k: self._contexts[k].last_used)
            oldest_entry = self._contexts.pop(oldest_key)
            try:
                if oldest_entry.context:
                    oldest_entry.context.close()
            except Exception:
                pass

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
        return self._run_on_owner(
            lambda: self._watch_room_impl(
                room_id=room_id,
                account_id=account_id,
                platform=platform,
                room_url=room_url,
            )
        )

    def _watch_room_impl(
        self,
        *,
        room_id: str,
        account_id: str,
        platform: str,
        room_url: str | None,
    ) -> RoomWatchSession:
        existing = self._rooms.get(room_id)
        if existing is not None:
            if existing.is_active and existing.page is not None:
                return existing
            self._stop_watching_impl(room_id)

        session = RoomWatchSession(room_id=room_id, account_id=account_id, platform=platform)
        context = self._get_or_create_context(platform, account_id)
        page = context.new_page()
        cdp_session = context.new_cdp_session(page)
        cdp_session.send("Network.enable")
        session.cdp_session = cdp_session

        self._setup_websocket_monitoring(session)

        url = room_url or f"https://live.douyin.com/{room_id}"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        session.page = page
        session.last_update = datetime.now(timezone.utc)
        self._rooms[room_id] = session
        return session

    def _setup_websocket_monitoring(self, session: RoomWatchSession) -> None:
        cdp = session.cdp_session
        if cdp is None:
            return

        def emit(event: dict[str, object]) -> None:
            try:
                event_name = str(event.get("event") or "")
                request_id = str(event.get("request_id") or "")
                if event_name == "cdp_websocket_created":
                    if request_id:
                        session.ws_request_ids.add(request_id)
                        session.ws_request_urls[request_id] = str(event.get("url") or "")
                    return

                if event_name not in {"cdp_websocket_frame_received", "cdp_websocket_frame_sent"}:
                    return
                if request_id and request_id not in session.ws_request_ids:
                    session.ws_request_ids.add(request_id)
                opcode = event.get("opcode")
                payload_full = str(event.get("payload_data") or "")
                payload_preview = str(event.get("payload_preview") or payload_full[:5000])
                payload = payload_full or payload_preview
                item: dict[str, Any] = {
                    "timestamp": event.get("ts") or datetime.now(timezone.utc).isoformat(),
                    "direction": "received" if event_name.endswith("received") else "sent",
                    "opcode": opcode,
                    "request_id": request_id,
                    "url": session.ws_request_urls.get(request_id, ""),
                    "payload_length": event.get("payload_length"),
                }
                if opcode == 2 and payload:
                    item["is_binary"] = True
                    item["data_b64"] = payload
                    item["data_b64_preview"] = payload_preview
                else:
                    item["is_binary"] = False
                    item["text"] = payload_preview
                session.websocket_frames.append(item)
                if len(session.websocket_frames) > 1000:
                    session.websocket_frames = session.websocket_frames[-1000:]
            except Exception:
                pass

        attach_cdp_websocket_trace(cdp, emit=emit)

    def get_websocket_frames(
        self,
        room_id: str,
        *,
        since: int = 0,
        direction: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        return self._run_on_owner(
            lambda: self._get_websocket_frames_impl(room_id=room_id, since=since, direction=direction)
        )

    def _get_websocket_frames_impl(
        self,
        *,
        room_id: str,
        since: int,
        direction: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        session = self._rooms.get(room_id)
        if session is None:
            return [], since
        frames = session.websocket_frames[since:]
        if direction is not None:
            frames = [f for f in frames if f.get("direction") == direction]
        return frames, len(session.websocket_frames)

    def get_room_status(self, room_id: str) -> dict[str, Any] | None:
        return self._run_on_owner(lambda: self._get_room_status_impl(room_id))

    def _get_room_status_impl(self, room_id: str) -> dict[str, Any] | None:
        session = self._rooms.get(room_id)
        if session is None or session.page is None:
            return None
        if not session.is_active:
            return {"error": "room session inactive", "room_id": room_id}
        try:
            html = session.page.content()
            page_state = self._extract_page_state(html)

            try:
                js_state = session.page.evaluate(
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
                        page_state["roomStore"] = js_state["roomStore"]
                    if isinstance(js_state.get("defaultHeaderUserInfo"), dict):
                        page_state["defaultHeaderUserInfo"] = js_state["defaultHeaderUserInfo"]
                    if js_state.get("pageTitle"):
                        page_state["pageTitle"] = js_state["pageTitle"]
                    if js_state.get("bodyText"):
                        page_state["bodyText"] = js_state["bodyText"]
                    if js_state.get("storeKeys"):
                        page_state["storeKeys"] = js_state["storeKeys"]
            except Exception:
                pass

            session.last_status = page_state
            session.last_update = datetime.now(timezone.utc)
            return {
                "room_id": room_id,
                "status": page_state,
                "last_update": session.last_update.isoformat(),
                "websocket_frames_count": len(session.websocket_frames),
                "websocket_urls": list(session.ws_request_urls.values())[:20],
            }
        except Exception as e:
            return {"error": str(e), "room_id": room_id}

    def refresh_room(self, room_id: str) -> bool:
        return self._run_on_owner(lambda: self._refresh_room_impl(room_id))

    def _refresh_room_impl(self, room_id: str) -> bool:
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
        return self._run_on_owner(lambda: self._stop_watching_impl(room_id))

    def _stop_watching_impl(self, room_id: str) -> bool:
        session = self._rooms.pop(room_id, None)
        if session is None:
            return False
        try:
            if session.page:
                session.page.close()
        except Exception:
            pass
        return True

    def _extract_page_state(self, html: str) -> dict[str, Any]:
        import json
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
        return self._run_on_owner(self._get_stats_impl)

    def _get_stats_impl(self) -> dict[str, Any]:
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
                    "ws_request_ids": len(session.ws_request_ids),
                    "ws_urls": list(session.ws_request_urls.values())[:10],
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
