from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select

from app.collector.douyin.live.exceptions import DouyinProviderError
from app.collector.douyin.live.status_collector import (
    DouyinLiveStatusCollector,
    StubDouyinLiveStatusCollector,
)
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

    def scan_rooms_once(self) -> dict[str, int]:
        scanned = 0
        live_count = 0

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
                    room.last_live_start_time = status.fetched_at
                    self._create_snapshot(session, room, active_session, status)
                elif active_session is not None:
                    self._close_session(session, room, active_session, status.fetched_at)

                room.updated_at = datetime.now(timezone.utc)

        return {"scanned": scanned, "live_count": live_count}

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
            raw_json=json.dumps(asdict(status), ensure_ascii=False),
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
            raw_json=json.dumps(status.raw_payload, ensure_ascii=False),
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
