from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import and_, desc, func, or_, select

from app.config.settings import get_settings
from app.db.session import get_db_session
from app.models.douyin_live_comment import DouyinLiveComment
from app.models.douyin_live_room import DouyinLiveRoom
from app.models.douyin_live_session import DouyinLiveSession
from app.models.douyin_live_snapshot import DouyinLiveSnapshot

TZ = ZoneInfo("Asia/Shanghai")


@dataclass
class ReportWindow:
    kind: str
    label: str
    start: datetime
    end: datetime
    slug: str


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _to_dt(value: date, end_of_day: bool = False) -> datetime:
    base = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(value, base, TZ)


def _daily_window(run_day: date) -> ReportWindow:
    target = run_day - timedelta(days=1)
    start = _to_dt(target)
    end = _to_dt(run_day)
    return ReportWindow(
        kind="daily",
        label=f"日报（{_fmt_date(target)}）",
        start=start,
        end=end,
        slug=target.strftime("daily-%Y-%m-%d"),
    )


def _weekly_window(run_day: date) -> ReportWindow:
    current_week_monday = run_day - timedelta(days=run_day.weekday())
    target_start = current_week_monday - timedelta(days=7)
    target_end = current_week_monday
    return ReportWindow(
        kind="weekly",
        label=f"周报（{_fmt_date(target_start)} ~ {_fmt_date(target_end - timedelta(days=1))}）",
        start=_to_dt(target_start),
        end=_to_dt(target_end),
        slug=f"weekly-{target_start.strftime('%Y-%m-%d')}_to_{(target_end - timedelta(days=1)).strftime('%Y-%m-%d')}",
    )


def _monthly_window(run_day: date) -> ReportWindow:
    first_of_this_month = run_day.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    return ReportWindow(
        kind="monthly",
        label=f"月报（{first_of_prev_month.strftime('%Y-%m')}）",
        start=_to_dt(first_of_prev_month),
        end=_to_dt(first_of_this_month),
        slug=f"monthly-{first_of_prev_month.strftime('%Y-%m')}",
    )


def determine_windows(run_day: date) -> list[ReportWindow]:
    windows = [_daily_window(run_day)]
    # 约定：每周一做上周周报；如果还是当月第一个周一，再补做上月月报。
    if run_day.weekday() == 0:
        windows.append(_weekly_window(run_day))
        if run_day.day <= 7:
            windows.append(_monthly_window(run_day))
    return windows


def _safe_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _load_room_meta_map(session_ids: Iterable[int]) -> dict[int, dict[str, object]]:
    session_ids = list(session_ids)
    if not session_ids:
        return {}

    with get_db_session() as s:
        rows = s.execute(
            select(
                DouyinLiveSession.id,
                DouyinLiveSession.room_id,
                DouyinLiveSession.live_title,
                DouyinLiveSession.start_time,
                DouyinLiveRoom.nickname,
                DouyinLiveRoom.room_url,
            )
            .join(DouyinLiveRoom, DouyinLiveRoom.id == DouyinLiveSession.live_room_id)
            .where(DouyinLiveSession.id.in_(session_ids))
        ).all()

    result: dict[int, dict[str, object]] = {}
    for row in rows:
        result[int(row.id)] = {
            "room_id": row.room_id,
            "title": row.live_title or "",
            "nickname": row.nickname or "",
            "room_url": row.room_url or "",
            "start_time": row.start_time,
        }
    return result


