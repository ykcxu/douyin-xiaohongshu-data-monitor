from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.live_monitor_service import LiveMonitorService

router = APIRouter(prefix="/douyin/ingest", tags=["douyin-ingest"])
live_monitor_service = LiveMonitorService()


class DouyinStatusSampleIngestRequest(BaseModel):
    room_pk: int
    status_payload: dict[str, object]


class DouyinCommentSampleIngestRequest(BaseModel):
    session_id: int
    comment_payload: dict[str, object]


@router.post("/status-sample", status_code=status.HTTP_201_CREATED)
def ingest_status_sample(payload: DouyinStatusSampleIngestRequest) -> dict[str, int | str]:
    try:
        result = live_monitor_service.ingest_status_sample(
            room_pk=payload.room_pk,
            status_payload=payload.status_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return result


@router.post("/comment-sample", status_code=status.HTTP_201_CREATED)
def ingest_comment_sample(payload: DouyinCommentSampleIngestRequest) -> dict[str, int]:
    try:
        result = live_monitor_service.ingest_comment_sample(
            session_id=payload.session_id,
            comment_payload=payload.comment_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return result
