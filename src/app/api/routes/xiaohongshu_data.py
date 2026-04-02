from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session_dependency
from app.schemas.xiaohongshu_account_snapshot import XiaohongshuAccountSnapshotRead
from app.schemas.xiaohongshu_note import XiaohongshuNoteRead
from app.schemas.xiaohongshu_note_comment import XiaohongshuNoteCommentRead
from app.schemas.xiaohongshu_note_snapshot import XiaohongshuNoteSnapshotRead
from app.services.xiaohongshu_query_service import XiaohongshuQueryService

router = APIRouter(prefix="/xiaohongshu", tags=["xiaohongshu-data"])
query_service = XiaohongshuQueryService()


@router.get("/accounts/snapshots", response_model=list[XiaohongshuAccountSnapshotRead])
def list_account_snapshots(
    session: Annotated[Session, Depends(db_session_dependency)],
    account_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[XiaohongshuAccountSnapshotRead]:
    return query_service.list_account_snapshots(session, account_id=account_id, limit=limit)


@router.get("/notes", response_model=list[XiaohongshuNoteRead])
def list_notes(
    session: Annotated[Session, Depends(db_session_dependency)],
    account_id: Annotated[str | None, Query()] = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[XiaohongshuNoteRead]:
    return query_service.list_notes(session, account_id=account_id, status=status_value, limit=limit)


@router.get("/notes/{note_pk}", response_model=XiaohongshuNoteRead)
def get_note(
    note_pk: int,
    session: Annotated[Session, Depends(db_session_dependency)],
) -> XiaohongshuNoteRead:
    note = query_service.get_note(session, note_pk)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.get("/notes/{note_pk}/snapshots", response_model=list[XiaohongshuNoteSnapshotRead])
def list_note_snapshots(
    note_pk: int,
    session: Annotated[Session, Depends(db_session_dependency)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[XiaohongshuNoteSnapshotRead]:
    return query_service.list_note_snapshots(session, note_pk=note_pk, limit=limit)


@router.get("/notes/{note_pk}/comments", response_model=list[XiaohongshuNoteCommentRead])
def list_note_comments(
    note_pk: int,
    session: Annotated[Session, Depends(db_session_dependency)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[XiaohongshuNoteCommentRead]:
    return query_service.list_note_comments(session, note_pk=note_pk, limit=limit)