def build_report(window: ReportWindow) -> dict[str, object]:
    with get_db_session() as s:
        snapshot_rows = s.execute(
            select(
                DouyinLiveSnapshot.session_id,
                DouyinLiveSnapshot.live_room_id,
                DouyinLiveSnapshot.snapshot_time,
                DouyinLiveSnapshot.online_count,
                DouyinLiveSnapshot.total_viewer_count,
                DouyinLiveSnapshot.like_count,
                DouyinLiveSnapshot.comment_count,
                DouyinLiveSnapshot.share_count,
                DouyinLiveSnapshot.gift_count,
                DouyinLiveSnapshot.gift_amount,
            )
            .where(
                and_(
                    DouyinLiveSnapshot.snapshot_time >= window.start,
                    DouyinLiveSnapshot.snapshot_time < window.end,
                )
            )
            .order_by(DouyinLiveSnapshot.snapshot_time.asc())
        ).all()

        comment_rows = s.execute(
            select(
                DouyinLiveComment.session_id,
                DouyinLiveComment.live_room_id,
                DouyinLiveComment.fetch_time,
                DouyinLiveComment.message_type,
                DouyinLiveComment.nickname,
                DouyinLiveComment.content,
            )
            .where(
                and_(
                    DouyinLiveComment.fetch_time >= window.start,
                    DouyinLiveComment.fetch_time < window.end,
                )
            )
            .order_by(DouyinLiveComment.fetch_time.asc())
        ).all()

    session_ids = sorted({int(r.session_id) for r in snapshot_rows} | {int(r.session_id) for r in comment_rows})
    room_meta = _load_room_meta_map(session_ids)

    room_rollups: dict[int, dict[str, object]] = {}
    type_counter: Counter[str] = Counter()
    for row in snapshot_rows:
        item = room_rollups.setdefault(
            int(row.session_id),
            {
                "session_id": int(row.session_id),
                "live_room_id": int(row.live_room_id),
                "snapshot_count": 0,
                "comment_total": 0,
                "type_counts": Counter(),
                "latest_comments": [],
                "peak_online_count": None,
                "latest_online_count": None,
                "max_like_count": None,
                "max_comment_count_snapshot": None,
                "max_share_count": None,
                "max_gift_count": None,
                "max_gift_amount": None,
                "latest_snapshot_time": None,
            },
        )
        item["snapshot_count"] = int(item["snapshot_count"]) + 1
        online_count = _safe_int(row.online_count)
        like_count = _safe_int(row.like_count)
        comment_count = _safe_int(row.comment_count)
        share_count = _safe_int(row.share_count)
        gift_count = _safe_int(row.gift_count)
        gift_amount = _safe_int(row.gift_amount)
        item["latest_snapshot_time"] = row.snapshot_time
        item["latest_online_count"] = online_count
        if online_count is not None:
            prev = item["peak_online_count"]
            item["peak_online_count"] = online_count if prev is None else max(int(prev), online_count)
        if like_count is not None:
            prev = item["max_like_count"]
            item["max_like_count"] = like_count if prev is None else max(int(prev), like_count)
        if comment_count is not None:
            prev = item["max_comment_count_snapshot"]
            item["max_comment_count_snapshot"] = comment_count if prev is None else max(int(prev), comment_count)
        if share_count is not None:
            prev = item["max_share_count"]
            item["max_share_count"] = share_count if prev is None else max(int(prev), share_count)
        if gift_count is not None:
            prev = item["max_gift_count"]
            item["max_gift_count"] = gift_count if prev is None else max(int(prev), gift_count)
        if gift_amount is not None:
            prev = item["max_gift_amount"]
            item["max_gift_amount"] = gift_amount if prev is None else max(int(prev), gift_amount)

    for row in comment_rows:
        item = room_rollups.setdefault(
            int(row.session_id),
            {
                "session_id": int(row.session_id),
                "live_room_id": int(row.live_room_id),
                "snapshot_count": 0,
                "comment_total": 0,
                "type_counts": Counter(),
                "latest_comments": [],
                "peak_online_count": None,
                "latest_online_count": None,
                "max_like_count": None,
                "max_comment_count_snapshot": None,
                "max_share_count": None,
                "max_gift_count": None,
                "max_gift_amount": None,
                "latest_snapshot_time": None,
            },
        )
        item["comment_total"] = int(item["comment_total"]) + 1
        msg_type = str(row.message_type or "unknown")
        item["type_counts"][msg_type] += 1
        type_counter[msg_type] += 1
        latest_comments = item["latest_comments"]
        latest_comments.append(
            {
                "fetch_time": row.fetch_time,
                "type": msg_type,
                "nickname": row.nickname or "",
                "content": row.content or "",
            }
        )
        if len(latest_comments) > 5:
            del latest_comments[:-5]

    rows_for_output: list[dict[str, object]] = []
    for session_id, item in room_rollups.items():
        meta = room_meta.get(session_id, {})
        rows_for_output.append(
            {
                "session_id": session_id,
                "room_id": meta.get("room_id") or "",
                "title": meta.get("title") or "",
                "nickname": meta.get("nickname") or "",
                "room_url": meta.get("room_url") or "",
                "start_time": meta.get("start_time"),
                **item,
                "type_counts": dict(item["type_counts"]),
            }
        )

    rows_for_output.sort(
        key=lambda x: (
            int(x.get("comment_total") or 0),
            int(x.get("peak_online_count") or 0),
            int(x.get("snapshot_count") or 0),
        ),
        reverse=True,
    )

    overview = {
        "kind": window.kind,
        "label": window.label,
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "rooms": len({int(r["live_room_id"]) for r in rows_for_output if r.get("live_room_id") is not None}),
        "sessions": len(rows_for_output),
        "snapshots": len(snapshot_rows),
        "comments": len(comment_rows),
        "comment_type_counts": dict(type_counter),
    }

    return {
        "overview": overview,
        "rooms": rows_for_output,
    }


