from __future__ import annotations

import base64
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from sqlalchemy import select

from app.browser.browser_sidecar import get_browser_sidecar
from app.collector.douyin.live.exceptions import DouyinProviderError
from app.collector.douyin.live.status_collector import (
    DouyinLiveStatusCollector,
    StubDouyinLiveStatusCollector,
)
from app.collector.douyin.live.proto import douyin_webcast_pb2 as pb
from app.collector.douyin.live.websocket_decoder import DouyinWebSocketDecoder
from app.config.settings import get_settings
from app.db.session import get_db_session
from app.models.douyin_live_comment import DouyinLiveComment
from app.models.douyin_live_room import DouyinLiveRoom
from app.models.douyin_live_session import DouyinLiveSession
from app.models.douyin_live_snapshot import DouyinLiveSnapshot
from app.services.jsonl_archive_service import JsonlArchiveService
from app.services.login_state_service import LoginStateService


class LiveMonitorService:
    def __init__(self, collector: DouyinLiveStatusCollector | None = None) -> None:
        self.collector = collector or StubDouyinLiveStatusCollector()
        self.archive_service = JsonlArchiveService()
        self.login_state_service = LoginStateService()
        self.settings = get_settings()
        self.ws_decoder = DouyinWebSocketDecoder()
        self._room_frame_cursors: dict[str, int] = {}
        self._sidecar_errors: dict[str, str] = {}
        self._watcher_room_offset = 0
        self._room_meta_probe_at: dict[str, datetime] = {}
        self._room_watch_retry_at: dict[str, datetime] = {}

    def _get_sidecar(self):
        return get_browser_sidecar()

    def _safe_get_sidecar_stats(self) -> dict[str, object]:
        try:
            return self._get_sidecar().get_stats()
        except Exception as exc:
            return {
                "running": False,
                "contexts_count": 0,
                "rooms_count": 0,
                "contexts": [],
                "rooms": [],
                "stats_error": f"{type(exc).__name__}: {exc}",
            }

    def _safe_get_room_meta(self, room_id: str) -> dict[str, object] | None:
        try:
            return self._get_sidecar().get_room_meta(room_id)
        except Exception as exc:
            self._sidecar_errors[room_id] = f"room-meta {type(exc).__name__}: {exc}"
            print(f"[sidecar-room-meta-error] room_id={room_id} error={type(exc).__name__}: {exc}")
            return None

    def get_sidecar_stats(self) -> dict[str, object]:
        stats = self._safe_get_sidecar_stats()
        stats["frame_cursors"] = dict(self._room_frame_cursors)
        stats["sidecar_errors"] = dict(self._sidecar_errors)
        return stats

    def get_watcher_stats(self) -> dict[str, object]:
        with get_db_session() as session:
            active_live_sessions = session.execute(
                select(DouyinLiveSession).where(DouyinLiveSession.status == "live")
            ).scalars().all()
        stats = self.get_sidecar_stats()
        stats["active_live_sessions"] = len(active_live_sessions)
        stats["active_live_room_ids"] = [item.room_id for item in active_live_sessions[:50]]
        return stats

    def debug_decode_room_frames(self, room_id: str, limit: int = 5) -> dict[str, object]:
        frames, cursor = self._get_sidecar().get_websocket_frames(room_id, since=0, direction="received")
        binary_frames = [frame for frame in frames if frame.get("is_binary") and frame.get("data_b64")]

        # Most rooms produce a lot of heartbeat frames (payloadType=hb) which decode to 0 messages.
        # For debugging the real ingest pipeline we prefer frames that actually carry decoded messages.
        # We scan backwards from the newest frames and pick the first N meaningful samples.
        decoded_items: list[dict[str, object]] = []
        scanned = 0
        max_scan = max(200, (limit or 0) * 200)

        for frame in reversed(binary_frames):
            if limit > 0 and len(decoded_items) >= limit:
                break
            scanned += 1
            if scanned > max_scan:
                break
            if not frame.get("data_b64"):
                continue

            data_b64 = str(frame["data_b64"])
            raw_prefix_hex = None
            raw_len = None
            raw: bytes | None = None
            try:
                raw = base64.b64decode(data_b64)
                raw_len = len(raw)
                raw_prefix_hex = raw[:24].hex()
            except Exception:
                raw = None

            # Decode via protobuf decoder (business messages). Keep errors for visibility.
            try:
                result = self.ws_decoder.decode_frame_base64(data_b64)
            except Exception as exc:
                result = type("_R", (), {"error": f"decode_exception:{type(exc).__name__}:{exc}", "messages": []})()

            push_meta: dict[str, object] = {}
            push_payload_type = None
            try:
                if raw is not None:
                    push_frame = pb.PushFrame()
                    push_frame.ParseFromString(raw)
                    payload_preview_bytes = bytes(push_frame.payload[:120])
                    payload_preview_text = payload_preview_bytes.decode("utf-8", errors="replace")
                    push_payload_type = push_frame.payloadType
                    push_meta = {
                        "push_payload_type": push_frame.payloadType,
                        "push_payload_encoding": push_frame.payloadEncoding,
                        "push_payload_len": len(push_frame.payload),
                        "push_payload_preview_text": payload_preview_text,
                        "push_headers": MessageToDict(push_frame).get("headersList", [])[:10],
                    }
            except Exception as inspect_error:
                push_meta = {"push_inspect_error": str(inspect_error)}

            message_count = len(getattr(result, "messages", []) or [])
            is_heartbeat = str(push_payload_type or "").lower() == "hb"

            meaningful = bool(result.error) or (message_count > 0) or (not is_heartbeat)
            if not meaningful:
                continue

            decoded_items.append({
                "timestamp": frame.get("timestamp"),
                "request_id": frame.get("request_id"),
                "url": frame.get("url"),
                "host": self._classify_ws_host(frame.get("url")),
                "opcode": frame.get("opcode"),
                "raw_len": raw_len,
                "raw_prefix_hex": raw_prefix_hex,
                "error": getattr(result, "error", ""),
                "message_count": message_count,
                "methods": [m.method for m in (getattr(result, "messages", []) or [])[:20]],
                "messages_preview": [
                    {
                        "msg_id": m.msg_id,
                        "method": m.method,
                        "room_id": m.room_id,
                        "timestamp": m.timestamp,
                        "user_id": m.user_id,
                        "nickname": m.nickname,
                        "content": m.content,
                    }
                    for m in (getattr(result, "messages", []) or [])[:5]
                ],
                **push_meta,
            })

        decoded_items.reverse()
        stats = self._safe_get_sidecar_stats()
        room_stats = next((x for x in stats.get("rooms", []) if x.get("room_id") == room_id), {})
        return {
            "room_id": room_id,
            "total_frames": len(frames),
            "cursor": cursor,
            "ws_urls": room_stats.get("ws_urls", []),
            "decoded_samples": decoded_items,
            "scanned_binary_frames": scanned,
        }

    def debug_room_frames(self, room_id: str, limit: int = 20) -> dict[str, object]:
        frames, cursor = self._get_sidecar().get_websocket_frames(room_id, since=0, direction="received")
        recent = frames[-limit:] if limit > 0 else frames
        items: list[dict[str, object]] = []
        for idx, frame in enumerate(recent):
            data_b64 = frame.get("data_b64")
            raw_len = None
            raw_prefix_hex = None
            raw_prefix_text = None
            if frame.get("is_binary") and data_b64:
                try:
                    raw = base64.b64decode(str(data_b64))
                    raw_len = len(raw)
                    raw_prefix_hex = raw[:32].hex()
                    raw_prefix_text = raw[:32].decode("utf-8", errors="replace")
                except Exception:
                    pass
            items.append({
                "index": idx,
                "timestamp": frame.get("timestamp"),
                "request_id": frame.get("request_id"),
                "url": frame.get("url"),
                "host": self._classify_ws_host(frame.get("url")),
                "opcode": frame.get("opcode"),
                "is_binary": frame.get("is_binary", False),
                "raw_len": raw_len,
                "raw_prefix_hex": raw_prefix_hex,
                "raw_prefix_text": raw_prefix_text,
            })
        return {
            "room_id": room_id,
            "total_frames": len(frames),
            "cursor": cursor,
            "frames": items,
        }

    def scan_rooms_once(self) -> dict[str, int]:
        scanned = 0
        live_count = 0
        opened_sessions = 0
        closed_sessions = 0
        snapshots_created = 0

        with get_db_session() as session:
            stmt = (
                select(DouyinLiveRoom)
                .where(DouyinLiveRoom.is_monitor_enabled.is_(True))
                .order_by(DouyinLiveRoom.monitor_priority.asc(), DouyinLiveRoom.id.asc())
            )
            rooms = session.execute(stmt).scalars().all()

            for room in rooms:
                scanned += 1
                try:
                    status = self.collector.fetch_room_status(room)
                except DouyinProviderError as exc:
                    if room.account_id:
                        self.login_state_service.mark_state(
                            platform="douyin",
                            account_id=room.account_id,
                            status="error",
                            last_error_code=exc.__class__.__name__,
                            last_error_message=str(exc),
                        )
                    room.last_live_status = "error"
                    room.updated_at = datetime.now(timezone.utc)
                    continue

                room.last_live_status = status.live_status
                room.nickname = status.nickname or room.nickname
                room.live_title = status.live_title or room.live_title

                active_session = self._get_active_session(session, room.id)

                if status.is_live:
                    live_count += 1
                    if active_session is None:
                        active_session = self._open_session(session, room, status)
                        opened_sessions += 1
                    room.last_live_start_time = status.fetched_at
                    self._create_snapshot(session, room, active_session, status)
                    snapshots_created += 1
                elif active_session is not None:
                    self._close_session(session, room, active_session, status.fetched_at)
                    self._stop_sidecar_watch(room.room_id)
                    closed_sessions += 1

                room.updated_at = datetime.now(timezone.utc)

        return {
            "scanned": scanned,
            "live_count": live_count,
            "opened_sessions": opened_sessions,
            "closed_sessions": closed_sessions,
            "snapshots_created": snapshots_created,
        }

    def ingest_status_sample(
        self,
        *,
        room_pk: int,
        status_payload: dict[str, object],
    ) -> dict[str, int | str]:
        status = self._status_from_payload(status_payload)

        with get_db_session() as session:
            room = session.get(DouyinLiveRoom, room_pk)
            if room is None:
                raise ValueError(f"Live room {room_pk} not found")

            active_session = self._get_active_session(session, room.id)
            live_count = 0

            room.last_live_status = status.live_status
            room.nickname = status.nickname or room.nickname
            room.live_title = status.live_title or room.live_title

            if status.is_live:
                live_count = 1
                if active_session is None:
                    active_session = self._open_session(session, room, status)
                room.last_live_start_time = status.fetched_at
                self._create_snapshot(session, room, active_session, status)
            elif active_session is not None:
                self._close_session(session, room, active_session, status.fetched_at)
                self._stop_sidecar_watch(room.room_id)

            room.updated_at = datetime.now(timezone.utc)
            session.flush()

            return {
                "room_pk": room.id,
                "session_id": active_session.id if active_session is not None else 0,
                "live_count": live_count,
                "live_status": status.live_status,
            }

    def watcher_tick_once(self) -> dict[str, int]:
        watched = 0
        ingested_rooms = 0
        decoded_message_rooms = 0
        comment_written_rooms = 0
        inserted_comments = 0
        stopped_rooms = 0
        newly_watched = 0
        meta_checked_rooms = 0
        configured_max_new_rooms = max(0, int(getattr(self.settings, "douyin_watcher_max_new_rooms_per_tick", 1) or 0))
        max_rooms = max(1, int(getattr(self.settings, "douyin_watcher_max_rooms_per_tick", 2) or 2))
        max_new_rooms = configured_max_new_rooms
        sidecar_stats = self._safe_get_sidecar_stats()
        sidecar_room_ids = {
            str(item.get("room_id"))
            for item in sidecar_stats.get("rooms", [])
            if item.get("room_id")
        }

        with get_db_session() as session:
            stmt = (
                select(DouyinLiveSession, DouyinLiveRoom)
                .join(DouyinLiveRoom, DouyinLiveRoom.id == DouyinLiveSession.live_room_id)
                .where(DouyinLiveSession.status == "live")
                .order_by(DouyinLiveSession.start_time.asc())
            )
            rows = session.execute(stmt).all()
            if rows:
                offset = self._watcher_room_offset % len(rows)
                ordered_rows = rows[offset:] + rows[:offset]
                self._watcher_room_offset = (offset + max_rooms) % len(rows)
            else:
                ordered_rows = []
                self._watcher_room_offset = 0

            if configured_max_new_rooms <= 0 and not self._room_frame_cursors and ordered_rows:
                max_new_rooms = 1

            for live_session, room in ordered_rows:
                if watched >= max_rooms:
                    break
                watched += 1
                already_watching = room.room_id in self._room_frame_cursors or room.room_id in sidecar_room_ids
                current_meta = None
                if already_watching and room.room_id in sidecar_room_ids:
                    self._room_frame_cursors.setdefault(room.room_id, 0)
                    current_meta = self._safe_get_room_meta(room.room_id)
                if not already_watching:
                    if newly_watched >= max_new_rooms:
                        continue
                    self._ensure_sidecar_watch(room)
                    current_meta = self._safe_get_room_meta(room.room_id)
                    if current_meta is None:
                        continue
                    self._room_frame_cursors.setdefault(room.room_id, 0)
                    newly_watched += 1

                ingest_result = self._ingest_sidecar_messages(room, live_session)
                if ingest_result.get("decoded_messages", 0) > 0:
                    decoded_message_rooms += 1
                if ingest_result.get("inserted_comments", 0) > 0:
                    ingested_rooms += 1
                    comment_written_rooms += 1
                    inserted_comments += int(ingest_result.get("inserted_comments", 0))

                current_meta = current_meta or self._maybe_get_room_meta(room.room_id)
                if current_meta is not None:
                    meta_checked_rooms += 1
                if current_meta and not current_meta.get("is_active", True):
                    self._stop_sidecar_watch(room.room_id)
                    stopped_rooms += 1

        return {
            "watched": watched,
            "ingested_rooms": ingested_rooms,
            "decoded_message_rooms": decoded_message_rooms,
            "comment_written_rooms": comment_written_rooms,
            "inserted_comments": inserted_comments,
            "stopped_rooms": stopped_rooms,
            "newly_watched": newly_watched,
            "meta_checked_rooms": meta_checked_rooms,
        }

    def _ensure_sidecar_watch(self, room: DouyinLiveRoom) -> None:
        try:
            now = datetime.now(timezone.utc)
            retry_at = self._room_watch_retry_at.get(room.room_id)
            if retry_at is not None and retry_at > now:
                retry_after_seconds = int((retry_at - now).total_seconds())
                self._sidecar_errors[room.room_id] = f"skipped:watch-retry-after={retry_after_seconds}"
                return
            if not room.account_id:
                self._sidecar_errors[room.room_id] = "missing account_id"
                return
            login_state = self.login_state_service.get_state(platform="douyin", account_id=room.account_id)
            if login_state is not None and login_state.status == "challenge":
                updated_at = getattr(login_state, "updated_at", None)
                retry_after_seconds = None
                if updated_at is not None:
                    retry_at = updated_at + timedelta(seconds=self.settings.douyin_challenge_retry_seconds)
                    retry_after_seconds = int((retry_at - now).total_seconds())
                if retry_after_seconds is None or retry_after_seconds > 0:
                    suffix = f":retry-after={retry_after_seconds}" if retry_after_seconds is not None else ""
                    self._sidecar_errors[room.room_id] = f"skipped:challenge-state{suffix}"
                    return
            self._get_sidecar().watch_room(
                room_id=room.room_id,
                account_id=room.account_id,
                platform="douyin",
                room_url=room.room_url,
            )
            self._sidecar_errors.pop(room.room_id, None)
            self._room_meta_probe_at.pop(room.room_id, None)
            self._room_watch_retry_at.pop(room.room_id, None)
        except Exception as e:
            retry_seconds = max(30, int(getattr(self.settings, "douyin_watcher_watch_retry_seconds", 180) or 180))
            self._room_watch_retry_at[room.room_id] = now + timedelta(seconds=retry_seconds)
            self._sidecar_errors[room.room_id] = f"{type(e).__name__}: {e}:retry-after={retry_seconds}"
            print(f"[sidecar-watch-error] room_id={room.room_id} error={type(e).__name__}: {e} retry_after={retry_seconds}")
            return

    def _maybe_get_room_meta(self, room_id: str) -> dict[str, object] | None:
        now = datetime.now(timezone.utc)
        last_probe_at = self._room_meta_probe_at.get(room_id)
        if last_probe_at is not None and (now - last_probe_at).total_seconds() < 120:
            return None
        self._room_meta_probe_at[room_id] = now
        return self._safe_get_room_meta(room_id)

    def _stop_sidecar_watch(self, room_id: str) -> None:
        self._room_frame_cursors.pop(room_id, None)
        self._room_meta_probe_at.pop(room_id, None)
        self._room_watch_retry_at.pop(room_id, None)
        try:
            self._get_sidecar().stop_watching(room_id)
        except Exception:
            pass

    def _ingest_sidecar_messages(self, room: DouyinLiveRoom, live_session: DouyinLiveSession) -> dict[str, int]:
        cursor = self._room_frame_cursors.get(room.room_id, 0)
        result = {
            "frames": 0,
            "decoded_messages": 0,
            "inserted_comments": 0,
        }
        try:
            frames, next_cursor = self._get_sidecar().get_websocket_frames(
                room.room_id,
                since=cursor,
                direction="received",
            )
        except Exception as e:
            self._sidecar_errors[room.room_id] = f"frame-read {type(e).__name__}: {e}"
            print(f"[sidecar-frame-error] room_id={room.room_id} error={type(e).__name__}: {e}")
            return result
        self._room_frame_cursors[room.room_id] = next_cursor
        result["frames"] = len(frames)

        for frame in frames:
            if not frame.get("is_binary"):
                continue
            data_b64 = frame.get("data_b64")
            if not data_b64:
                continue
            try:
                decoded = self.ws_decoder.decode_frame_base64(str(data_b64))
            except Exception:
                continue
            for msg in decoded.messages:
                if msg.method not in {
                    "WebcastChatMessage",
                    "WebcastMemberMessage",
                    "WebcastGiftMessage",
                    "WebcastLikeMessage",
                    "WebcastSocialMessage",
                }:
                    continue
                result["decoded_messages"] += 1
                payload = {
                    "message_id": str(msg.msg_id or f"{live_session.session_no}-{msg.method}-{frame.get('timestamp')}-{msg.user_id}"),
                    "message_type": msg.method.replace("Webcast", "").replace("Message", "").lower(),
                    "event_time": self._millis_to_iso(msg.timestamp) or frame.get("timestamp"),
                    "fetch_time": frame.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                    "user_id": str(msg.user_id) if msg.user_id else None,
                    "nickname": msg.nickname or None,
                    "display_name": msg.nickname or None,
                    "content": msg.content or self._build_message_content(msg),
                    "content_plain": msg.content or self._build_message_content(msg),
                    "raw_json": msg.raw or {
                        "method": msg.method,
                        "gift_id": msg.gift_id,
                        "gift_name": msg.gift_name,
                        "gift_count": msg.gift_count,
                        "like_count": msg.like_count,
                        "online_count": msg.online_count,
                    },
                }
                try:
                    self.record_comment(
                        session_id=live_session.id,
                        live_room_id=room.id,
                        room_id=live_session.room_id,
                        session_no=live_session.session_no,
                        comment_payload=payload,
                    )
                    result["inserted_comments"] += 1
                except Exception:
                    continue

        return result

    def _build_message_content(self, msg) -> str:
        if msg.gift_name:
            return f"{msg.nickname or '用户'} 送出 {msg.gift_name} x{msg.gift_count or 1}"
        if msg.like_count:
            return f"{msg.nickname or '用户'} 点赞 {msg.like_count}"
        return msg.content or msg.method

    def _classify_ws_host(self, url: object) -> str:
        text = str(url or "")
        if "frontier-pc" in text:
            return "frontier-pc"
        if "frontier-im" in text:
            return "frontier-im"
        return "other"

    def _millis_to_iso(self, value: int | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
        except Exception:
            return None

    def _get_active_session(self, session, live_room_id: int) -> DouyinLiveSession | None:
        stmt = (
            select(DouyinLiveSession)
            .where(
                DouyinLiveSession.live_room_id == live_room_id,
                DouyinLiveSession.status == "live",
            )
            .order_by(DouyinLiveSession.start_time.desc())
        )
        return session.execute(stmt).scalars().first()

    def _open_session(
        self,
        session,
        room: DouyinLiveRoom,
        status,
    ) -> DouyinLiveSession:
        start_time = status.fetched_at
        session_no = f"{room.room_id}-{start_time.strftime('%Y%m%d%H%M%S')}"
        live_session = DouyinLiveSession(
            live_room_id=room.id,
            session_no=session_no,
            room_id=room.room_id,
            account_id=status.account_id or room.account_id,
            start_time=start_time,
            status="live",
            live_title=status.live_title or room.live_title,
            source_url=status.source_url or room.room_url,
            first_snapshot_time=start_time,
            last_snapshot_time=start_time,
            raw_json=self._safe_json_dumps(status),
        )
        session.add(live_session)
        session.flush()
        return live_session

    def _close_session(
        self,
        session,
        room: DouyinLiveRoom,
        live_session: DouyinLiveSession,
        end_time: datetime,
    ) -> None:
        live_session.status = "finished"
        live_session.end_time = end_time
        live_session.last_snapshot_time = end_time
        room.last_live_end_time = end_time

    def _create_snapshot(
        self,
        session,
        room: DouyinLiveRoom,
        live_session: DouyinLiveSession,
        status,
    ) -> None:
        snapshot = DouyinLiveSnapshot(
            session_id=live_session.id,
            live_room_id=room.id,
            snapshot_time=status.fetched_at,
            live_status=status.live_status,
            online_count=status.online_count,
            total_viewer_count=status.total_viewer_count,
            like_count=status.like_count,
            comment_count=status.comment_count,
            share_count=status.share_count,
            raw_json=self._safe_json_dumps(status.raw_payload),
        )
        session.add(snapshot)
        live_session.last_snapshot_time = status.fetched_at

    def record_comment(
        self,
        *,
        session_id: int,
        live_room_id: int,
        room_id: str,
        session_no: str,
        comment_payload: dict[str, object],
    ) -> DouyinLiveComment:
        payload = self.archive_service.normalize_payload(comment_payload)
        event_time = self._parse_datetime(payload.get("event_time"))
        fetch_time = self._parse_datetime(payload.get("fetch_time")) or datetime.now(timezone.utc)
        raw_file_path, raw_line_no = self.archive_service.archive_live_comment(
            room_id=room_id,
            session_no=session_no,
            payload=payload,
            event_time=event_time or fetch_time,
        )

        with get_db_session() as session:
            comment = DouyinLiveComment(
                session_id=session_id,
                live_room_id=live_room_id,
                message_id=str(payload.get("message_id") or f"{session_no}-{raw_line_no}"),
                message_type=str(payload.get("message_type") or "comment"),
                event_time=event_time or fetch_time,
                fetch_time=fetch_time,
                sequence_no=self._parse_int(payload.get("sequence_no")),
                user_id=self._string(payload.get("user_id")),
                sec_user_id=self._string(payload.get("sec_user_id")),
                nickname=self._string(payload.get("nickname")),
                display_name=self._string(payload.get("display_name")),
                avatar_url=self._string(payload.get("avatar_url")),
                gender=self._string(payload.get("gender")),
                city=self._string(payload.get("city")),
                province=self._string(payload.get("province")),
                country=self._string(payload.get("country")),
                follower_count=self._parse_int(payload.get("follower_count")),
                fan_level=self._parse_int(payload.get("fan_level")),
                user_level=self._parse_int(payload.get("user_level")),
                is_anchor=bool(payload.get("is_anchor", False)),
                is_admin=bool(payload.get("is_admin", False)),
                is_room_manager=bool(payload.get("is_room_manager", False)),
                is_fans_group_member=bool(payload.get("is_fans_group_member", False)),
                is_new_fan=bool(payload.get("is_new_fan", False)),
                content=self._string(payload.get("content")),
                content_plain=self._string(payload.get("content_plain")),
                emoji_text=self._string(payload.get("emoji_text")),
                mentioned_users=self._json_string(payload.get("mentioned_users")),
                extra_badges=self._json_string(payload.get("extra_badges")),
                device_info=self._json_string(payload.get("device_info")),
                ip_location=self._string(payload.get("ip_location")),
                risk_flags=self._json_string(payload.get("risk_flags")),
                raw_json=json.dumps(payload, ensure_ascii=False),
                raw_file_path=raw_file_path,
                raw_line_no=raw_line_no,
            )
            session.add(comment)
            session.flush()
            session.refresh(comment)
            return comment

    def ingest_comment_sample(
        self,
        *,
        session_id: int,
        comment_payload: dict[str, object],
    ) -> dict[str, int]:
        with get_db_session() as session:
            live_session = session.get(DouyinLiveSession, session_id)
            if live_session is None:
                raise ValueError(f"Live session {session_id} not found")

            room = session.get(DouyinLiveRoom, live_session.live_room_id)
            if room is None:
                raise ValueError(f"Live room {live_session.live_room_id} not found")

        comment = self.record_comment(
            session_id=live_session.id,
            live_room_id=live_session.live_room_id,
            room_id=live_session.room_id,
            session_no=live_session.session_no,
            comment_payload=comment_payload,
        )
        return {"id": comment.id, "session_id": comment.session_id}

    def _status_from_payload(self, payload: dict[str, object]):
        fetched_at = self._parse_datetime(payload.get("fetched_at")) or datetime.now(timezone.utc)
        live_status = self._string(payload.get("live_status")) or "offline"
        is_live = bool(payload.get("is_live", live_status == "live"))

        from app.collector.douyin.live.status_collector import LiveRoomStatus

        return LiveRoomStatus(
            room_id=self._required_string(payload.get("room_id"), "room_id"),
            fetched_at=fetched_at,
            live_status=live_status,
            is_live=is_live,
            account_id=self._string(payload.get("account_id")),
            nickname=self._string(payload.get("nickname")),
            live_title=self._string(payload.get("live_title")),
            source_url=self._string(payload.get("source_url")),
            online_count=self._parse_int(payload.get("online_count")),
            total_viewer_count=self._parse_int(payload.get("total_viewer_count")),
            like_count=self._parse_int(payload.get("like_count")),
            comment_count=self._parse_int(payload.get("comment_count")),
            share_count=self._parse_int(payload.get("share_count")),
            raw_payload=payload,
        )

    def _safe_json_dumps(self, value: object) -> str:
        return json.dumps(self._make_json_safe(value), ensure_ascii=False, default=str)

    def _make_json_safe(self, value: object, seen: set[int] | None = None):
        if seen is None:
            seen = set()

        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)

        obj_id = id(value)
        if obj_id in seen:
            return "[circular]"

        if isinstance(value, dict):
            seen.add(obj_id)
            result = {str(k): self._make_json_safe(v, seen) for k, v in value.items()}
            seen.remove(obj_id)
            return result

        if isinstance(value, (list, tuple, set)):
            seen.add(obj_id)
            result = [self._make_json_safe(v, seen) for v in value]
            seen.remove(obj_id)
            return result

        if hasattr(value, "isoformat") and callable(getattr(value, "isoformat")):
            try:
                return value.isoformat()
            except Exception:
                pass

        if hasattr(value, "__dict__"):
            seen.add(obj_id)
            result = {
                str(k): self._make_json_safe(v, seen)
                for k, v in vars(value).items()
                if not str(k).startswith("_")
            }
            seen.remove(obj_id)
            return result

        return str(value)

    def _parse_datetime(self, value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _parse_int(self, value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return str(value)

    def _json_string(self, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def _required_string(self, value: object, field_name: str) -> str:
        text = self._string(value)
        if not text:
            raise ValueError(f"{field_name} is required")
        return text
