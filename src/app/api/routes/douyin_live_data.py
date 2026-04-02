from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session_dependency
from app.schemas.douyin_live_comment import DouyinLiveCommentRead
from app.schemas.douyin_live_session import DouyinLiveSessionRead
from app.schemas.douyin_live_snapshot import DouyinLiveSnapshotRead
from app.services.douyin_live_query_service import DouyinLiveQueryService

router = APIRouter(prefix="/douyin/live", tags=["douyin-live-data"])
query_service = DouyinLiveQueryService()


@router.get("/sessions", response_model=list[DouyinLiveSessionRead])
def list_sessions(
    session: Annotated[Session, Depends(db_session_dependency)],
    room_id: Annotated[str | None, Query()] = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[DouyinLiveSessionRead]:
    return query_service.list_sessions(session, room_id=room_id, status=status_value, limit=limit)


@router.get("/sessions/{session_id}", response_model=DouyinLiveSessionRead)
def get_session(
    session_id: int,
    session: Annotated[Session, Depends(db_session_dependency)],
) -> DouyinLiveSessionRead:
    record = query_service.get_session(session, session_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return record


@router.get("/sessions/{session_id}/snapshots", response_model=list[DouyinLiveSnapshotRead])
def list_snapshots(
    session_id: int,
    session: Annotated[Session, Depends(db_session_dependency)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[DouyinLiveSnapshotRead]:
    return query_service.list_snapshots(session, session_id=session_id, limit=limit)


@router.get("/sessions/{session_id}/comments", response_model=list[DouyinLiveCommentRead])
def list_comments(
    session_id: int,
    session: Annotated[Session, Depends(db_session_dependency)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    message_type: Annotated[str | None, Query()] = None,
) -> list[DouyinLiveCommentRead]:
    return query_service.list_comments(
        session,
        session_id=session_id,
        limit=limit,
        message_type=message_type,
    )
