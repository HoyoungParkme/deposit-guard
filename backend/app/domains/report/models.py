"""Report 도메인 ORM 모델 (Opinion).

근거: JSD-DOM-002 2.6, JSD-DOM-003 1장, 2장
"""

import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class Opinion(Base):
    """의견서 모델 (JSD-DOM-003 opinions)."""

    __tablename__ = "opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    subject: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    written_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
