from app.config.settings import get_settings


def init_db() -> None:
    settings = get_settings()
    settings.browser_state_dir.mkdir(parents=True, exist_ok=True)
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
