from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config.settings import get_settings


class JsonlArchiveService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def archive_live_comment(
        self,
        *,
        room_id: str,
        session_no: str,
        payload: dict[str, Any],
        event_time: datetime,
    ) -> tuple[str, int]:
        file_path = self._comment_file_path(room_id=room_id, session_no=session_no, event_time=event_time)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        line_count = 1
        if file_path.exists():
            with file_path.open("r", encoding="utf-8") as existing:
                line_count = sum(1 for _ in existing) + 1

        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

        return str(file_path), line_count

    def normalize_payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        if is_dataclass(payload):
            return asdict(payload)
        return {"value": str(payload)}

    def _comment_file_path(self, *, room_id: str, session_no: str, event_time: datetime) -> Path:
        date_key = event_time.strftime("%Y-%m-%d")
        return (
            self.settings.raw_data_dir
            / "douyin"
            / "live_comments"
            / date_key
            / room_id
            / f"{session_no}.jsonl"
        )
