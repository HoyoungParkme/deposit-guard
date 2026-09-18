"""Gate 도메인 ORM 모델 (IpQuota, FileCache).

근거: JSD-DOM-002 2.7, JSD-DOM-003 1장, 2장
"""

from datetime import date, datetime
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class IpQuota(Base):
    """IP 일일 요청 한도 모델 (JSD-DOM-003 ip_quotas)."""

    __tablename__ = "ip_quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip_hash: Mapped[str] = mapped_column(Text, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("ip_hash", "day", name="uq_ip_quotas_hash_day"),
    )


class FileCache(Base):
    """파일 파싱 결과(업스테이지 HTML) 캐시 모델 (JSD-DOM-003 file_caches)."""

    __tablename__ = "file_caches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_sha256: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
