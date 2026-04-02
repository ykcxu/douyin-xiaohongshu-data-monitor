from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select

from app.collector.douyin.live.status_collector import (
    DouyinLiveStatusCollector,
    StubDouyinLiveStatusCollector,
)
from app.db.session import get_db_session
from app.models.douyin_live_room import DouyinLiveRoom
from app.models.douyin_live_session import DouyinLiveSession
from app.models.douyin_live_snapshot import DouyinLiveSnapshot


class LiveMonitorService:
    def __init__(self, collector: DouyinLiveStatusCollector | None = None) -> None:
        self.collector = collector or StubDouyinLiveStatusCollector()

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
                status = self.collector.fetch_room_status(room)
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
