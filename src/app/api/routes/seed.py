from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import db_session_dependency
from app.services.seed_service import SeedService

router = APIRouter(prefix="/seed", tags=["seed"])
seed_service = SeedService()


@router.post("/demo", status_code=status.HTTP_201_CREATED)
def seed_demo_data(
    session: Annotated[Session, Depends(db_session_dependency)],
) -> dict[str, int]:
    return seed_service.ensure_default_seed(session)
