from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.auth import UserPublic
from app.schemas.message import MessageOut


class OpenRoomRequest(BaseModel):
    user_id: UUID


class RoomOut(BaseModel):
    id: UUID
    partner: UserPublic
    last_message: Optional[MessageOut] = None
    created_at: datetime


class RoomListResponse(BaseModel):
    rooms: list[RoomOut]


class FriendOut(BaseModel):
    user: UserPublic
    room_id: Optional[UUID] = None


class FriendListResponse(BaseModel):
    friends: list[FriendOut]
