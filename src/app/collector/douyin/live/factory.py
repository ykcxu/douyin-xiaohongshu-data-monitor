from app.collector.douyin.live.status_collector import (
    DouyinLiveStatusCollector,
    StubDouyinLiveStatusCollector,
)
from app.config.settings import get_settings


def create_douyin_live_status_collector() -> DouyinLiveStatusCollector:
    settings = get_settings()

    # The real provider will be introduced behind this switch so the scheduler
    # and service layer do not need to change when live integrations are added.
    if settings.douyin_live_provider == "stub":
        return StubDouyinLiveStatusCollector()

    raise ValueError(f"Unsupported Douyin live provider: {settings.douyin_live_provider}")
