from app.config.settings import get_settings
from app.db.base import Base
from app.db.session import engine
from app.models import (
    BrowserLoginState,
    DouyinLiveComment,
    DouyinLiveRoom,
    DouyinLiveSession,
    DouyinLiveSnapshot,
    PlatformAccount,
    XiaohongshuAccountSnapshot,
    XiaohongshuNote,
    XiaohongshuNoteComment,
    XiaohongshuNoteSnapshot,
)


def init_db() -> None:
    settings = get_settings()
    settings.browser_state_dir.mkdir(parents=True, exist_ok=True)
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    if settings.auto_create_schema:
        _ = (
            BrowserLoginState,
            DouyinLiveComment,
            DouyinLiveRoom,
            DouyinLiveSession,
            DouyinLiveSnapshot,
            PlatformAccount,
            XiaohongshuAccountSnapshot,
            XiaohongshuNote,
            XiaohongshuNoteComment,
            XiaohongshuNoteSnapshot,
        )
        Base.metadata.create_all(bind=engine)