def render_markdown(report: dict[str, object]) -> str:
    overview = report["overview"]
    rooms = report["rooms"]

    lines: list[str] = []
    lines.append(f"# {overview['label']}")
    lines.append("")
    lines.append(f"- 时间范围：{_fmt_dt(datetime.fromisoformat(str(overview['start'])))} ~ {_fmt_dt(datetime.fromisoformat(str(overview['end'])))}")
    lines.append(f"- 活跃直播间数：{overview['rooms']}")
    lines.append(f"- 活跃场次数：{overview['sessions']}")
    lines.append(f"- 快照条数：{overview['snapshots']}")
    lines.append(f"- 弹幕/互动条数：{overview['comments']}")
    lines.append(f"- 类型分布：{json.dumps(overview['comment_type_counts'], ensure_ascii=False)}")
    lines.append("")
    lines.append("## 重点直播间")
    lines.append("")

    if not rooms:
        lines.append("本周期没有采集到可用数据。")
        return "\n".join(lines)

    for idx, room in enumerate(rooms[:10], start=1):
        lines.append(f"### {idx}. {room.get('title') or room.get('nickname') or room.get('room_id')}")
        lines.append(f"- 房间号：{room.get('room_id') or '-'}")
        if room.get('nickname'):
            lines.append(f"- 主播/房间昵称：{room.get('nickname')}")
        lines.append(f"- 场次 ID：{room.get('session_id')}")
        lines.append(f"- 开播时间：{_fmt_dt(room.get('start_time'))}")
        lines.append(f"- 快照数：{room.get('snapshot_count')}")
        lines.append(f"- 峰值在线人数：{room.get('peak_online_count') if room.get('peak_online_count') is not None else '-'}")
        lines.append(f"- 最近在线人数：{room.get('latest_online_count') if room.get('latest_online_count') is not None else '-'}")
        lines.append(f"- 最高点赞数：{room.get('max_like_count') if room.get('max_like_count') is not None else '-'}")
        lines.append(f"- 弹幕/互动总数：{room.get('comment_total')}")
        lines.append(f"- 类型分布：{json.dumps(room.get('type_counts') or {}, ensure_ascii=False)}")
        lines.append(f"- 最近快照时间：{_fmt_dt(room.get('latest_snapshot_time'))}")
        if room.get('room_url'):
            lines.append(f"- 房间链接：{room.get('room_url')}")
        latest_comments = room.get('latest_comments') or []
        if latest_comments:
            lines.append("- 最近互动样本：")
            for sample in latest_comments[-3:]:
                lines.append(
                    f"  - [{_fmt_dt(sample.get('fetch_time'))}] {sample.get('type')} | {sample.get('nickname') or '-'} | {(sample.get('content') or '').strip()}"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def save_reports(run_day: date, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[dict[str, object]] = []

    for window in determine_windows(run_day):
        report = build_report(window)
        markdown = render_markdown(report)
        json_path = output_dir / f"{window.slug}.json"
        md_path = output_dir / f"{window.slug}.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        generated.append(
            {
                "kind": window.kind,
                "label": window.label,
                "json_path": str(json_path),
                "markdown_path": str(md_path),
            }
        )

    manifest = {
        "generated_at": datetime.now(TZ).isoformat(),
        "run_day": run_day.isoformat(),
        "reports": generated,
    }
    (output_dir / "latest_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    import argparse

    settings = get_settings()
    parser = argparse.ArgumentParser(description="Generate scheduled daily/weekly/monthly reports.")
    parser.add_argument("--run-date", help="Run date in Asia/Shanghai, default=today.")
    parser.add_argument(
        "--output-dir",
        default=str(settings.app_root / "runtime" / "reports"),
        help="Directory to write report files.",
    )
    args = parser.parse_args()

    run_day = datetime.now(TZ).date()
    if args.run_date:
        run_day = date.fromisoformat(args.run_date)

    manifest = save_reports(run_day=run_day, output_dir=Path(args.output_dir))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
