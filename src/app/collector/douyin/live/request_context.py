from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DouyinLiveRequestContext:
    account_id: str | None
    storage_state_path: Path | None
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.storage_state_path and self.storage_state_path.exists())


def load_storage_state_cookies(storage_state_path: Path | None) -> dict[str, str]:
    if storage_state_path is None or not storage_state_path.exists():
        return {}

    payload = json.loads(storage_state_path.read_text(encoding="utf-8"))
    cookies = payload.get("cookies", [])
    result: dict[str, str] = {}
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value:
            result[str(name)] = str(value)
    return result
