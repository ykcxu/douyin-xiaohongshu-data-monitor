from app.db.base import Base
from app.db.session import engine
from app.models import BrowserLoginState, PlatformAccount


def init_db() -> None:
    # Importing models above ensures metadata is populated before create_all.
    _ = (BrowserLoginState, PlatformAccount)
    Base.metadata.create_all(bind=engine)
