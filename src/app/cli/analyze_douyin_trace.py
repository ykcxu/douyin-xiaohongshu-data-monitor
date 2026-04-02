from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize a Douyin request trace JSONL file.")
    parser.add_argument("--input", required=True, help="Path to the request trace JSONL file.")
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="How many top XHR/fetch paths to print. Defaults to 20.",
    )
    return parser


def load_rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"Missing input file: {path}")
        return 1

    rows = load_rows(path)
    event_counts = Counter(str(row.get("event")) for row in rows)
    resource_counts = Counter(
        str(row.get("resource_type"))
        for row in rows
        if row.get("resource_type")
    )

    print("== Event Counts ==")
    for key, value in event_counts.most_common():
        print(f"{key}: {value}")

    print("\n== Resource Counts ==")
    for key, value in resource_counts.most_common():
        print(f"{key}: {value}")

    xhr_rows = [
        row
        for row in rows
        if row.get("event") == "request" and row.get("resource_type") in {"xhr", "fetch"}
    ]
    path_counts = Counter(urlparse(str(row.get("url", ""))).path for row in xhr_rows)

    print("\n== Top XHR/Fetch Paths ==")
    for endpoint, count in path_counts.most_common(args.top):
        print(f"{count:>4}  {endpoint}")

    websocket_urls = []
    for row in rows:
        if row.get("event") in {"websocket", "cdp_websocket_created"}:
            url = str(row.get("url", ""))
            if url and url not in websocket_urls:
                websocket_urls.append(url)

    print("\n== WebSocket URLs ==")
    for url in websocket_urls:
        print(url)

    frame_rows = [
        row
        for row in rows
        if row.get("event") in {"cdp_websocket_frame_received", "cdp_websocket_frame_sent"}
    ]
    print(f"\n== WebSocket Frames ==\ncount: {len(frame_rows)}")
    for row in frame_rows[:10]:
        payload_preview = str(row.get("payload_preview", ""))
        print(f"{row.get('event')}: {payload_preview[:160]}")

    interesting_keywords = ("webcast", "room", "comment", "im", "danmaku", "frontier")
    print("\n== Interesting Requests ==")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        url = str(row.get("url", ""))
        if not url or not any(keyword in url for keyword in interesting_keywords):
            continue
        event = str(row.get("event", ""))
        key = (event, url)
        if key in seen:
            continue
        seen.add(key)
        print(f"{event}: {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
