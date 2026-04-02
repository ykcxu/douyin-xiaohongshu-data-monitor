from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session_dependency
from app.schemas.platform_account import (
    PlatformAccountCreate,
    PlatformAccountRead,
    PlatformAccountUpdate,
)
from app.services.platform_account_service import PlatformAccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])
account_service = PlatformAccountService()


@router.get("", response_model=list[PlatformAccountRead])
def list_accounts(
    session: Annotated[Session, Depends(db_session_dependency)],
    platform: Annotated[str | None, Query()] = None,
) -> list[PlatformAccountRead]:
    return account_service.list_accounts(session, platform=platform)


@router.post("", response_model=PlatformAccountRead, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: PlatformAccountCreate,
    session: Annotated[Session, Depends(db_session_dependency)],
) -> PlatformAccountRead:
    return account_service.create_account(session, payload)


@router.get("/{account_pk}", response_model=PlatformAccountRead)
def get_account(
    account_pk: int,
    session: Annotated[Session, Depends(db_session_dependency)],
) -> PlatformAccountRead:
    account = account_service.get_account(session, account_pk)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.patch("/{account_pk}", response_model=PlatformAccountRead)
def update_account(
    account_pk: int,
    payload: PlatformAccountUpdate,
    session: Annotated[Session, Depends(db_session_dependency)],
) -> PlatformAccountRead:
    account = account_service.get_account(session, account_pk)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account_service.update_account(session, account, payload)
