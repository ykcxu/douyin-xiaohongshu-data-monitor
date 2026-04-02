"""
CLI for browser sidecar operations.

Usage:
    python -m app.cli.browser_sidecar --action watch --room-id <room_id> --account-id <account_id>
    python -m app.cli.browser_sidecar --action status --room-id <room_id>
    python -m app.cli.browser_sidecar --action stats
    python -m app.cli.browser_sidecar --action stop --room-id <room_id>
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from app.browser.browser_sidecar import BrowserSidecar, get_browser_sidecar


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser Sidecar CLI")
    parser.add_argument(
        "--action",
        choices=["watch", "status", "refresh", "stop", "stats", "demo"],
        required=True,
        help="Action to perform",
    )
    parser.add_argument("--room-id", type=str, help="Room ID to watch")
    parser.add_argument("--account-id", type=str, default="douyin_demo", help="Account ID")
    parser.add_argument("--platform", type=str, default="douyin", help="Platform")
    parser.add_argument("--room-url", type=str, help="Room URL (optional)")
    parser.add_argument("--wait-seconds", type=int, default=10, help="Seconds to wait after watching")
    
    args = parser.parse_args()
    
    sidecar = get_browser_sidecar()
    
    if args.action == "demo":
        # Demo: watch a room, get status, then stop
        room_id = args.room_id or "7624033765924326144"
        account_id = args.account_id
        
        print(f"[Demo] Starting to watch room {room_id} with account {account_id}")
        
        # Start watching
        session = sidecar.watch_room(
            room_id=room_id,
            account_id=account_id,
            platform=args.platform,
        )
        print(f"[Demo] Room watch session created: {session.room_id}")
        
        # Wait a bit for page to load
        time.sleep(5)
        
        # Get status
        print(f"[Demo] Getting room status...")
        status = sidecar.get_room_status(room_id)
        if status:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            print("[Demo] Failed to get room status")
            
        # Wait for more WebSocket frames
        print(f"[Demo] Waiting {args.wait_seconds}s for WebSocket traffic...")
        time.sleep(args.wait_seconds)
        
        # Get updated status
        status = sidecar.get_room_status(room_id)
        if status:
            print(f"[Demo] WebSocket frames captured: {status.get('websocket_frames_count', 0)}")
            
        # Stop watching
        print(f"[Demo] Stopping watch...")
        sidecar.stop_watching(room_id)
        print(f"[Demo] Done!")
        
    elif args.action == "watch":
        if not args.room_id:
            print("Error: --room-id is required for watch action", file=sys.stderr)
            return 1
            
        session = sidecar.watch_room(
            room_id=args.room_id,
            account_id=args.account_id,
            platform=args.platform,
            room_url=args.room_url,
        )
        print(f"Started watching room: {session.room_id}")
        
        if args.wait_seconds > 0:
            print(f"Waiting {args.wait_seconds}s...")
            time.sleep(args.wait_seconds)
            
    elif args.action == "status":
        if not args.room_id:
            print("Error: --room-id is required for status action", file=sys.stderr)
            return 1
            
        status = sidecar.get_room_status(args.room_id)
        if status:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            print(f"Room {args.room_id} not found")
            return 1
            
    elif args.action == "refresh":
        if not args.room_id:
            print("Error: --room-id is required for refresh action", file=sys.stderr)
            return 1
            
        success = sidecar.refresh_room(args.room_id)
        print(f"Refresh {'successful' if success else 'failed'}")
        
    elif args.action == "stop":
        if not args.room_id:
            print("Error: --room-id is required for stop action", file=sys.stderr)
            return 1
            
        success = sidecar.stop_watching(args.room_id)
        print(f"Stop {'successful' if success else 'failed'}")
        
    elif args.action == "stats":
        stats = sidecar.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
