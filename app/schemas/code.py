from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PagerCodeOut(BaseModel):
    label: str
    emoji: Optional[str] = None
    effect: str


class CodesResponse(BaseModel):
    codes: dict[str, PagerCodeOut]
