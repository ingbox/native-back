from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.user import RefreshToken, User, UserSettings
from app.schemas.auth import GoogleLoginRequest, RefreshRequest, TokenResponse, UserPublic
from app.security import create_access_token, create_refresh_token, decode_token, verify_google_id_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_token_hash(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


def _google_username(sub: str) -> str:
    digest = hashlib.sha256(f"google:{sub}".encode("utf-8")).hexdigest()
    return f"g{digest[:19]}"


@router.post("/google", response_model=TokenResponse)
async def google_login(body: GoogleLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    info = verify_google_id_token(body.id_token)
    sub = str(info["sub"])
    email = info.get("email") if info.get("email_verified") else None
    raw_name = info.get("name") or (email.split("@")[0] if email else "삐삐")
    display_name = str(raw_name)[:40]

    user = await db.scalar(select(User).where(User.google_sub == sub))
    if user is None and email:
        user = await db.scalar(select(User).where(User.email == email))
        if user is not None:
            user.google_sub = sub

    if user is None:
        user = User(
            username=_google_username(sub),
            hashed_password=None,
            display_name=display_name,
            google_sub=sub,
            email=email,
        )
        db.add(user)
        await db.flush()
        db.add(UserSettings(user_id=user.id))
    else:
        if email:
            user.email = email
        if display_name and user.display_name.startswith("g"):
            user.display_name = display_name

    return await _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user_id = decode_token(body.refresh_token, "refresh")
    token_row = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == _token_hash(body.refresh_token),
            RefreshToken.revoked.is_(False),
        )
    )
    if token_row is None or token_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="리프레시 토큰이 유효하지 않아요")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없어요")

    token_row.revoked = True
    return await _issue_tokens(db, user)


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    token_row = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.token_hash == _token_hash(body.refresh_token),
        )
    )
    if token_row is not None:
        token_row.revoked = True
        await db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
