from datetime import datetime

from pydantic import BaseModel, ConfigDict


class XiaohongshuAccountSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_account_id: int | None
    account_id: str
    account_handle: str | None
    nickname: str | None
    bio: str | None
    follower_count: int | None
    following_count: int | None
    liked_count: int | None
    note_count: int | None
    snapshot_time: datetime
    created_at: datetime
