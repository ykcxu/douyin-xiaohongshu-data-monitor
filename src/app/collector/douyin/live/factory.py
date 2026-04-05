from app.collector.douyin.live.browser_provider import BrowserDouyinLiveStatusCollector
from app.collector.douyin.live.providers import HttpDouyinLiveStatusCollector
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
    if settings.douyin_live_provider == "http":
        return HttpDouyinLiveStatusCollector()
    if settings.douyin_live_provider == "browser":
        return BrowserDouyinLiveStatusCollector(
            timeout_seconds=30,
            headless=getattr(settings, 'douyin_browser_headless', True),
            challenge_retry_seconds=getattr(settings, 'douyin_challenge_retry_seconds', 900),
        )

    raise ValueError(f"Unsupported Douyin live provider: {settings.douyin_live_provider}")
