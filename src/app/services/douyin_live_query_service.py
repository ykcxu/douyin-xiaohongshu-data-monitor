from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.douyin_live_comment import DouyinLiveComment
from app.models.douyin_live_session import DouyinLiveSession
from app.models.douyin_live_snapshot import DouyinLiveSnapshot


class DouyinLiveQueryService:
    def list_sessions(
        self,
        session: Session,
        *,
        room_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[DouyinLiveSession]:
        stmt = select(DouyinLiveSession).order_by(DouyinLiveSession.start_time.desc()).limit(limit)
        if room_id:
            stmt = stmt.where(DouyinLiveSession.room_id == room_id)
        if status:
            stmt = stmt.where(DouyinLiveSession.status == status)
        return list(session.execute(stmt).scalars().all())

    def get_session(self, session: Session, session_id: int) -> DouyinLiveSession | None:
        return session.get(DouyinLiveSession, session_id)

    def list_snapshots(
        self,
        session: Session,
        *,
        session_id: int,
        limit: int = 200,
    ) -> list[DouyinLiveSnapshot]:
        stmt = (
            select(DouyinLiveSnapshot)
            .where(DouyinLiveSnapshot.session_id == session_id)
            .order_by(DouyinLiveSnapshot.snapshot_time.desc())
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())

    def list_comments(
        self,
        session: Session,
        *,
        session_id: int,
        limit: int = 200,
        message_type: str | None = None,
    ) -> list[DouyinLiveComment]:
        stmt = (
            select(DouyinLiveComment)
            .where(DouyinLiveComment.session_id == session_id)
            .order_by(DouyinLiveComment.event_time.desc(), DouyinLiveComment.id.desc())
            .limit(limit)
        )
        if message_type:
            stmt = stmt.where(DouyinLiveComment.message_type == message_type)
        return list(session.execute(stmt).scalars().all())
