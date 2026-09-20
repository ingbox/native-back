from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.room import Room
from app.models.user import User
from app.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요해요")

    user_id = decode_token(creds.credentials, "access")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없어요")
    return user


async def get_current_room(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Room:
    room = await find_user_room(db, user.id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="아직 페어링되지 않았어요")
    return room


async def find_user_room(db: AsyncSession, user_id: UUID) -> Optional[Room]:
    result = await db.execute(
        select(Room).where(or_(Room.user_a_id == user_id, Room.user_b_id == user_id))
    )
    return result.scalar_one_or_none()


def ordered_pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


async def find_room_between(db: AsyncSession, a: UUID, b: UUID) -> Optional[Room]:
    user_a_id, user_b_id = ordered_pair(a, b)
    return await db.scalar(select(Room).where(Room.user_a_id == user_a_id, Room.user_b_id == user_b_id))


async def get_or_create_room(db: AsyncSession, a: UUID, b: UUID) -> Room:
    room = await find_room_between(db, a, b)
    if room is not None:
        return room
    user_a_id, user_b_id = ordered_pair(a, b)
    room = Room(user_a_id=user_a_id, user_b_id=user_b_id)
    db.add(room)
    await db.flush()
    return room


def partner_id(room: Room, user_id: UUID) -> UUID:
    return room.user_b_id if room.user_a_id == user_id else room.user_a_id
