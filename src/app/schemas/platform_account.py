from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlatformAccountBase(BaseModel):
    account_no: str = Field(min_length=1, max_length=64)
    platform: str = Field(min_length=1, max_length=32)
    account_id: str = Field(min_length=1, max_length=128)
    account_handle: str | None = None
    nickname: str | None = None
    account_type: str | None = None
    is_competitor: bool = False
    department: str | None = None
    owner: str | None = None
    priority: int = 100
    status: str = "active"
    homepage_url: str | None = None
    live_room_url: str | None = None
    discover_source: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class PlatformAccountCreate(PlatformAccountBase):
    pass


class PlatformAccountUpdate(BaseModel):
    account_handle: str | None = None
    nickname: str | None = None
    account_type: str | None = None
    is_competitor: bool | None = None
    department: str | None = None
    owner: str | None = None
    priority: int | None = None
    status: str | None = None
    homepage_url: str | None = None
    live_room_url: str | None = None
    discover_source: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class PlatformAccountRead(PlatformAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
