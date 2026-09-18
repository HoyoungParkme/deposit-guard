"""LookupService 외부 데이터 조회 및 HUG 명단 대조 서비스.

항목 ID: JSD-MS-006
근거: JSD-DOM-002 4.6, JSD-DOM-003, JSD-SEQ-001, JSD-API-002
규칙: 다른 서비스를 부르지 않음. 지번·성명 원문을 로그/캐시키에 남기지 않음.
"""

from __future__ import annotations
import asyncio
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import re
from typing import Any, Callable
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.domains.lookup import crud
from app.domains.lookup.ports import DefaulterSource, LedgerSource, TradeSource
from app.domains.lookup.schemas import (
    DefaulterRow,
    LedgerRow,
    RegionCodeRow,
    Trade,
)
from app.domains.registry.schemas import Property
from app.shared.types import (
    BuildingLedger,
    BuildingType,
    DefaulterMatch,
    PriceLookup,
    PriceSource,
)

logger = logging.getLogger("deposit_guard.lookup")


def _hmac_hex(msg: str) -> str:
    """앱 시크릿으로 캐시 키를 HMAC-SHA256 해시하여 개인정보 및 지번 노출을 방지한다."""
    secret = settings.APP_SECRET.encode("utf-8")
    return hmac.new(secret, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalize_name(name: str) -> str:
    """비교를 위해 공백 및 특수문자를 제거한다."""
    return re.sub(r"[\s\(\)\-_]", "", name).lower()


class LookupService:
    """실거래가, 건축물대장, HUG 명단 조회 서비스."""

    def __init__(
        self,
        session: AsyncSession,
        trade_source: TradeSource | None = None,
        ledger_source: LedgerSource | None = None,
        defaulter_source: DefaulterSource | None = None,
        today_fn: Callable[[], date] | None = None,
    ):
        self._session = session
        self._trade_source = trade_source
        self._ledger_source = ledger_source
        self._defaulter_source = defaulter_source
        self._today_fn = today_fn or date.today
        self._db_lock = asyncio.Lock()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def region_code(self, lot_address: str | None) -> str:
        """지번 주소에서 법정동코드 10자리를 조회한다.

        항목 ID: JSD-MS-006#LookupService.region_code
        근거: JSD-UC-001#UC-S4
        """
        if not lot_address or not lot_address.strip():
            raise AppError("no_region_code", "지번 주소가 비어 있어 법정동코드를 조회할 수 없습니다.")

        words = lot_address.strip().split()
        # 마지막 지번 토큰(^산?\d+(-\d+)?$) 제거
        if len(words) > 1 and re.match(r"^산?\d+(-\d+)?$", words[-1]):
            addr_prefix = " ".join(words[:-1])
        else:
            addr_prefix = " ".join(words)

        async with self._db_lock:
            code = await crud.find_region_code(self._session, addr_prefix)
        if not code:
            raise AppError("no_region_code", f"해당 주소에 일치하는 법정동코드가 없습니다.")
        return code

    async def price(
        self, target: Property, area_m2: float | None = None
    ) -> PriceLookup:
        """최근 12개월 같은 단지·유사 면적(±3%) 매매 평균가를 조회한다.

        항목 ID: JSD-MS-006#LookupService.price
        근거: JSD-SEQ-001#SEQ-6, JSD-UC-001#UC-S4, JSD-API-002#lookup_price
        """
        code = await self.region_code(target.lot_address)
        lawd = code[:5]

        # API 매매 종류 매핑
        kind_map = {
            BuildingType.apartment: "apt",
            BuildingType.multi_family_unit: "rh",
            BuildingType.officetel: "offi",
            BuildingType.multi_household: "sh",
            BuildingType.other: "sh",
        }
        api_kind = kind_map.get(target.building_type, "sh")

        # 오늘 기준 과거 12개월 YYYYMM 목록 생성
        today = self._today_fn()
        months: list[str] = []
        cur_year, cur_month = today.year, today.month
        for _ in range(12):
            months.append(f"{cur_year}{cur_month:02d}")
            cur_month -= 1
            if cur_month == 0:
                cur_month = 12
                cur_year -= 1

        now = self._now()
        semaphore = asyncio.Semaphore(4)

        async def fetch_month(ym: str) -> list[Trade] | None:
            async with semaphore:
                key = _hmac_hex(f"trade|{api_kind}|{lawd}|{ym}")
                async with self._db_lock:
                    cached = await crud.get_cached_payload(self._session, key, now)
                if cached is not None:
                    # 캐시 복원
                    return [
                        Trade(
                            date=date.fromisoformat(t["date"]),
                            amount_manwon=t["amount_manwon"],
                            area_m2=t["area_m2"],
                            building_name=t["building_name"],
                        )
                        for t in cached
                    ]

                if self._trade_source is None:
                    return None

                try:
                    trades = await self._trade_source.fetch(api_kind, lawd, ym)
                    payload = [
                        {
                            "date": t.date.isoformat(),
                            "amount_manwon": t.amount_manwon,
                            "area_m2": t.area_m2,
                            "building_name": t.building_name,
                        }
                        for t in trades
                    ]
                    expires = now + timedelta(hours=24)
                    async with self._db_lock:
                        await crud.save_cache_payload(
                            self._session, "trade", key, payload, expires
                        )
                    return trades
                except Exception as e:
                    logger.warning(f"Trade fetch failed for {ym}: {e}")
                    return None

        results = await asyncio.gather(*(fetch_month(ym) for ym in months))
        all_trades: list[Trade] = []
        failed_count = 0
        for r in results:
            if r is None:
                failed_count += 1
            else:
                all_trades.extend(r)

        if failed_count == len(months):
            raise AppError("api_failed", "공공 실거래가 조회가 모두 실패했습니다.")

        # 거르기 (면적 및 건물명 일치)
        target_area = area_m2 if area_m2 is not None else target.exclusive_area_m2
        filtered: list[Trade] = []
        for t in all_trades:
            # sh(단독다가구)가 아닌 경우 건물명 대조
            if api_kind != "sh" and target.building_name:
                if _normalize_name(t.building_name) != _normalize_name(
                    target.building_name
                ):
                    continue

            # 면적 ±3%
            if target_area is not None and target_area > 0:
                if abs(t.area_m2 - target_area) > (target_area * 0.03):
                    continue

            filtered.append(t)

        if not filtered:
            raise AppError("no_trades", "조건에 일치하는 실거래 매매 내역이 없습니다.")

        avg_price = round(sum(t.amount_manwon for t in filtered) / len(filtered))
        sorted_trades = sorted(filtered, key=lambda x: x.date, reverse=True)
        earliest = min(t.date for t in filtered)
        latest = max(t.date for t in filtered)
        period = f"{earliest.strftime('%Y.%m')}~{latest.strftime('%Y.%m')}"

        samples = [
            {
                "date": t.date.isoformat(),
                "amount_manwon": t.amount_manwon,
                "area_m2": t.area_m2,
            }
            for t in sorted_trades[:5]
        ]

        return PriceLookup(
            price_manwon=avg_price,
            count=len(filtered),
            period=period,
            source=PriceSource.trade_api,
            samples=samples,
        )

    async def building(self, target: Property) -> BuildingLedger:
        """건축물대장 표제부를 조회한다.

        항목 ID: JSD-MS-006#LookupService.building
        근거: JSD-SEQ-001#SEQ-6, JSD-UC-001#UC-S5, JSD-API-002#lookup_building
        """
        code = await self.region_code(target.lot_address)

        if not target.lot_address:
            raise AppError("no_region_code", "지번 주소가 없습니다.")

        words = target.lot_address.strip().split()
        last_word = words[-1] if words else ""

        if last_word.startswith("산"):
            raise AppError("not_found", "산 번지는 건축물대장 조회를 지원하지 않습니다.")

        match = re.match(r"^(\d+)(?:-(\d+))?$", last_word)
        if not match:
            raise AppError("not_found", "올바른 본번·부번 형식이 아닙니다.")

        bun = match.group(1).zfill(4)
        ji = (match.group(2) or "0").zfill(4)

        key = _hmac_hex(f"building|{code}|{bun}|{ji}")
        now = self._now()

        cached = await crud.get_cached_payload(self._session, key, now)
        if cached is not None:
            rows = [
                LedgerRow(
                    main_use=r["main_use"],
                    ledger_kind=r["ledger_kind"],
                    households=r["households"],
                    families=r["families"],
                    approved_at=date.fromisoformat(r["approved_at"])
                    if r["approved_at"]
                    else None,
                    dong_name=r["dong_name"],
                )
                for r in cached
            ]
        else:
            if self._ledger_source is None:
                raise AppError("api_failed", "건축물대장 어댑터가 설정되지 않았습니다.")

            try:
                rows = await self._ledger_source.fetch(code, bun, ji)
                payload = [
                    {
                        "main_use": r.main_use,
                        "ledger_kind": r.ledger_kind.value
                        if hasattr(r.ledger_kind, "value")
                        else r.ledger_kind,
                        "households": r.households,
                        "families": r.families,
                        "approved_at": r.approved_at.isoformat()
                        if r.approved_at
                        else None,
                        "dong_name": r.dong_name,
                    }
                    for r in rows
                ]
                expires = now + timedelta(hours=24)
                await crud.save_cache_payload(
                    self._session, "building", key, payload, expires
                )
            except Exception as e:
                logger.warning(f"Ledger fetch failed: {e}")
                raise AppError("api_failed", "건축물대장 조회 중 오류가 발생했습니다.") from e

        if not rows:
            raise AppError("not_found", "건축물대장 정보가 존재하지 않습니다.")

        # 고르기: 주건축물 중 동 명칭 또는 주택 용도 우선
        selected: LedgerRow | None = None
        if len(rows) == 1:
            selected = rows[0]
        else:
            if target.building_name:
                for r in rows:
                    if r.dong_name and (
                        _normalize_name(r.dong_name)
                        in _normalize_name(target.building_name)
                        or _normalize_name(target.building_name)
                        in _normalize_name(r.dong_name)
                    ):
                        selected = r
                        break

            if selected is None:
                for r in rows:
                    if any(
                        kw in r.main_use
                        for kw in ("공동주택", "단독주택", "다세대", "다가구", "아파트", "오피스텔", "주택")
                    ):
                        selected = r
                        break

            if selected is None:
                selected = rows[0]

        return BuildingLedger(
            main_use=selected.main_use,
            ledger_kind=selected.ledger_kind,
            households=selected.households,
            families=selected.families,
            approved_at=selected.approved_at,
            multiple_candidates=(len(rows) > 1),
        )

    async def defaulter(self, name: str | None) -> DefaulterMatch:
        """HUG 상습 채무불이행자 공개 명단과 성명을 대조한다.

        항목 ID: JSD-MS-006#LookupService.defaulter
        근거: JSD-SEQ-001#SEQ-6, JSD-UC-001#UC-S6, JSD-API-002#match_defaulter
        """
        snap = await crud.get_max_defaulter_snapshot_date(self._session)
        if snap is None:
            raise AppError("no_snapshot", "HUG 악성 임대인 명단 스냅샷이 적재되지 않았습니다.")

        if not name or not name.strip():
            raise AppError("no_name", "대조할 임대인 성명이 제공되지 않았습니다.")

        normalized = _normalize_name(name)
        count = await crud.count_matching_defaulters(self._session, normalized)

        return DefaulterMatch(
            matched=(count > 0),
            match_count=count,
            snapshot_date=snap,
            note="동명이인일 수 있습니다. 나이·주소로 직접 확인하세요",
        )

    async def refresh_defaulters(self) -> int:
        """HUG 악성 임대인 공개 명단 전체를 스크래핑해 스냅샷을 교체한다.

        항목 ID: JSD-MS-006#LookupService.refresh_defaulters
        근거: JSD-SEQ-001#SEQ-17, JSD-UC-001#UC-S6
        """
        if self._defaulter_source is None:
            raise AppError("api_failed", "DefaulterSource가 제공되지 않았습니다.")

        rows = await self._defaulter_source.fetch_all()
        if not rows:
            logger.warning("defaulter_refresh_empty: 0 records fetched, skipping replacement")
            return 0

        today = self._today_fn()
        count = await crud.replace_defaulter_records(self._session, rows, today)
        logger.info(f"Refreshed {count} defaulter records for snapshot {today}")
        return count

    async def load_region_codes(self, rows: list[RegionCodeRow]) -> int:
        """법정동코드 10자리 데이터를 적재 및 갱신한다.

        항목 ID: JSD-MS-006#LookupService.load_region_codes
        근거: JSD-UC-001#UC-S4
        """
        return await crud.upsert_region_code_rows(self._session, rows)

    async def purge_cache(self, now: datetime) -> int:
        """만료된 외부 조회 캐시를 삭제한다.

        항목 ID: JSD-MS-006#LookupService.purge_cache
        근거: JSD-SEQ-001#SEQ-16
        """
        return await crud.delete_expired_lookup_caches(self._session, now)
