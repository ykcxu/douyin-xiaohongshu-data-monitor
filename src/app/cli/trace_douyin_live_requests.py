from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from app.browser.login_manager import BrowserLoginManager
from app.config.settings import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open a Douyin live room with saved login state and record network and WebSocket traffic.",
    )
    parser.add_argument("--account-id", required=True, help="Internal account id bound to the storage_state file.")
    parser.add_argument("--room-url", required=True, help="Douyin live room URL to inspect.")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSONL output path. Defaults to RAW_DATA_DIR/douyin/request-trace/<timestamp>.jsonl",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=30,
        help="How long to keep the room open and collect traffic before exiting. Defaults to 30.",
    )
    return parser


def append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def normalize_headers(headers: Any) -> dict[str, str]:
    if isinstance(headers, dict):
        return {str(key): str(value) for key, value in headers.items()}
    return {}


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
        cdp_session = context.new_cdp_session(page)
        cdp_session.send("Network.enable")

        def on_request(request) -> None:
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
            payload = {
                "event": "response",
                "ts": datetime.now(timezone.utc).isoformat(),
                "method": request.method,
                "resource_type": request.resource_type,
                "url": response.url,
                "status": response.status,
                "headers": normalize_headers(response.headers),
            }
            try:
                if request.resource_type in {"fetch", "xhr", "document"}:
                    payload["body_preview"] = response.text()[:5000]
                else:
                    payload["body_preview"] = None
            except BaseException:
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

        def on_console(message) -> None:
            append_jsonl(
                output_path,
                {
                    "event": "console",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": message.type,
                    "text": message.text,
                },
            )

        def on_websocket_created(params: dict[str, Any]) -> None:
            append_jsonl(
                output_path,
                {
                    "event": "cdp_websocket_created",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "request_id": params.get("requestId"),
                    "url": params.get("url"),
                    "initiator": params.get("initiator"),
                },
            )

        def on_websocket_frame_received(params: dict[str, Any]) -> None:
            response_payload = params.get("response", {})
            append_jsonl(
                output_path,
                {
                    "event": "cdp_websocket_frame_received",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "request_id": params.get("requestId"),
                    "opcode": response_payload.get("opcode"),
                    "payload_preview": str(response_payload.get("payloadData", ""))[:5000],
                },
            )

        def on_websocket_frame_sent(params: dict[str, Any]) -> None:
            response_payload = params.get("response", {})
            append_jsonl(
                output_path,
                {
                    "event": "cdp_websocket_frame_sent",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "request_id": params.get("requestId"),
                    "opcode": response_payload.get("opcode"),
                    "payload_preview": str(response_payload.get("payloadData", ""))[:5000],
                },
            )

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("websocket", on_websocket)
        page.on("console", on_console)
        cdp_session.on("Network.webSocketCreated", on_websocket_created)
        cdp_session.on("Network.webSocketFrameReceived", on_websocket_frame_received)
        cdp_session.on("Network.webSocketFrameSent", on_websocket_frame_sent)

        page.goto(args.room_url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("load", timeout=20000)
        except BaseException:
            pass
        print(f"Tracing Douyin live room traffic to: {output_path}")
        print(f"Collecting traffic for {args.wait_seconds} seconds...")
        page.wait_for_timeout(args.wait_seconds * 1000)

        context.close()
        browser.close()

    print(f"Saved trace file: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
