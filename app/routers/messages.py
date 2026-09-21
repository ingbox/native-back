from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_owned_room
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageListResponse, MessageOut, SendMessageRequest
from app.services.ws_manager import manager

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


def to_out(message: Message, user_id: UUID) -> MessageOut:
    return MessageOut(
        id=message.id,
        digits=message.digits,
        from_me=message.sender_id == user_id,
        created_at=message.created_at,
    )


def decode_cursor(cursor: str) -> datetime:
    try:
        return datetime.fromisoformat(cursor)
    except ValueError:
        raise HTTPException(status_code=400, detail="커서 형식이 올바르지 않아요")


@router.get("", response_model=MessageListResponse)
async def list_messages(
    room_id: UUID,
    before: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    room = await get_owned_room(db, user.id, room_id)
    stmt = select(Message).where(Message.room_id == room.id)
    if before:
        stmt = stmt.where(Message.created_at < decode_cursor(before))
    stmt = stmt.order_by(Message.created_at.desc()).limit(limit + 1)

    rows = list((await db.execute(stmt)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    rows.reverse()

    return MessageListResponse(
        messages=[to_out(row, user.id) for row in rows],
        next_cursor=rows[0].created_at.isoformat() if has_more and rows else None,
    )


@router.get("/latest", response_model=Optional[MessageOut])
async def latest_message(
    room_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Optional[MessageOut]:
    room = await get_owned_room(db, user.id, room_id)
    message = await db.scalar(
        select(Message).where(Message.room_id == room.id).order_by(Message.created_at.desc()).limit(1)
    )
    return to_out(message, user.id) if message else None


@router.post("", response_model=MessageOut, status_code=201)
async def send_message(
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    room = await get_owned_room(db, user.id, body.room_id)
    message = Message(room_id=room.id, sender_id=user.id, digits=body.digits)
    db.add(message)
    await db.commit()
    await db.refresh(message)

    payload = {
        "type": "message.new",
        "payload": {
            "id": str(message.id),
            "room_id": str(room.id),
            "digits": message.digits,
            "sender_id": str(message.sender_id),
            "created_at": message.created_at.isoformat(),
        },
    }
    await manager.broadcast(room.id, payload, exclude=user.id)
    return to_out(message, user.id)
