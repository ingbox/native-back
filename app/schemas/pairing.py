from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import UserPublic


class PairingCodeResponse(BaseModel):
    code: str
    expires_at: datetime


class JoinRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PairingStatusResponse(BaseModel):
    paired: bool
    room_id: Optional[UUID] = None
    partner: Optional[UserPublic] = None
