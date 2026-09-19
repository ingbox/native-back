from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import find_user_room, get_current_user, partner_id
from app.models.message import Message
from app.models.room import PairingCode, Room
from app.models.user import User
from app.schemas.auth import UserPublic
from app.schemas.pairing import JoinRequest, PairingCodeResponse, PairingStatusResponse

router = APIRouter(prefix="/api/v1/pairing", tags=["pairing"])

CODE_TTL_MINUTES = 10


async def _unique_code(db: AsyncSession) -> str:
    for _ in range(20):
        code = f"{random.randint(0, 999999):06d}"
        exists = await db.scalar(select(PairingCode.id).where(PairingCode.code == code))
        if exists is None:
            return code
    raise HTTPException(status_code=500, detail="페어링 코드를 만들지 못했어요")


@router.post("/codes", response_model=PairingCodeResponse)
async def create_pairing_code(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PairingCodeResponse:
    if await find_user_room(db, user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 페어링되어 있어요")

    row = PairingCode(
        code=await _unique_code(db),
        creator_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
    )
    db.add(row)
    await db.commit()
    return PairingCodeResponse(code=row.code, expires_at=row.expires_at)


@router.post("/join", response_model=PairingStatusResponse)
async def join_pairing(
    body: JoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PairingStatusResponse:
    if await find_user_room(db, user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 페어링되어 있어요")

    pairing = await db.scalar(select(PairingCode).where(PairingCode.code == body.code))
    now = datetime.now(timezone.utc)
    if pairing is None or pairing.used_at is not None or pairing.expires_at < now:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="유효하지 않은 페어링 코드예요")
    if pairing.creator_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="본인 코드로는 페어링할 수 없어요")
    if await find_user_room(db, pairing.creator_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="상대방이 이미 페어링되어 있어요")

    room = Room(user_a_id=pairing.creator_id, user_b_id=user.id)
    pairing.used_at = now
    db.add(room)
    await db.commit()
    await db.refresh(room)

    partner = await db.get(User, pairing.creator_id)
    return PairingStatusResponse(
        paired=True,
        room_id=room.id,
        partner=UserPublic.model_validate(partner) if partner else None,
    )


@router.get("/status", response_model=PairingStatusResponse)
async def pairing_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PairingStatusResponse:
    room = await find_user_room(db, user.id)
    if room is None:
        return PairingStatusResponse(paired=False)

    partner = await db.get(User, partner_id(room, user.id))
    return PairingStatusResponse(
        paired=True,
        room_id=room.id,
        partner=UserPublic.model_validate(partner) if partner else None,
    )


@router.delete("/room")
async def unpair(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    room = await find_user_room(db, user.id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="페어링된 방이 없어요")

    await db.execute(delete(Message).where(Message.room_id == room.id))
    await db.delete(room)
    await db.commit()
    return {"ok": True}
