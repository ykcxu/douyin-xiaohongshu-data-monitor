from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.browser.login_manager import BrowserLoginManager
from app.config.settings import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open a Douyin live room with saved login state and record XHR/fetch/WebSocket traffic.",
    )
    parser.add_argument("--account-id", required=True, help="Internal account id bound to the storage_state file.")
    parser.add_argument("--room-url", required=True, help="Douyin live room URL to inspect.")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSONL output path. Defaults to RAW_DATA_DIR/douyin/request-trace/<timestamp>.jsonl",
    )
    return parser


def append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    manager = BrowserLoginManager()
    state_file = manager.state_file("douyin", args.account_id)
    if not state_file.exists():
        print(f"Missing storage_state file: {state_file}")
        return 1

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = settings.raw_data_dir / "douyin" / "request-trace" / f"{args.account_id}-{timestamp}.jsonl"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(state_file))
        page = context.new_page()

        def on_request(request) -> None:
            if request.resource_type not in {"fetch", "xhr"}:
                return
            append_jsonl(
                output_path,
                {
                    "event": "request",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "method": request.method,
                    "resource_type": request.resource_type,
                    "url": request.url,
                    "headers": request.headers,
                },
            )

        def on_response(response) -> None:
            request = response.request
            if request.resource_type not in {"fetch", "xhr"}:
                return
            payload = {
                "event": "response",
                "ts": datetime.now(timezone.utc).isoformat(),
                "method": request.method,
                "resource_type": request.resource_type,
                "url": response.url,
                "status": response.status,
                "headers": dict(response.headers),
            }
            try:
                payload["body_preview"] = response.text()[:5000]
            except Exception:
                payload["body_preview"] = None
            append_jsonl(output_path, payload)

        def on_websocket(websocket) -> None:
            append_jsonl(
                output_path,
                {
                    "event": "websocket",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "url": websocket.url,
                },
            )

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("websocket", on_websocket)

        page.goto(args.room_url, wait_until="domcontentloaded")
        print(f"Tracing Douyin live room traffic to: {output_path}")
        print("Keep the page open while requests load. Press Enter here when you want to stop tracing...")
        try:
            input()
        except EOFError:
            page.wait_for_timeout(30000)

        context.close()
        browser.close()

    print(f"Saved trace file: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
