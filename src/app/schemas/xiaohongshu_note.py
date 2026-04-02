from datetime import datetime

from pydantic import BaseModel, ConfigDict


class XiaohongshuNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_account_id: int | None
    note_id: str
    account_id: str | None
    note_title: str | None
    note_summary: str | None
    note_url: str | None
    note_type: str | None
    publish_time: datetime | None
    status: str
    topics: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
