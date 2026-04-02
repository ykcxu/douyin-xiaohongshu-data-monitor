from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.login_state import BrowserLoginStateRead
from app.services.login_state_service import LoginStateService

router = APIRouter(prefix="/login-states", tags=["login-states"])
login_state_service = LoginStateService()


@router.get("", response_model=BrowserLoginStateRead)
def get_login_state(
    platform: Annotated[str, Query(min_length=1)],
    account_id: Annotated[str, Query(min_length=1)],
) -> BrowserLoginStateRead:
    state = login_state_service.get_state(platform=platform, account_id=account_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Login state not found")
    return state
