from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict:
    return {"name": "Pipi API", "docs": "/docs", "health": "/health"}


@router.get("/health")
async def health() -> dict:
    return {"ok": True}


@router.get("/api/v1/health")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"ok": True, "database": "connected"}
