from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.collector.douyin.live.providers import HttpDouyinLiveStatusCollector
from app.config.settings import get_settings
from app.models.douyin_live_room import DouyinLiveRoom


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe a Douyin live room with known room-level debug requests.",
    )
    parser.add_argument("--room-id", required=True, help="Douyin room id or web_rid.")
    parser.add_argument("--account-id", required=True, help="Internal account id bound to the login state.")
    parser.add_argument("--room-url", default=None, help="Optional full room URL override.")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()

    room = DouyinLiveRoom(
        room_id=args.room_id,
        room_url=args.room_url or f"https://live.douyin.com/{args.room_id}",
        account_id=args.account_id,
    )
    collector = HttpDouyinLiveStatusCollector()
    payload = collector.build_debug_bundle(room)

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = (
            settings.raw_data_dir / "douyin" / "probe" / f"{args.account_id}-{args.room_id}-{timestamp}.json"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved probe result: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
