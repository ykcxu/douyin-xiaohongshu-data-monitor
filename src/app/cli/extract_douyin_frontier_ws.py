from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract and summarize Douyin frontier WebSocket handshake information from a request trace JSONL file.",
    )
    parser.add_argument("--input", required=True, help="Path to a Douyin request trace JSONL file.")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    return parser


def load_rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def first_value(parsed_query: dict[str, list[str]], key: str) -> str | None:
    values = parsed_query.get(key)
    if not values:
        return None
    return values[0]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Missing input file: {input_path}")
        return 1

    rows = load_rows(input_path)
    websocket_rows = [
        row
        for row in rows
        if str(row.get("event")) in {"websocket", "cdp_websocket_created"}
        and str(row.get("url", "")).startswith("wss://frontier")
    ]
    frame_rows = [
        row
        for row in rows
        if str(row.get("event")) in {"cdp_websocket_frame_received", "cdp_websocket_frame_sent"}
    ]

    url_entries: list[dict[str, object]] = []
    grouped_by_host: dict[str, list[dict[str, object]]] = defaultdict(list)
    grouped_by_request_id: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen_urls: set[str] = set()

    for row in websocket_rows:
        url = str(row.get("url", ""))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        entry = {
            "event": row.get("event"),
            "ts": row.get("ts"),
            "request_id": row.get("request_id"),
            "host": parsed.netloc,
            "path": parsed.path,
            "url": url,
            "query": {key: values[0] if len(values) == 1 else values for key, values in sorted(query.items())},
            "summary": {
                "aid": first_value(query, "aid"),
                "device_platform": first_value(query, "device_platform"),
                "device_id": first_value(query, "device_id"),
                "access_key": first_value(query, "access_key"),
                "fpid": first_value(query, "fpid"),
                "conn_tag": first_value(query, "conn_tag"),
                "qos_sdk_version": first_value(query, "qos_sdk_version"),
                "version_code": first_value(query, "version_code"),
            },
        }
        url_entries.append(entry)
        grouped_by_host[parsed.netloc].append(entry)
        request_id = str(row.get("request_id", "")).strip()
        if request_id:
            grouped_by_request_id[request_id].append(entry)

    frame_counts = Counter(str(row.get("event")) for row in frame_rows)
    frame_preview_by_request_id: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in frame_rows:
        request_id = str(row.get("request_id", "")).strip()
        if not request_id:
            continue
        if len(frame_preview_by_request_id[request_id]) >= 5:
            continue
        frame_preview_by_request_id[request_id].append(
            {
                "event": row.get("event"),
                "opcode": row.get("opcode"),
                "payload_preview": str(row.get("payload_preview", ""))[:200],
            }
        )

    result = {
        "input": str(input_path),
        "summary": {
            "frontier_url_count": len(url_entries),
            "host_counts": {host: len(entries) for host, entries in sorted(grouped_by_host.items())},
            "frame_counts": dict(frame_counts),
            "unique_device_ids": sorted(
                {
                    str(entry["summary"]["device_id"])
                    for entry in url_entries
                    if entry["summary"]["device_id"]
                }
            ),
            "unique_conn_tags": sorted(
                {
                    str(entry["summary"]["conn_tag"])
                    for entry in url_entries
                    if entry["summary"]["conn_tag"]
                }
            ),
        },
        "frontier_urls": url_entries,
        "frame_preview_by_request_id": dict(frame_preview_by_request_id),
    }

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + ".frontier.json")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved frontier summary: {output_path}")
    print("== Frontier Hosts ==")
    for host, count in result["summary"]["host_counts"].items():
        print(f"{host}: {count}")
    print("== Unique conn_tag ==")
    for item in result["summary"]["unique_conn_tags"]:
        print(item)
    print("== Unique device_id ==")
    for item in result["summary"]["unique_device_ids"]:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
