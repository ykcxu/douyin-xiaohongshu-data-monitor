from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.douyin_live_room import DouyinLiveRoom
from app.schemas.douyin_live_room import DouyinLiveRoomCreate, DouyinLiveRoomUpdate


class DouyinLiveRoomService:
    def list_rooms(self, session: Session, *, enabled_only: bool = False) -> list[DouyinLiveRoom]:
        stmt = select(DouyinLiveRoom).order_by(
            DouyinLiveRoom.monitor_priority.asc(),
            DouyinLiveRoom.id.asc(),
        )
        if enabled_only:
            stmt = stmt.where(DouyinLiveRoom.is_monitor_enabled.is_(True))
        return list(session.execute(stmt).scalars().all())

    def get_room(self, session: Session, room_pk: int) -> DouyinLiveRoom | None:
        return session.get(DouyinLiveRoom, room_pk)

    def create_room(self, session: Session, payload: DouyinLiveRoomCreate) -> DouyinLiveRoom:
        room = DouyinLiveRoom(**payload.model_dump())
        session.add(room)
        session.commit()
        session.refresh(room)
        return room

    def update_room(
        self,
        session: Session,
        room: DouyinLiveRoom,
        payload: DouyinLiveRoomUpdate,
    ) -> DouyinLiveRoom:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(room, key, value)
        session.add(room)
        session.commit()
        session.refresh(room)
        return room
