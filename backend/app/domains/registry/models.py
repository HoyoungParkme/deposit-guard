"""Registry 도메인 ORM 모델 (RegistryExtract, RegistryEntryRow).

근거: JSD-DOM-002 2.2, JSD-DOM-003 1장, 2장
"""

import uuid
from datetime import date, datetime
from typing import Any
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base

PURPOSE_CODES = (
    "ownership_preserve",
    "ownership_transfer",
    "mortgage",
    "mortgage_change",
    "jeonse_right",
    "lease_right",
    "seizure",
    "provisional_seizure",
    "injunction",
    "provisional_registration",
    "auction",
    "trust",
    "notice_registration",
    "cancellation",
    "other",
)
PURPOSE_CODES_SQL = ", ".join(f"'{c}'" for c in PURPOSE_CODES)


class RegistryExtract(Base):
    """등기부 추출물 모델 (JSD-DOM-003 registry_extracts)."""

    __tablename__ = "registry_extracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    file_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    lot_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    building_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    land_right_unregistered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    separate_land_registry: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    exclusive_area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    building_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    read_by_agent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("id", "review_id", name="uq_registry_extracts_id_review"),
        CheckConstraint(
            "kind IN ('building', 'land', 'collective')",
            name="ck_registry_extracts_kind",
        ),
        CheckConstraint(
            "building_type IS NULL OR building_type IN ('apartment', 'multi_family_unit', 'multi_household', 'officetel', 'other')",
            name="ck_registry_extracts_building_type",
        ),
    )


class RegistryEntryRow(Base):
    """등기부 항목 모델 (JSD-DOM-003 registry_entries)."""

    __tablename__ = "registry_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    extract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entry_id: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str] = mapped_column(Text, nullable=False)
    rank_no: Mapped[str] = mapped_column(Text, nullable=False)
    parent_entry_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose_code: Mapped[str] = mapped_column(Text, nullable=False)
    purpose_text: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    receipt_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_manwon: Mapped[int | None] = mapped_column(Integer, nullable=True)
    holder: Mapped[str | None] = mapped_column(Text, nullable=True)
    holder_is_corporation: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_by_entry_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    block_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    location_label: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("review_id", "entry_id", name="uq_registry_entries_review_entry"),
        ForeignKeyConstraint(
            ["extract_id", "review_id"],
            ["registry_extracts.id", "registry_extracts.review_id"],
            ondelete="CASCADE",
            name="fk_registry_entries_extract",
        ),
        ForeignKeyConstraint(
            ["review_id", "parent_entry_id"],
            ["registry_entries.review_id", "registry_entries.entry_id"],
            ondelete="CASCADE",
            name="fk_registry_entries_parent",
        ),
        CheckConstraint(
            "section IN ('gap', 'eul')",
            name="ck_registry_entries_section",
        ),
        CheckConstraint(
            f"purpose_code IN ({PURPOSE_CODES_SQL})",
            name="ck_registry_entries_purpose_code",
        ),
    )
