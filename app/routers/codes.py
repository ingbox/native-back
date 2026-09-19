from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.code import PagerCode
from app.schemas.code import CodesResponse, PagerCodeOut

router = APIRouter(prefix="/api/v1/codes", tags=["codes"])


@router.get("", response_model=CodesResponse)
async def list_codes(db: AsyncSession = Depends(get_db)) -> CodesResponse:
    rows = (await db.execute(select(PagerCode))).scalars().all()
    return CodesResponse(
        codes={
            row.digits: PagerCodeOut(label=row.label, emoji=row.emoji, effect=row.effect)
            for row in rows
        }
    )
