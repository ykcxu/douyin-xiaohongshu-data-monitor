from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class XiaohongshuNoteSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    note_pk: int
    note_id: str
    snapshot_time: datetime
    like_count: int | None
    favorite_count: int | None
    comment_count: int | None
    share_count: int | None
    view_count: int | None
    created_at: datetime
