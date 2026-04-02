from __future__ import annotations

import argparse

from app.browser.login_manager import BrowserLoginManager
from app.services.bootstrap import init_db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open a local browser, complete Douyin login, and save Playwright storage_state.",
    )
    parser.add_argument("--platform", default="douyin", help="Platform name. Defaults to douyin.")
    parser.add_argument(
        "--account-id",
        required=True,
        help="Internal account id used by the monitoring system.",
    )
    parser.add_argument(
        "--login-url",
        default=None,
        help="Optional login URL override.",
    )
    parser.add_argument(
        "--operator",
        default=None,
        help="Optional operator name written to browser_login_state.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=600,
        help="Fallback wait time when stdin is unavailable (default: 600 seconds).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    init_db()
    manager = BrowserLoginManager()
    state_file = manager.interactive_login(
        platform=args.platform,
        account_id=args.account_id,
        login_url=args.login_url,
        operator=args.operator,
        fallback_wait_seconds=args.wait_seconds,
    )
    print(f"Saved storage_state: {state_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
