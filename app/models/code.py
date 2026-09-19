from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PagerCode(Base):
    __tablename__ = "pipi_pager_codes"

    digits: Mapped[str] = mapped_column(String(16), primary_key=True)
    label: Mapped[str] = mapped_column(String(40))
    emoji: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    effect: Mapped[str] = mapped_column(String(16), default="none")
