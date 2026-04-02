from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DouyinLiveSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    live_room_id: int
    snapshot_time: datetime
    live_status: str
    online_count: int | None
    total_viewer_count: int | None
    new_viewer_count: int | None
    like_count: int | None
    new_like_count: int | None
    comment_count: int | None
    new_comment_count: int | None
    share_count: int | None
    gift_count: int | None
    gift_amount: int | None
    created_at: datetime
