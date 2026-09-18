"""Lookup 도메인 외부 포트(Protocol).

근거: JSD-DOM-002 4.13, JSD-MS-013
"""

from typing import Protocol
from app.domains.lookup.schemas import DefaulterRow, LedgerRow, Trade


class TradeSource(Protocol):
    """국토부 실거래가 조회 포트."""

    async def fetch(self, kind: str, region_code: str, year_month: str) -> list[Trade]:
        """한 달치 실거래가 목록을 반환한다."""
        ...


class LedgerSource(Protocol):
    """건축물대장 표제부 조회 포트."""

    async def fetch(self, region_code: str, bun: str, ji: str) -> list[LedgerRow]:
        """지번의 건축물대장 표제부 행 목록을 반환한다."""
        ...


class DefaulterSource(Protocol):
    """HUG 상습 채무불이행자 명단 조회 포트."""

    async def fetch_all(self) -> list[DefaulterRow]:
        """공개 명단 전체를 반환한다."""
        ...
