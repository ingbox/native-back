from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    digits: str = Field(min_length=1, max_length=64)
    room_id: UUID


class MessageOut(BaseModel):
    id: UUID
    digits: str
    from_me: bool
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[MessageOut]
    next_cursor: Optional[str] = None
