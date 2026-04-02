from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.collector.douyin.live.factory import create_douyin_live_status_collector
from app.config.settings import get_settings
from app.services.live_monitor_service import LiveMonitorService


class SchedulerRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self.live_monitor_service = LiveMonitorService(create_douyin_live_status_collector())
        self._configured = False

    def configure(self) -> None:
        if self._configured:
            return

        self.scheduler.add_job(
            self.live_monitor_service.scan_rooms_once,
            trigger=IntervalTrigger(seconds=self.settings.live_status_poll_seconds),
            id="douyin_live_status_scan",
            name="Douyin Live Status Scan",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._configured = True

    def start(self) -> None:
        if not self.settings.scheduler_enabled:
            return
        self.configure()
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
