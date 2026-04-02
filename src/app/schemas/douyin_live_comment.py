from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DouyinLiveCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    live_room_id: int
    message_id: str
    message_type: str
    event_time: datetime
    fetch_time: datetime
    sequence_no: int | None
    user_id: str | None
    sec_user_id: str | None
    nickname: str | None
    display_name: str | None
    avatar_url: str | None
    gender: str | None
    city: str | None
    province: str | None
    country: str | None
    follower_count: int | None
    fan_level: int | None
    user_level: int | None
    is_anchor: bool
    is_admin: bool
    is_room_manager: bool
    is_fans_group_member: bool
    is_new_fan: bool
    content: str | None
    content_plain: str | None
    emoji_text: str | None
    mentioned_users: str | None
    extra_badges: str | None
    device_info: str | None
    ip_location: str | None
    risk_flags: str | None
    raw_file_path: str | None
    raw_line_no: int | None
    created_at: datetime
