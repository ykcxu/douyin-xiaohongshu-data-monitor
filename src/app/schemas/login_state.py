from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BrowserLoginStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    account_id: str
    login_type: str | None
    storage_state_path: str
    cookie_hash: str | None
    status: str
    expire_risk_level: str | None
    last_error_code: str | None
    last_error_message: str | None
    operator: str | None
    last_login_time: datetime | None
    last_valid_time: datetime | None
    created_at: datetime
    updated_at: datetime
