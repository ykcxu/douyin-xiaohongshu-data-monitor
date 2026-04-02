from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def db_session_dependency() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
