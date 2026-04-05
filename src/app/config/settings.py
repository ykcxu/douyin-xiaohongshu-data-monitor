from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    app_name: str = Field(default="douyin-xiaohongshu-monitor", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_root: Path = Field(default=Path("."), alias="APP_ROOT")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    auto_create_schema: bool = Field(default=False, alias="AUTO_CREATE_SCHEMA")

    postgres_db: str = Field(default="monitoring", alias="POSTGRES_DB")
    postgres_user: str = Field(default="monitoring", alias="POSTGRES_USER")
    postgres_password: str = Field(default="change_me", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    browser_state_dir: Path = Field(default=Path("./runtime/browser"), alias="BROWSER_STATE_DIR")
    raw_data_dir: Path = Field(default=Path("./data/raw"), alias="RAW_DATA_DIR")
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    live_status_poll_seconds: int = Field(default=30, alias="LIVE_STATUS_POLL_SECONDS")
    live_snapshot_poll_seconds: int = Field(default=30, alias="LIVE_SNAPSHOT_POLL_SECONDS")
    douyin_live_provider: str = Field(default="stub", alias="DOUYIN_LIVE_PROVIDER")
    douyin_browser_headless: bool = Field(default=True, alias="DOUYIN_BROWSER_HEADLESS")
    douyin_challenge_retry_seconds: int = Field(default=900, alias="DOUYIN_CHALLENGE_RETRY_SECONDS")
    douyin_watcher_max_new_rooms_per_tick: int = Field(default=1, alias="DOUYIN_WATCHER_MAX_NEW_ROOMS_PER_TICK")
    douyin_watcher_max_rooms_per_tick: int = Field(default=2, alias="DOUYIN_WATCHER_MAX_ROOMS_PER_TICK")

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    if not settings.app_root.is_absolute():
        settings.app_root = (PROJECT_ROOT / settings.app_root).resolve()
    if not settings.browser_state_dir.is_absolute():
        settings.browser_state_dir = (settings.app_root / settings.browser_state_dir).resolve()
    if not settings.raw_data_dir.is_absolute():
        settings.raw_data_dir = (settings.app_root / settings.raw_data_dir).resolve()

    settings.browser_state_dir.mkdir(parents=True, exist_ok=True)
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    return settings
