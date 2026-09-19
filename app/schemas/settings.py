from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SettingsOut(BaseModel):
    dark_mode: bool
    notifications_enabled: bool


class SettingsUpdate(BaseModel):
    dark_mode: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
