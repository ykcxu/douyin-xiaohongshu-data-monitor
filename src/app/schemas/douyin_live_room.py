from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DouyinLiveRoomBase(BaseModel):
    room_id: str = Field(min_length=1, max_length=128)
    room_handle: str | None = None
    platform_account_id: int | None = None
    account_id: str | None = None
    sec_account_id: str | None = None
    nickname: str | None = None
    live_title: str | None = None
    room_url: str | None = None
    status: str = "active"
    is_monitor_enabled: bool = True
    monitor_priority: int = 100
    tags: str | None = None
    notes: str | None = None


class DouyinLiveRoomCreate(DouyinLiveRoomBase):
    pass


class DouyinLiveRoomUpdate(BaseModel):
    room_handle: str | None = None
    platform_account_id: int | None = None
    account_id: str | None = None
    sec_account_id: str | None = None
    nickname: str | None = None
    live_title: str | None = None
    room_url: str | None = None
    status: str | None = None
    is_monitor_enabled: bool | None = None
    monitor_priority: int | None = None
    tags: str | None = None
    notes: str | None = None


class DouyinLiveRoomRead(DouyinLiveRoomBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_live_status: str | None
    last_live_start_time: datetime | None
    last_live_end_time: datetime | None
    created_at: datetime
    updated_at: datetime
