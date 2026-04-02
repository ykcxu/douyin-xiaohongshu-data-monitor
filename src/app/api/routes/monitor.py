from fastapi import APIRouter

from app.collector.douyin.live.factory import create_douyin_live_status_collector
from app.services.live_monitor_service import LiveMonitorService

router = APIRouter(prefix="/monitor", tags=["monitor"])
live_monitor_service = LiveMonitorService(create_douyin_live_status_collector())


@router.post("/douyin/live/scan")
def trigger_douyin_live_scan() -> dict[str, int]:
    return live_monitor_service.scan_rooms_once()


@router.get("/douyin/live/sidecar-stats")
def get_douyin_live_sidecar_stats() -> dict[str, object]:
    return live_monitor_service.get_sidecar_stats()


@router.get("/douyin/live/sidecar-decode")
def get_douyin_live_sidecar_decode(room_id: str, limit: int = 5) -> dict[str, object]:
    return live_monitor_service.debug_decode_room_frames(room_id=room_id, limit=limit)
