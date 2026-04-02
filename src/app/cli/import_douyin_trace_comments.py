from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.collector.douyin.live.websocket_decoder import analyze_websocket_trace
from app.db.session import get_db_session
from app.models.douyin_live_comment import DouyinLiveComment
from app.models.douyin_live_room import DouyinLiveRoom
from app.models.douyin_live_session import DouyinLiveSession
from app.services.live_monitor_service import LiveMonitorService

ALLOWED_METHODS = {
    "WebcastChatMessage",
    "WebcastMemberMessage",
    "WebcastGiftMessage",
    "WebcastLikeMessage",
    "WebcastSocialMessage",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import decoded Douyin websocket trace messages into douyin_live_comment")
    parser.add_argument("--input", required=True, help="Trace JSONL file path")
    parser.add_argument("--session-id", required=True, type=int, help="Target douyin_live_session.id")
    parser.add_argument("--limit", type=int, default=0, help="Optional max messages to import (0 = no limit)")
    return parser


def build_content(msg: dict[str, object]) -> str:
    nickname = str(msg.get("nickname") or "用户")
    content = str(msg.get("content") or "").strip()
    gift_name = str(msg.get("gift_name") or "").strip()
    gift_count = int(msg.get("gift_count") or 0)
    like_count = int(msg.get("like_count") or 0)

    if content:
        return content
    if gift_name:
        return f"{nickname} 送出 {gift_name} x{gift_count or 1}"
    if like_count:
        return f"{nickname} 点赞 {like_count}"
    return str(msg.get("method") or "unknown")


def is_parse_failure_text(content: str | None) -> bool:
    text = (content or "").strip()
    return text.startswith("[解析失败:")


def repair_existing_comment(*, message_id: str, payload: dict[str, object]) -> bool:
    content = str(payload.get("content") or "").strip()
    nickname = payload.get("nickname")
    raw_json = payload.get("raw_json")

    with get_db_session() as session:
        existing = session.execute(
            select(DouyinLiveComment).where(DouyinLiveComment.message_id == message_id)
        ).scalar_one_or_none()
        if existing is None:
            return False

        should_repair = False
        if is_parse_failure_text(existing.content) and content and not is_parse_failure_text(content):
            existing.content = content
            existing.content_plain = str(payload.get("content_plain") or content)
            should_repair = True

        if (not existing.nickname) and nickname:
            existing.nickname = str(nickname)
            existing.display_name = str(payload.get("display_name") or nickname)
            should_repair = True

        if should_repair and raw_json and isinstance(raw_json, dict):
            existing.raw_json = json.dumps(payload, ensure_ascii=False)

        if should_repair:
            session.add(existing)
        return should_repair


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}")
        return 1

    with get_db_session() as session:
        live_session = session.get(DouyinLiveSession, args.session_id)
        if live_session is None:
            print(f"ERROR: live session not found: {args.session_id}")
            return 1
        room = session.get(DouyinLiveRoom, live_session.live_room_id)
        if room is None:
            print(f"ERROR: live room not found: {live_session.live_room_id}")
            return 1
        session_no = live_session.session_no
        room_id = live_session.room_id
        live_room_id = live_session.live_room_id

    results = analyze_websocket_trace(str(input_path))
    if "error" in results:
        print(f"ERROR: {results['error']}")
        return 1

    service = LiveMonitorService()
    inserted = 0
    duplicate = 0
    repaired = 0
    skipped = 0
    failed = 0

    messages = results.get("messages", [])
    if args.limit and args.limit > 0:
        messages = messages[: args.limit]

    for idx, msg in enumerate(messages, start=1):
        method = str(msg.get("method") or "")
        if method not in ALLOWED_METHODS:
            skipped += 1
            continue

        event_time = msg.get("timestamp")
        event_iso = None
        if isinstance(event_time, int) and event_time > 0:
            event_iso = datetime.fromtimestamp(event_time / 1000, tz=timezone.utc).isoformat()
        else:
            event_iso = str(msg.get("fetched_at") or datetime.now(timezone.utc).isoformat())

        payload = {
            "message_id": str(msg.get("msg_id") or f"{session_no}-{idx}"),
            "message_type": method.replace("Webcast", "").replace("Message", "").lower(),
            "event_time": event_iso,
            "fetch_time": str(msg.get("fetched_at") or datetime.now(timezone.utc).isoformat()),
            "sequence_no": idx,
            "user_id": str(msg.get("user_id")) if msg.get("user_id") else None,
            "nickname": msg.get("nickname"),
            "display_name": msg.get("nickname"),
            "content": build_content(msg),
            "content_plain": build_content(msg),
            "raw_json": msg,
        }

        try:
            service.record_comment(
                session_id=args.session_id,
                live_room_id=live_room_id,
                room_id=room_id,
                session_no=session_no,
                comment_payload=payload,
            )
            inserted += 1
        except IntegrityError:
            duplicate += 1
            if repair_existing_comment(message_id=str(payload["message_id"]), payload=payload):
                repaired += 1
        except Exception as exc:
            failed += 1
            print(f"WARN: failed to import message idx={idx} method={method}: {type(exc).__name__}: {exc}")

    print(
        f"IMPORT DONE: inserted={inserted} duplicate={duplicate} repaired={repaired} skipped={skipped} failed={failed} "
        f"total_decoded={len(results.get('messages', []))} total_frames={results.get('total_frames', 0)}"
    )
    return 0 if inserted > 0 or duplicate > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
