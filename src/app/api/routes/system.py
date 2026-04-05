from fastapi import APIRouter

from app.config.settings import get_settings
from app.scheduler.runtime import scheduler_runtime

router = APIRouter(prefix="/system", tags=["system"])
settings = get_settings()


@router.get("/status")
def system_status() -> dict[str, object]:
    jobs = []
    try:
        jobs = [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in scheduler_runtime.scheduler.get_jobs()
        ]
    except Exception:
        jobs = []

    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "scheduler_enabled": settings.scheduler_enabled,
        "scheduler_running": scheduler_runtime.scheduler.running,
        "douyin_live_provider": settings.douyin_live_provider,
        "browser_state_dir": str(settings.browser_state_dir),
        "browser_state_dir_exists": settings.browser_state_dir.exists(),
        "raw_data_dir": str(settings.raw_data_dir),
        "raw_data_dir_exists": settings.raw_data_dir.exists(),
        "live_status_poll_seconds": settings.live_status_poll_seconds,
        "live_snapshot_poll_seconds": settings.live_snapshot_poll_seconds,
        "scheduler_jobs": jobs,
    }
