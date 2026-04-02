from __future__ import annotations

import argparse
import json

from app.services.bootstrap import init_db
from app.services.login_state_service import LoginStateService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect a saved browser login state.")
    parser.add_argument("--platform", default="douyin", help="Platform name. Defaults to douyin.")
    parser.add_argument("--account-id", required=True, help="Internal account id.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    init_db()
    service = LoginStateService()
    state = service.get_state(platform=args.platform, account_id=args.account_id)
    if state is None:
        print("Login state not found.")
        return 1

    path = service.resolve_storage_state_path(platform=args.platform, account_id=args.account_id)
    print(f"platform: {state.platform}")
    print(f"account_id: {state.account_id}")
    print(f"status: {state.status}")
    print(f"storage_state_path: {state.storage_state_path}")
    print(f"file_exists: {path is not None}")
    print(f"cookie_hash: {state.cookie_hash or ''}")
    print(f"last_login_time: {state.last_login_time}")
    print(f"last_valid_time: {state.last_valid_time}")
    print(f"operator: {state.operator or ''}")
    if path is not None:
        payload = json.loads(path.read_text(encoding='utf-8'))
        print(f"cookie_count: {len(payload.get('cookies', []))}")
        print(f"origin_count: {len(payload.get('origins', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
