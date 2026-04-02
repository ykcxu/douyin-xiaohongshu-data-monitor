from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class XiaohongshuNoteCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    note_pk: int
    note_id: str
    comment_id: str
    parent_comment_id: str | None
    comment_level: int | None
    user_id: str | None
    nickname: str | None
    content: str | None
    like_count: int | None
    comment_time: datetime | None
    status: str
    created_at: datetime
