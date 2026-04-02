from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.session import get_db_session
from app.models.login_state import BrowserLoginState


class LoginStateService:
    def upsert_storage_state(
        self,
        *,
        platform: str,
        account_id: str,
        storage_state_path: Path,
        login_type: str = "scan",
        status: str = "valid",
        operator: str | None = None,
        last_error_code: str | None = None,
        last_error_message: str | None = None,
    ) -> BrowserLoginState:
        now = datetime.now(timezone.utc)

        with get_db_session() as session:
            stmt = select(BrowserLoginState).where(
                BrowserLoginState.platform == platform,
                BrowserLoginState.account_id == account_id,
            )
            state = session.execute(stmt).scalar_one_or_none()

            if state is None:
                state = BrowserLoginState(
                    platform=platform,
                    account_id=account_id,
                    storage_state_path=str(storage_state_path),
                )
                session.add(state)

            state.storage_state_path = str(storage_state_path)
            state.login_type = login_type
            state.status = status
            state.operator = operator
            state.last_error_code = last_error_code
            state.last_error_message = last_error_message
            state.last_login_time = now
            state.last_valid_time = now if status == "valid" else state.last_valid_time

            session.flush()
            session.refresh(state)
            return state
