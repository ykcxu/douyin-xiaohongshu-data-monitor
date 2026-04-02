from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session_dependency
from app.schemas.douyin_live_room import (
    DouyinLiveRoomCreate,
    DouyinLiveRoomRead,
    DouyinLiveRoomUpdate,
)
from app.services.douyin_live_room_service import DouyinLiveRoomService

router = APIRouter(prefix="/douyin/live-rooms", tags=["douyin-live-rooms"])
room_service = DouyinLiveRoomService()


@router.get("", response_model=list[DouyinLiveRoomRead])
def list_live_rooms(
    session: Annotated[Session, Depends(db_session_dependency)],
    enabled_only: Annotated[bool, Query()] = False,
) -> list[DouyinLiveRoomRead]:
    return room_service.list_rooms(session, enabled_only=enabled_only)


@router.post("", response_model=DouyinLiveRoomRead, status_code=status.HTTP_201_CREATED)
def create_live_room(
    payload: DouyinLiveRoomCreate,
    session: Annotated[Session, Depends(db_session_dependency)],
) -> DouyinLiveRoomRead:
    return room_service.create_room(session, payload)


@router.get("/{room_pk}", response_model=DouyinLiveRoomRead)
def get_live_room(
    room_pk: int,
    session: Annotated[Session, Depends(db_session_dependency)],
) -> DouyinLiveRoomRead:
    room = room_service.get_room(session, room_pk)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live room not found")
    return room


@router.patch("/{room_pk}", response_model=DouyinLiveRoomRead)
def update_live_room(
    room_pk: int,
    payload: DouyinLiveRoomUpdate,
    session: Annotated[Session, Depends(db_session_dependency)],
) -> DouyinLiveRoomRead:
    room = room_service.get_room(session, room_pk)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live room not found")
    return room_service.update_room(session, room, payload)
