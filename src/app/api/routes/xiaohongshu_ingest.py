from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.xiaohongshu_write_service import XiaohongshuWriteService

router = APIRouter(prefix="/xiaohongshu/ingest", tags=["xiaohongshu-ingest"])
write_service = XiaohongshuWriteService()


class AccountSnapshotIngestRequest(BaseModel):
    account_id: str
    platform_account_id: int | None = None
    snapshot_payload: dict[str, object]


class NoteIngestRequest(BaseModel):
    platform_account_id: int | None = None
    note_payload: dict[str, object]


class NoteSnapshotIngestRequest(BaseModel):
    note_pk: int
    note_id: str
    snapshot_payload: dict[str, object]


class NoteCommentIngestRequest(BaseModel):
    note_pk: int
    note_id: str
    comment_payload: dict[str, object]


@router.post("/account-snapshot", status_code=status.HTTP_201_CREATED)
def ingest_account_snapshot(payload: AccountSnapshotIngestRequest) -> dict[str, int]:
    record = write_service.record_account_snapshot(
        account_id=payload.account_id,
        platform_account_id=payload.platform_account_id,
        snapshot_payload=payload.snapshot_payload,
    )
    return {"id": record.id}


@router.post("/note", status_code=status.HTTP_201_CREATED)
def ingest_note(payload: NoteIngestRequest) -> dict[str, int]:
    try:
        record = write_service.upsert_note(
            platform_account_id=payload.platform_account_id,
            note_payload=payload.note_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"id": record.id}


@router.post("/note-snapshot", status_code=status.HTTP_201_CREATED)
def ingest_note_snapshot(payload: NoteSnapshotIngestRequest) -> dict[str, int]:
    record = write_service.record_note_snapshot(
        note_pk=payload.note_pk,
        note_id=payload.note_id,
        snapshot_payload=payload.snapshot_payload,
    )
    return {"id": record.id}


@router.post("/note-comment", status_code=status.HTTP_201_CREATED)
def ingest_note_comment(payload: NoteCommentIngestRequest) -> dict[str, int]:
    try:
        record = write_service.upsert_note_comment(
            note_pk=payload.note_pk,
            note_id=payload.note_id,
            comment_payload=payload.comment_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"id": record.id}
