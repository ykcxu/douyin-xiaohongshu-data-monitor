from fastapi import APIRouter

from app.services.live_monitor_service import LiveMonitorService

router = APIRouter(prefix="/monitor", tags=["monitor"])
live_monitor_service = LiveMonitorService()


@router.post("/douyin/live/scan")
def trigger_douyin_live_scan() -> dict[str, int]:
    return live_monitor_service.scan_rooms_once()
