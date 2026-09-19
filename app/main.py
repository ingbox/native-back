from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import SessionLocal, engine
from app.database import Base
from app.models import code, message, room, user  # noqa: F401
from app.routers import auth, codes, health, messages, pairing, settings as settings_router, ws
from app.services.seed import seed_pager_codes


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await seed_pager_codes(db)
    yield
    await engine.dispose()


app = FastAPI(
    title="Pipi API",
    description="React Native 삐삐 채팅 백엔드",
    version="1.0.0",
    lifespan=lifespan,
)

origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(pairing.router)
app.include_router(messages.router)
app.include_router(codes.router)
app.include_router(settings_router.router)
app.include_router(ws.router)
