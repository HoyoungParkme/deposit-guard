"""Share 도메인 ORM 모델 (SharedOpinion).

근거: JSD-DOM-002 2.6, JSD-DOM-003 1장, 2장
"""

from datetime import datetime
from typing import Any
from sqlalchemy import (
    DateTime,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class SharedOpinion(Base):
    """공유 의견서 모델 (JSD-DOM-003 shared_opinions)."""

    __tablename__ = "shared_opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    subject: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
