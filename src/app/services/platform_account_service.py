from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.platform_account import PlatformAccount
from app.schemas.platform_account import PlatformAccountCreate, PlatformAccountUpdate


class PlatformAccountService:
    def list_accounts(self, session: Session, *, platform: str | None = None) -> list[PlatformAccount]:
        stmt = select(PlatformAccount).order_by(PlatformAccount.priority.asc(), PlatformAccount.id.asc())
        if platform:
            stmt = stmt.where(PlatformAccount.platform == platform)
        return list(session.execute(stmt).scalars().all())

    def get_account(self, session: Session, account_id: int) -> PlatformAccount | None:
        return session.get(PlatformAccount, account_id)

    def create_account(self, session: Session, payload: PlatformAccountCreate) -> PlatformAccount:
        account = PlatformAccount(**payload.model_dump())
        session.add(account)
        session.commit()
        session.refresh(account)
        return account

    def update_account(
        self,
        session: Session,
        account: PlatformAccount,
        payload: PlatformAccountUpdate,
    ) -> PlatformAccount:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(account, key, value)
        session.add(account)
        session.commit()
        session.refresh(account)
        return account
