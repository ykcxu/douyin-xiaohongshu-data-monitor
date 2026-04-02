from fastapi import APIRouter

from app.collector.douyin.live.factory import create_douyin_live_status_collector
from app.services.live_monitor_service import LiveMonitorService

router = APIRouter(prefix="/monitor", tags=["monitor"])
live_monitor_service = LiveMonitorService(create_douyin_live_status_collector())


@router.post("/douyin/live/scan")
def trigger_douyin_live_scan() -> dict[str, int]:
    return live_monitor_service.scan_rooms_once()
