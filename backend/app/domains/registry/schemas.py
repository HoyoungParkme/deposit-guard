"""Registry 도메인 DTO 및 스키마.

근거: JSD-DOM-002 2.8, JSD-MS-004, JSD-MS-003
"""

from dataclasses import dataclass, field
from datetime import date
from app.shared.types import BuildingType, DocKind, PurposeCode, Section


@dataclass(frozen=True)
class Property:
    """주택 정보 DTO (JSD-DOM-002 2.8 Property)."""

    region: str
    building_type: BuildingType
    is_collective: bool
    land_right_unregistered: bool
    separate_land_registry: bool
    lot_address: str | None = None
    exclusive_area_m2: float | None = None
    building_name: str | None = None


@dataclass
class RegistryEntry:
    """등기 항목 DTO (JSD-DOM-002 2.8 RegistryEntry)."""

    entry_id: str
    rank_no: str
    purpose_code: PurposeCode
    received_at: date | None = None
    amount_manwon: int | None = None
    price_manwon: int | None = None
    holder: str | None = None
    holder_is_corporation: bool | None = None
    cancelled: bool = False
    document_id: str = ""
    block_ids: list[str] = field(default_factory=list)
    location_label: str = ""
    section: Section = Section.gap
    parent_entry_id: str | None = None
    cause: str | None = None
    cancelled_by_entry_id: str | None = None


@dataclass
class ParsedEntry:
    """파싱된 등기 항목 DTO (JSD-DOM-002 2.8 ParsedEntry)."""

    entry_id: str
    rank_no: str
    purpose_code: PurposeCode
    received_at: date | None
    amount_manwon: int | None
    price_manwon: int | None
    holder: str | None
    holder_is_corporation: bool | None
    cancelled: bool
    receipt_no: str | None
    purpose_text: str
    block_ids: list[str]
    location_label: str
    section: Section
    parent_entry_id: str | None = None
    cause: str | None = None
    cancelled_by_entry_id: str | None = None


@dataclass(frozen=True)
class Block:
    """HTML 요소 블록 DTO (JSD-DOM-002 2.8 Block)."""

    tag: str
    block_id: str
    text: str
    header: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedRegistry:
    """파싱된 등기부 전체 DTO (JSD-DOM-002 2.8 ParsedRegistry)."""

    kind: DocKind
    property: Property | None
    entries: list[ParsedEntry]
    panel_html: str
    warnings: list[str]


@dataclass(frozen=True)
class DocumentBrief:
    """문서 요약 DTO (JSD-DOM-002 2.8 DocumentBrief)."""

    document_id: str
    kind: DocKind
    label: str
    page_count: int


@dataclass(frozen=True)
class Owner:
    """현재 소유자 DTO (JSD-DOM-002 2.8 Owner)."""

    name: str
    is_corporation: bool
    acquired_at: date | None
    cause: PurposeCode
    entry_id: str


@dataclass(frozen=True)
class BlockExcerpt:
    """블록 발췌 DTO (JSD-DOM-002 2.8 BlockExcerpt)."""

    entry_id: str
    document_id: str
    excerpt: str


@dataclass(frozen=True)
class Registry:
    """에이전트가 읽는 등기부 DTO (JSD-DOM-002 2.8 Registry)."""

    document_id: str
    doc_kind: DocKind
    building: Property | None
    gap: list[RegistryEntry]
    eul: list[RegistryEntry]
    warnings: list[str]
