from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import find_room_between, get_current_user, get_or_create_room, partner_id
from app.models.message import Message
from app.models.room import Room
from app.models.user import User
from app.schemas.auth import UserPublic
from app.schemas.message import MessageOut
from app.schemas.room import FriendListResponse, FriendOut, OpenRoomRequest, RoomListResponse, RoomOut

router = APIRouter(prefix="/api/v1", tags=["rooms"])


def _last_message_out(message: Message | None, user_id: UUID) -> MessageOut | None:
    if message is None:
        return None
    return MessageOut(
        id=message.id,
        digits=message.digits,
        from_me=message.sender_id == user_id,
        created_at=message.created_at,
    )


async def _room_out(db: AsyncSession, room: Room, user_id: UUID) -> RoomOut:
    partner = await db.get(User, partner_id(room, user_id))
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="상대를 찾을 수 없어요")
    last = await db.scalar(
        select(Message).where(Message.room_id == room.id).order_by(Message.created_at.desc()).limit(1)
    )
    return RoomOut(
        id=room.id,
        partner=UserPublic.model_validate(partner),
        last_message=_last_message_out(last, user_id),
        created_at=room.created_at,
    )


@router.get("/friends", response_model=FriendListResponse)
async def list_friends(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FriendListResponse:
    others = list((await db.scalars(select(User).where(User.id != user.id).order_by(User.display_name))).all())
    friends: list[FriendOut] = []
    for other in others:
        room = await find_room_between(db, user.id, other.id)
        friends.append(FriendOut(user=UserPublic.model_validate(other), room_id=room.id if room else None))
    return FriendListResponse(friends=friends)


@router.get("/rooms", response_model=RoomListResponse)
async def list_rooms(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoomListResponse:
    rooms = list(
        (
            await db.scalars(
                select(Room).where((Room.user_a_id == user.id) | (Room.user_b_id == user.id))
            )
        ).all()
    )
    out = [await _room_out(db, room, user.id) for room in rooms]
    out.sort(key=lambda item: item.last_message.created_at if item.last_message else item.created_at, reverse=True)
    return RoomListResponse(rooms=out)


@router.post("/rooms", response_model=RoomOut)
async def open_room(
    body: OpenRoomRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoomOut:
    if body.user_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="나와는 채팅할 수 없어요")
    partner = await db.get(User, body.user_id)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없어요")

    room = await get_or_create_room(db, user.id, partner.id)
    await db.commit()
    await db.refresh(room)
    return await _room_out(db, room, user.id)
