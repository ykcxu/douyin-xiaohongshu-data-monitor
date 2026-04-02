from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DouyinLiveSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    live_room_id: int
    session_no: str
    room_id: str
    account_id: str | None
    start_time: datetime
    end_time: datetime | None
    status: str
    live_title: str | None
    source_url: str | None
    end_reason: str | None
    first_snapshot_time: datetime | None
    last_snapshot_time: datetime | None
    created_at: datetime
    updated_at: datetime
