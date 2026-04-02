"""
CLI for WebSocket frame decoding and danmaku extraction.

Usage:
    python -m app.cli.decode_websocket --input data/raw/douyin/request-trace/xxx.jsonl
    python -m app.cli.decode_websocket --input data/raw/douyin/request-trace/xxx.jsonl --output decoded.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.collector.douyin.live.websocket_decoder import analyze_websocket_trace


def main() -> int:
    parser = argparse.ArgumentParser(description="Decode Douyin WebSocket frames")
    parser.add_argument("--input", "-i", type=str, required=True, help="Input trace file")
    parser.add_argument("--output", "-o", type=str, help="Output file (optional)")
    parser.add_argument("--format", choices=["summary", "full"], default="summary", help="Output format")
    parser.add_argument("--limit", type=int, default=20, help="Sample message limit")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    print(f"Analyzing WebSocket frames from: {input_path}")
    results = analyze_websocket_trace(str(input_path))

    if "error" in results:
        print(f"Error: {results['error']}", file=sys.stderr)
        return 1

    stats = results.get("stats", {})
    messages = results.get("messages", [])

    print(f"\n=== WebSocket Frame Analysis ===")
    print(f"Total frames : {results['total_frames']}")
    print(f"Total messages: {len(messages)}")
    print(f"\nMessage type breakdown:")
    for k, v in stats.items():
        if v:
            print(f"  {k:25s}: {v}")

    if messages:
        print(f"\n=== Sample Messages (first {args.limit}) ===")
        for msg in messages[:args.limit]:
            method_short = msg.get("method", "?").replace("Webcast", "").replace("Message", "")
            nickname = msg.get("nickname") or "-"
            content = msg.get("content", "")
            gift = f"  [礼物:{msg['gift_name']}x{msg['gift_count']}]" if msg.get("gift_name") else ""
            online = f"  [在线:{msg['online_count']}]" if msg.get("online_count") else ""
            print(f"  [{method_short:15s}] {nickname:12s}: {content[:80]}{gift}{online}")

    # Output to file if specified
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            if args.format == "summary":
                json.dump({"stats": stats, "messages": messages}, f, indent=2, ensure_ascii=False)
            else:
                json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
