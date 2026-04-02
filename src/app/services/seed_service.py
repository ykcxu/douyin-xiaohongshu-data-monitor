from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.douyin_live_room import DouyinLiveRoom
from app.models.platform_account import PlatformAccount


DEFAULT_PLATFORM_ACCOUNTS: list[dict[str, object]] = [
    {
        "account_no": "DY-DEMO-001",
        "platform": "douyin",
        "account_id": "douyin_demo_account_001",
        "account_handle": "douyin_demo_account_001",
        "nickname": "抖音演示账号",
        "account_type": "brand",
        "is_competitor": False,
        "department": "市场部",
        "owner": "codex",
        "priority": 10,
        "status": "active",
        "homepage_url": "https://www.douyin.com/",
        "live_room_url": "https://live.douyin.com/demo-room-001",
        "discover_source": "seed",
        "tags": ["demo", "douyin"],
        "notes": "系统初始化演示账号",
    },
    {
        "account_no": "XHS-DEMO-001",
        "platform": "xiaohongshu",
        "account_id": "xiaohongshu_demo_account_001",
        "account_handle": "xiaohongshu_demo_account_001",
        "nickname": "小红书演示账号",
        "account_type": "brand",
        "is_competitor": False,
        "department": "市场部",
        "owner": "codex",
        "priority": 20,
        "status": "active",
        "homepage_url": "https://www.xiaohongshu.com/",
        "discover_source": "seed",
        "tags": ["demo", "xiaohongshu"],
        "notes": "系统初始化演示账号",
    },
]

DEFAULT_DOUYIN_ROOMS: list[dict[str, object]] = [
    {
        "room_id": "demo-room-001",
        "room_handle": "demo-room-001",
        "account_id": "douyin_demo_account_001",
        "nickname": "抖音演示直播间",
        "live_title": "直播监测演示房间",
        "room_url": "https://live.douyin.com/demo-room-001",
        "status": "active",
        "is_monitor_enabled": True,
        "monitor_priority": 10,
        "tags": "demo,douyin",
        "notes": "系统初始化演示直播间",
    }
]


class SeedService:
    def ensure_default_seed(self, session: Session) -> dict[str, int]:
        created_accounts = 0
        created_rooms = 0

        for payload in DEFAULT_PLATFORM_ACCOUNTS:
            stmt = select(PlatformAccount).where(PlatformAccount.account_no == payload["account_no"])
            account = session.execute(stmt).scalar_one_or_none()
            if account is None:
                account = PlatformAccount(**payload)
                session.add(account)
                created_accounts += 1

        session.flush()

        for payload in DEFAULT_DOUYIN_ROOMS:
            stmt = select(DouyinLiveRoom).where(DouyinLiveRoom.room_id == payload["room_id"])
            room = session.execute(stmt).scalar_one_or_none()
            if room is not None:
                continue

            account_stmt = select(PlatformAccount).where(
                PlatformAccount.platform == "douyin",
                PlatformAccount.account_id == payload["account_id"],
            )
            account = session.execute(account_stmt).scalar_one_or_none()
            room = DouyinLiveRoom(
                platform_account_id=account.id if account else None,
                **payload,
            )
            session.add(room)
            created_rooms += 1

        session.commit()
        return {
            "created_accounts": created_accounts,
            "created_rooms": created_rooms,
        }
