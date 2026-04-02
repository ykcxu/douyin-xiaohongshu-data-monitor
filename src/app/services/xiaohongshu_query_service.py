from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.xiaohongshu_account_snapshot import XiaohongshuAccountSnapshot
from app.models.xiaohongshu_note import XiaohongshuNote
from app.models.xiaohongshu_note_comment import XiaohongshuNoteComment
from app.models.xiaohongshu_note_snapshot import XiaohongshuNoteSnapshot


class XiaohongshuQueryService:
    def list_account_snapshots(
        self,
        session: Session,
        *,
        account_id: str | None = None,
        limit: int = 100,
    ) -> list[XiaohongshuAccountSnapshot]:
        stmt = (
            select(XiaohongshuAccountSnapshot)
            .order_by(XiaohongshuAccountSnapshot.snapshot_time.desc())
            .limit(limit)
        )
        if account_id:
            stmt = stmt.where(XiaohongshuAccountSnapshot.account_id == account_id)
        return list(session.execute(stmt).scalars().all())

    def list_notes(
        self,
        session: Session,
        *,
        account_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[XiaohongshuNote]:
        stmt = select(XiaohongshuNote).order_by(XiaohongshuNote.publish_time.desc(), XiaohongshuNote.id.desc()).limit(limit)
        if account_id:
            stmt = stmt.where(XiaohongshuNote.account_id == account_id)
        if status:
            stmt = stmt.where(XiaohongshuNote.status == status)
        return list(session.execute(stmt).scalars().all())

    def get_note(self, session: Session, note_pk: int) -> XiaohongshuNote | None:
        return session.get(XiaohongshuNote, note_pk)

    def list_note_snapshots(
        self,
        session: Session,
        *,
        note_pk: int,
        limit: int = 200,
    ) -> list[XiaohongshuNoteSnapshot]:
        stmt = (
            select(XiaohongshuNoteSnapshot)
            .where(XiaohongshuNoteSnapshot.note_pk == note_pk)
            .order_by(XiaohongshuNoteSnapshot.snapshot_time.desc())
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())

    def list_note_comments(
        self,
        session: Session,
        *,
        note_pk: int,
        limit: int = 200,
    ) -> list[XiaohongshuNoteComment]:
        stmt = (
            select(XiaohongshuNoteComment)
            .where(XiaohongshuNoteComment.note_pk == note_pk)
            .order_by(XiaohongshuNoteComment.comment_time.desc(), XiaohongshuNoteComment.id.desc())
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())
