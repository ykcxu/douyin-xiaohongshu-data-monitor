from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from app.browser.login_manager import BrowserLoginManager
from app.config.settings import get_settings


INIT_SCRIPT = r"""
(() => {
  const trace = [];
  const maxPreview = 1200;
  const maxEntries = 500;

  function safePreview(value) {
    if (value === null || value === undefined) {
      return null;
    }
    try {
      if (typeof value === "string") {
        return value.slice(0, maxPreview);
      }
      return JSON.stringify(value).slice(0, maxPreview);
    } catch (error) {
      return String(value).slice(0, maxPreview);
    }
  }

  function push(event, payload) {
    trace.push({
      ts: new Date().toISOString(),
      event,
      ...payload,
    });
    if (trace.length > maxEntries) {
      trace.shift();
    }
  }

  Object.defineProperty(window, "__codexRuntimeTrace", {
    value: trace,
    configurable: false,
    enumerable: false,
    writable: false,
  });

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const input = args[0];
    const url = typeof input === "string" ? input : input?.url;
    push("fetch_call", {
      url,
      init_preview: safePreview(args[1]),
    });
    const response = await originalFetch(...args);
    const cloned = response.clone();
    let bodyPreview = null;
    try {
      bodyPreview = (await cloned.text()).slice(0, maxPreview);
    } catch (error) {
      bodyPreview = `<unavailable:${String(error)}>`;
    }
    push("fetch_result", {
      url: response.url,
      status: response.status,
      body_preview: bodyPreview,
    });
    return response;
  };

  const originalXhrOpen = XMLHttpRequest.prototype.open;
  const originalXhrSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__codexUrl = url;
    this.__codexMethod = method;
    push("xhr_open", { method, url });
    return originalXhrOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function(body) {
    push("xhr_send", {
      method: this.__codexMethod || null,
      url: this.__codexUrl || null,
      body_preview: safePreview(body),
    });
    this.addEventListener("loadend", () => {
      push("xhr_result", {
        method: this.__codexMethod || null,
        url: this.__codexUrl || null,
        status: this.status,
        body_preview: typeof this.responseText === "string" ? this.responseText.slice(0, maxPreview) : null,
      });
    });
    return originalXhrSend.call(this, body);
  };

  const originalWebSocket = window.WebSocket;
  window.WebSocket = function(...args) {
    push("websocket_create", { url: args[0] || null });
    const socket = new originalWebSocket(...args);
    socket.addEventListener("message", (event) => {
      push("websocket_message", {
        url: socket.url,
        data_preview: safePreview(event.data),
      });
    });
    return socket;
  };
  window.WebSocket.prototype = originalWebSocket.prototype;
  Object.setPrototypeOf(window.WebSocket, originalWebSocket);

  const hookSigner = () => {
    const acrawler = window.byted_acrawler;
    if (!acrawler || typeof acrawler.frontierSign !== "function" || acrawler.__codexWrapped) {
      return false;
    }
    const originalFrontierSign = acrawler.frontierSign.bind(acrawler);
    acrawler.frontierSign = async (...args) => {
      push("frontier_sign_call", { args_preview: safePreview(args) });
      const result = await originalFrontierSign(...args);
      push("frontier_sign_result", {
        args_preview: safePreview(args),
        result_preview: safePreview(result),
      });
      return result;
    };
    acrawler.__codexWrapped = true;
    push("frontier_sign_wrapped", {
      keys: Object.keys(acrawler),
    });
    return true;
  };

  const timer = window.setInterval(() => {
    if (hookSigner()) {
      window.clearInterval(timer);
    }
  }, 200);
})();
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trace Douyin page runtime calls including frontierSign/fetch/xhr/websocket from within the page.",
    )
    parser.add_argument("--account-id", required=True, help="Internal account id bound to the storage_state file.")
    parser.add_argument("--room-id", required=True, help="Douyin room id or web_rid.")
    parser.add_argument(
        "--room-url",
        default=None,
        help="Optional room URL override. Defaults to https://live.douyin.com/<room-id>.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=20,
        help="How long to keep the page open after load before exporting the runtime trace.",
    )
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chromium headless. Defaults to headed mode.",
    )
    return parser


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

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=str(state_file))
        context.add_init_script(INIT_SCRIPT)
        page = context.new_page()
        page.goto(room_url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("load", timeout=20000)
        except BaseException:
            pass
        page.wait_for_timeout(args.wait_seconds * 1000)
        trace = page.evaluate(
            """() => ({
                page_url: location.href,
                title: document.title,
                runtime_trace: window.__codexRuntimeTrace || [],
                has_frontier_sign: !!(window.byted_acrawler && window.byted_acrawler.frontierSign),
                byted_acrawler_keys: window.byted_acrawler ? Object.keys(window.byted_acrawler) : [],
            })"""
        )
        cookies = context.cookies(room_url)
        trace["playwright_context"] = {
            "storage_state_path": str(state_file),
            "cookie_count": len(cookies),
            "cookie_names": sorted({cookie.get("name", "") for cookie in cookies if cookie.get("name")}),
            "wait_seconds": args.wait_seconds,
            "headless": args.headless,
        }
        runtime_events = trace.get("runtime_trace", [])
        event_counts = Counter(
            str(item.get("event"))
            for item in runtime_events
            if isinstance(item, dict) and item.get("event")
        )
        interesting_paths = []
        seen_paths: set[str] = set()
        for item in runtime_events:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url:
                continue
            path = urlparse(url).path
            if not any(keyword in path for keyword in ("webcast", "comment", "room", "im", "frontier")):
                continue
            if path in seen_paths:
                continue
            seen_paths.add(path)
            interesting_paths.append(path)
        trace["summary"] = {
            "event_counts": dict(event_counts),
            "interesting_paths": interesting_paths,
            "saw_room_web_enter": any("/webcast/room/web/enter/" in path for path in interesting_paths),
            "saw_frontier_sign_call": event_counts.get("frontier_sign_call", 0) > 0,
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
            / "page-runtime-trace"
            / f"{args.account_id}-{args.room_id}-{timestamp}.json"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved runtime trace: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
