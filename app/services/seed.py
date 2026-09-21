from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import bcrypt

from app.deps import get_or_create_room
from app.models.code import PagerCode
from app.models.user import User, UserSettings

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


DEV_USERS = [
    {
        "email": "ingbox01@gmail.com",
        "username": "ingbox01",
        "display_name": "ingbox01",
        "password": "1234",
    },
    {
        "email": "dpwlsdl032097@gmail.com",
        "username": "dpwlsdl032097",
        "display_name": "dpwlsdl032097",
        "password": "1234",
    },
    {
        "email": "ingbox02@gmail.com",
        "username": "ingbox02",
        "display_name": "ingbox02",
        "password": "1234",
    },
]


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed_dev_users(db: AsyncSession) -> None:
    for item in DEV_USERS:
        email = item["email"].lower()
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = await db.scalar(select(User).where(User.username == item["username"]))
        if user is None:
            user = User(
                username=item["username"],
                hashed_password=_hash_password(item["password"]),
                display_name=item["display_name"],
                email=email,
            )
            db.add(user)
            await db.flush()
            db.add(UserSettings(user_id=user.id))
            continue

        user.email = email
        user.hashed_password = _hash_password(item["password"])
        if not user.display_name:
            user.display_name = item["display_name"]
    await db.commit()
    await seed_couple_room(db)


async def seed_couple_room(db: AsyncSession) -> None:
    emails = ["ingbox01@gmail.com", "dpwlsdl032097@gmail.com"]
    users = list((await db.scalars(select(User).where(User.email.in_(emails)))).all())
    if len(users) < 2:
        return
    await get_or_create_room(db, users[0].id, users[1].id)
    await db.commit()
