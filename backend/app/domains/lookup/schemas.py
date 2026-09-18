"""Lookup 도메인 스키마 및 DTO.

근거: JSD-DOM-002 2.8, JSD-MS-006
"""

from dataclasses import dataclass
from datetime import date
from app.shared.types import LedgerKind


@dataclass(frozen=True)
class Trade:
    """실거래가 1건 DTO (JSD-DOM-002 2.8 Trade)."""

    date: date
    amount_manwon: int
    area_m2: float
    building_name: str


@dataclass(frozen=True)
class LedgerRow:
    """건축물대장 표제부 1행 DTO (JSD-DOM-002 2.8 LedgerRow)."""

    main_use: str
    ledger_kind: LedgerKind
    households: int | None = None
    families: int | None = None
    approved_at: date | None = None
    dong_name: str | None = None


@dataclass(frozen=True)
class DefaulterRow:
    """HUG 악성 임대인 명단 1행 DTO (JSD-DOM-002 2.8 DefaulterRow)."""

    name: str
    age: int | None = None
    address: str = ""
    debt_manwon: int | None = None
    default_period: str | None = None


@dataclass(frozen=True)
class RegionCodeRow:
    """법정동코드 1행 DTO (JSD-DOM-002 2.8 RegionCodeRow)."""

    code: str
    name: str
    is_active: bool = True
