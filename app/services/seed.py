from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code import PagerCode

SEED_CODES = [
    {"digits": "486", "label": "사랑해", "emoji": "💗", "effect": "scale"},
    {"digits": "1004", "label": "천사", "emoji": "👼", "effect": "none"},
    {"digits": "8282", "label": "빨리", "emoji": "⚡", "effect": "haptic"},
]


async def seed_pager_codes(db: AsyncSession) -> None:
    existing = set((await db.execute(select(PagerCode.digits))).scalars().all())
    for item in SEED_CODES:
        if item["digits"] in existing:
            continue
        db.add(PagerCode(**item))
    await db.commit()
