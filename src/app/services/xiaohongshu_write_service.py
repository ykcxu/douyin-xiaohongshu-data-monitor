from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import get_db_session
from app.models.xiaohongshu_account_snapshot import XiaohongshuAccountSnapshot
from app.models.xiaohongshu_note import XiaohongshuNote
from app.models.xiaohongshu_note_comment import XiaohongshuNoteComment
from app.models.xiaohongshu_note_snapshot import XiaohongshuNoteSnapshot


class XiaohongshuWriteService:
    def record_account_snapshot(
        self,
        *,
        account_id: str,
        snapshot_payload: dict[str, object],
        platform_account_id: int | None = None,
    ) -> XiaohongshuAccountSnapshot:
        snapshot_time = self._parse_datetime(snapshot_payload.get("snapshot_time")) or datetime.now(timezone.utc)

        with get_db_session() as session:
            snapshot = XiaohongshuAccountSnapshot(
                platform_account_id=platform_account_id,
                account_id=account_id,
                account_handle=self._string(snapshot_payload.get("account_handle")),
                nickname=self._string(snapshot_payload.get("nickname")),
                bio=self._string(snapshot_payload.get("bio")),
                follower_count=self._parse_int(snapshot_payload.get("follower_count")),
                following_count=self._parse_int(snapshot_payload.get("following_count")),
                liked_count=self._parse_int(snapshot_payload.get("liked_count")),
                note_count=self._parse_int(snapshot_payload.get("note_count")),
                snapshot_time=snapshot_time,
                raw_json=json.dumps(snapshot_payload, ensure_ascii=False),
            )
            session.add(snapshot)
            session.flush()
            session.refresh(snapshot)
            return snapshot

    def upsert_note(
        self,
        *,
        note_payload: dict[str, object],
        platform_account_id: int | None = None,
    ) -> XiaohongshuNote:
        note_id = self._required_string(note_payload.get("note_id"), "note_id")
        publish_time = self._parse_datetime(note_payload.get("publish_time"))
        now = datetime.now(timezone.utc)

        with get_db_session() as session:
            stmt = select(XiaohongshuNote).where(XiaohongshuNote.note_id == note_id)
            note = session.execute(stmt).scalar_one_or_none()

            if note is None:
                note = XiaohongshuNote(
                    platform_account_id=platform_account_id,
                    note_id=note_id,
                    first_seen_at=now,
                )
                session.add(note)

            note.platform_account_id = platform_account_id or note.platform_account_id
            note.account_id = self._string(note_payload.get("account_id"))
            note.note_title = self._string(note_payload.get("note_title"))
            note.note_summary = self._string(note_payload.get("note_summary"))
            note.note_url = self._string(note_payload.get("note_url"))
            note.note_type = self._string(note_payload.get("note_type"))
            note.publish_time = publish_time
            note.status = self._string(note_payload.get("status")) or "active"
            note.topics = self._json_string(note_payload.get("topics"))
            note.raw_json = json.dumps(note_payload, ensure_ascii=False)
            note.last_seen_at = now

            session.flush()
            session.refresh(note)
            return note

    def record_note_snapshot(
        self,
        *,
        note_pk: int,
        note_id: str,
        snapshot_payload: dict[str, object],
    ) -> XiaohongshuNoteSnapshot:
        snapshot_time = self._parse_datetime(snapshot_payload.get("snapshot_time")) or datetime.now(timezone.utc)

        with get_db_session() as session:
            snapshot = XiaohongshuNoteSnapshot(
                note_pk=note_pk,
                note_id=note_id,
                snapshot_time=snapshot_time,
                like_count=self._parse_int(snapshot_payload.get("like_count")),
                favorite_count=self._parse_int(snapshot_payload.get("favorite_count")),
                comment_count=self._parse_int(snapshot_payload.get("comment_count")),
                share_count=self._parse_int(snapshot_payload.get("share_count")),
                view_count=self._parse_int(snapshot_payload.get("view_count")),
                raw_json=json.dumps(snapshot_payload, ensure_ascii=False),
            )
            session.add(snapshot)
            session.flush()
            session.refresh(snapshot)
            return snapshot

    def upsert_note_comment(
        self,
        *,
        note_pk: int,
        note_id: str,
        comment_payload: dict[str, object],
    ) -> XiaohongshuNoteComment:
        comment_id = self._required_string(comment_payload.get("comment_id"), "comment_id")
        comment_time = self._parse_datetime(comment_payload.get("comment_time"))

        with get_db_session() as session:
            stmt = select(XiaohongshuNoteComment).where(XiaohongshuNoteComment.comment_id == comment_id)
            comment = session.execute(stmt).scalar_one_or_none()

            if comment is None:
                comment = XiaohongshuNoteComment(
                    note_pk=note_pk,
                    note_id=note_id,
                    comment_id=comment_id,
                )
                session.add(comment)

            comment.note_pk = note_pk
            comment.note_id = note_id
            comment.parent_comment_id = self._string(comment_payload.get("parent_comment_id"))
            comment.comment_level = self._parse_int(comment_payload.get("comment_level"))
            comment.user_id = self._string(comment_payload.get("user_id"))
            comment.nickname = self._string(comment_payload.get("nickname"))
            comment.content = self._string(comment_payload.get("content"))
            comment.like_count = self._parse_int(comment_payload.get("like_count"))
            comment.comment_time = comment_time
            comment.status = self._string(comment_payload.get("status")) or "visible"
            comment.raw_json = json.dumps(comment_payload, ensure_ascii=False)

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

    def _required_string(self, value: object, field_name: str) -> str:
        text = self._string(value)
        if not text:
            raise ValueError(f"{field_name} is required")
        return text
