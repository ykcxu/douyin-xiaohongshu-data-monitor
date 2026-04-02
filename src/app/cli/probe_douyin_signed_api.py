from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from app.browser.login_manager import BrowserLoginManager
from app.config.settings import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe a Douyin live API from within the browser page context using frontierSign.",
    )
    parser.add_argument("--account-id", required=True, help="Internal account id bound to the storage_state file.")
    parser.add_argument("--room-id", required=True, help="Douyin room id or web_rid.")
    parser.add_argument(
        "--room-url",
        default=None,
        help="Optional room URL override. Defaults to https://live.douyin.com/<room-id>.",
    )
    parser.add_argument(
        "--preset",
        default="room-web-enter",
        choices=["room-web-enter", "webcast-setting", "user-me"],
        help="Known signed API preset to invoke. Defaults to room-web-enter.",
    )
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chromium headless. Defaults to headed mode for easier debugging.",
    )
    return parser


def build_common_query() -> dict[str, str]:
    return {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "pc_client_type": "1",
        "pc_libra_divert": "Windows",
        "update_version_code": "170400",
        "support_h265": "1",
        "support_dash": "0",
        "version_code": "170400",
        "version_name": "17.4.0",
        "cookie_enabled": "true",
        "screen_width": "1280",
        "screen_height": "720",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "browser_name": "Chrome",
        "browser_version": "145.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink",
        "engine_version": "145.0.0.0",
        "os_name": "Windows",
        "os_version": "10",
        "cpu_core_num": "24",
        "device_memory": "8",
        "platform": "PC",
        "downlink": "10",
        "effective_type": "4g",
        "round_trip_time": "50",
    }


def build_preset_path(preset: str, room_id: str) -> str:
    query = build_common_query()
    if preset == "room-web-enter":
        query.update(
            {
                "web_rid": room_id,
                "room_id_str": room_id,
                "enter_source": "web_live",
                "is_need_double_stream": "true",
                "enter_type": "1",
                "prefetch": "0",
            }
        )
        return "/webcast/room/web/enter/?" + urlencode(query)
    if preset == "webcast-setting":
        query.update(
            {
                "app_name": "douyin_web",
                "live_id": "1",
                "device_platform": "web",
                "language": "zh-CN",
                "enter_from": "link_share",
            }
        )
        return "/webcast/setting/?" + urlencode(query)
    if preset == "user-me":
        query.update(
            {
                "app_name": "douyin_web",
                "live_id": "1",
                "device_platform": "web",
                "language": "zh-CN",
                "enter_from": "link_share",
                "room_id": "0",
            }
        )
        return "/webcast/user/me/?" + urlencode(query)
    raise ValueError(f"Unsupported preset: {preset}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    manager = BrowserLoginManager()
    state_file = manager.state_file("douyin", args.account_id)
    if not state_file.exists():
        print(f"Missing storage_state file: {state_file}")
        return 1

    room_url = args.room_url or f"https://live.douyin.com/{args.room_id}"
    request_path = build_preset_path(args.preset, args.room_id)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=str(state_file))
        page = context.new_page()
        page.goto(room_url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("load", timeout=20000)
        except BaseException:
            pass

        payload = page.evaluate(
            """async (requestPath) => {
                const cookies = document.cookie
                  .split(";")
                  .map((item) => item.trim())
                  .filter(Boolean)
                  .map((item) => item.split("=")[0]);
                const signedHeaders = await window.byted_acrawler.frontierSign(requestPath);
                const response = await fetch(requestPath, {
                  credentials: "include",
                  headers: {
                    "accept": "application/json, text/plain, */*",
                    ...signedHeaders,
                  },
                });
                const responseText = await response.text();
                let responseBody = null;
                try {
                  responseBody = JSON.parse(responseText);
                } catch (error) {
                  responseBody = null;
                }
                return {
                  page_url: location.href,
                  request_path: requestPath,
                  signed_headers: signedHeaders,
                  runtime_context: {
                    user_agent: navigator.userAgent,
                    cookie_names: cookies,
                    has_frontier_sign: !!(window.byted_acrawler && window.byted_acrawler.frontierSign),
                    byted_acrawler_keys: window.byted_acrawler ? Object.keys(window.byted_acrawler) : [],
                  },
                  response: {
                    status: response.status,
                    url: response.url,
                    headers: Object.fromEntries(response.headers.entries()),
                    body: responseBody,
                    body_preview: responseBody ? null : responseText.slice(0, 5000),
                  },
                };
            }""",
            request_path,
        )

        cookies = context.cookies(room_url)
        payload["playwright_context"] = {
            "storage_state_path": str(state_file),
            "cookie_count": len(cookies),
            "cookie_names": sorted({cookie.get("name", "") for cookie in cookies if cookie.get("name")}),
        }

        context.close()
        browser.close()

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = (
            settings.raw_data_dir
            / "douyin"
            / "browser-probe"
            / f"{args.account_id}-{args.preset}-{args.room_id}-{timestamp}.json"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved signed API probe: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
