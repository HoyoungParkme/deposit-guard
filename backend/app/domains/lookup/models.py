"""Lookup 도메인 ORM 모델 (DefaulterRecord, RegionCode, LookupCache).

근거: JSD-DOM-002 2.4, JSD-DOM-003 1장, 2장
"""

from datetime import date, datetime
from typing import Any
from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class DefaulterRecord(Base):
    """HUG 상습 채무불이행자 명단 스냅샷 모델 (JSD-DOM-003 defaulter_records)."""

    __tablename__ = "defaulter_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    debt_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_period: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)


class RegionCode(Base):
    """법정동코드 10자리 모델 (JSD-DOM-003 region_codes)."""

    __tablename__ = "region_codes"

    code: Mapped[str] = mapped_column(CHAR(10), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LookupCache(Base):
    """외부 조회 캐시 모델 (JSD-DOM-003 lookup_caches)."""

    __tablename__ = "lookup_caches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('trade', 'building')",
            name="ck_lookup_caches_kind",
        ),
    )
