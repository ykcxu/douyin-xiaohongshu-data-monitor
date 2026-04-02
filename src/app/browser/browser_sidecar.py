from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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
    websocket_frames: list[dict] = field(default_factory=list)
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
    
    This class maintains persistent browser contexts to avoid the overhead
    of launching new browsers for each room check.
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
        self._lock = threading.RLock()
        self._running = False
        self._cleanup_thread: threading.Thread | None = None
        
    def start(self) -> None:
        """Start the sidecar and background maintenance threads."""
        with self._lock:
            if self._running:
                return
            
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._running = True
            
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        
    def stop(self) -> None:
        """Stop the sidecar and cleanup resources."""
        with self._lock:
            self._running = False
            
            # Close all contexts
            for entry in self._contexts.values():
                if entry.context:
                    entry.context.close()
            self._contexts.clear()
            
            # Close browser
            if self._browser:
                self._browser.close()
                self._browser = None
                
            # Stop playwright
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
                
    def _cleanup_loop(self) -> None:
        """Background thread to cleanup stale contexts."""
        while self._running:
            time.sleep(60)  # Check every minute
            self._cleanup_stale_contexts()
            
    def _cleanup_stale_contexts(self) -> None:
        """Remove contexts that haven't been used recently."""
        with self._lock:
            now = datetime.now(timezone.utc)
            stale_accounts = []
            
            for account_id, entry in self._contexts.items():
                age = (now - entry.last_used).total_seconds()
                if age > self.context_ttl_seconds:
                    stale_accounts.append(account_id)
                    
            for account_id in stale_accounts:
                entry = self._contexts.pop(account_id)
                if entry.context:
                    entry.context.close()
                    
    def _get_or_create_context(self, platform: str, account_id: str) -> BrowserContext:
        """Get existing context or create new one for account."""
        with self._lock:
            key = f"{platform}:{account_id}"
            
            # Check if context exists and is valid
            if key in self._contexts:
                entry = self._contexts[key]
                if entry.is_valid and entry.context:
                    entry.last_used = datetime.now(timezone.utc)
                    return entry.context
                    
            # Check context limit
            if len(self._contexts) >= self.max_contexts:
                # Remove oldest context
                oldest_key = min(
                    self._contexts.keys(),
                    key=lambda k: self._contexts[k].last_used
                )
                oldest_entry = self._contexts.pop(oldest_key)
                if oldest_entry.context:
                    oldest_entry.context.close()
                    
            # Create new context
            storage_state_path = self.login_state_service.resolve_storage_state_path(
                platform=platform,
                account_id=account_id,
            )
            
            context_options = {}
            if storage_state_path and Path(storage_state_path).exists():
                context_options["storage_state"] = str(storage_state_path)
                
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
        """Start watching a room and return session."""
        with self._lock:
            if room_id in self._rooms:
                return self._rooms[room_id]
                
            session = RoomWatchSession(
                room_id=room_id,
                account_id=account_id,
            )
            
            # Get or create context
            context = self._get_or_create_context(platform, account_id)
            
            # Create new page for room
            page = context.new_page()
            
            url = room_url or f"https://live.douyin.com/{room_id}"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            
            session.page = page
            session.last_update = datetime.now(timezone.utc)
            
            # Setup WebSocket monitoring
            self._setup_websocket_monitoring(session, page)
            
            self._rooms[room_id] = session
            return session
            
    def _setup_websocket_monitoring(self, session: RoomWatchSession, page: Page) -> None:
        """Setup listeners for WebSocket traffic."""
        def handle_ws(ws):
            # Check if this is the frontier/im WebSocket
            if "frontier" in ws.url or "/webcast/im/" in ws.url:
                ws.on("framereceived", lambda frame: self._on_ws_frame(session, frame, "received"))
                ws.on("framesent", lambda frame: self._on_ws_frame(session, frame, "sent"))
                
        page.on("websocket", handle_ws)
        
    def _on_ws_frame(self, session: RoomWatchSession, frame: Any, direction: str) -> None:
        """Handle incoming/outgoing WebSocket frames."""
        try:
            frame_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "direction": direction,
                "data": frame,
            }
            session.websocket_frames.append(frame_data)
            
            # Keep only last 1000 frames
            if len(session.websocket_frames) > 1000:
                session.websocket_frames = session.websocket_frames[-1000:]
        except Exception:
            pass
            
    def get_room_status(self, room_id: str) -> dict[str, Any] | None:
        """Get current status of a watched room."""
        with self._lock:
            if room_id not in self._rooms:
                return None
                
            session = self._rooms[room_id]
            if not session.page:
                return None
                
            try:
                html = session.page.content()
                
                # Extract room state from page
                page_state = self._extract_page_state(html)
                
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
        """Refresh the room page."""
        with self._lock:
            if room_id not in self._rooms:
                return False
                
            session = self._rooms[room_id]
            if session.page:
                try:
                    session.page.reload(wait_until="domcontentloaded", timeout=30000)
                    session.page.wait_for_timeout(3000)
                    session.last_update = datetime.now(timezone.utc)
                    return True
                except Exception:
                    session.is_active = False
                    return False
            return False
            
    def stop_watching(self, room_id: str) -> bool:
        """Stop watching a room."""
        with self._lock:
            if room_id not in self._rooms:
                return False
                
            session = self._rooms.pop(room_id)
            if session.page:
                session.page.close()
            return True
            
    def _extract_page_state(self, html: str) -> dict[str, Any]:
        """Extract room state from HTML."""
        import re
        import json
        
        result = {}
        
        # Try to find roomStore
        patterns = [
            (r'"roomStore":({.*?}),"linkmicStore":', 'roomStore'),
            (r'\\"roomStore\\":({.*?}),\\"linkmicStore\\":', 'roomStore'),
        ]
        
        for pattern, key in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    normalized = match.replace('\\"', '"')
                    data = json.loads(normalized)
                    result[key] = data
                    break
                except json.JSONDecodeError:
                    continue
                    
        return result
        
    def get_stats(self) -> dict[str, Any]:
        """Get sidecar statistics."""
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


# Global sidecar instance
_sidecar_instance: BrowserSidecar | None = None
_sidecar_lock = threading.Lock()


def get_browser_sidecar() -> BrowserSidecar:
    """Get or create global browser sidecar instance."""
    global _sidecar_instance
    with _sidecar_lock:
        if _sidecar_instance is None:
            _sidecar_instance = BrowserSidecar(headless=True)
            _sidecar_instance.start()
        return _sidecar_instance


def shutdown_browser_sidecar() -> None:
    """Shutdown global browser sidecar."""
    global _sidecar_instance
    with _sidecar_lock:
        if _sidecar_instance:
            _sidecar_instance.stop()
            _sidecar_instance = None
