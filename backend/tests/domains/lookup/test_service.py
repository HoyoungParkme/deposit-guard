"""LookupService 단위 및 통합 테스트.

항목 ID: JSD-MS-006
근거: JSD-MS-006 테스트 관점, JSD-DOM-002 4.6
"""

from datetime import date, datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domains.lookup import crud
from app.domains.lookup.schemas import (
    DefaulterRow,
    LedgerRow,
    RegionCodeRow,
    Trade,
)
from app.domains.lookup.service import LookupService
from app.domains.registry.schemas import Property
from app.shared.types import BuildingType, LedgerKind, PriceSource


class FakeTradeSource:
    def __init__(self, trades_by_month: dict[str, list[Trade]] | None = None):
        self.trades_by_month = trades_by_month or {}
        self.call_count = 0

    async def fetch(self, kind: str, region_code: str, year_month: str) -> list[Trade]:
        self.call_count += 1
        return self.trades_by_month.get(year_month, [])


class FakeLedgerSource:
    def __init__(self, rows: list[LedgerRow] | None = None):
        self.rows = rows or []
        self.call_count = 0

    async def fetch(self, region_code: str, bun: str, ji: str) -> list[LedgerRow]:
        self.call_count += 1
        return self.rows


class FakeDefaulterSource:
    def __init__(self, rows: list[DefaulterRow] | None = None):
        self.rows = rows or []

    async def fetch_all(self) -> list[DefaulterRow]:
        return self.rows


@pytest.fixture
async def seeded_region_codes(db_session: AsyncSession):
    svc = LookupService(db_session)
    await svc.load_region_codes(
        [
            RegionCodeRow(
                code="1135010500",
                name="서울특별시 노원구 상계동",
                is_active=True,
            ),
            RegionCodeRow(
                code="4119210100",
                name="경기도 부천시 원미구 심곡동",
                is_active=True,
            ),
            RegionCodeRow(
                code="9999999999",
                name="폐지된지역동",
                is_active=False,
            ),
        ]
    )


@pytest.mark.asyncio
async def test_region_code_lookup(
    db_session: AsyncSession, seeded_region_codes
):
    """지번 주소에서 법정동코드 조회 검증 (JSD-MS-006#LookupService.region_code)."""
    svc = LookupService(db_session)

    # 서울시 노원구 상계동
    code1 = await svc.region_code("서울특별시 노원구 상계동 715")
    assert code1 == "1135010500"

    # 부천시 원미구 심곡동
    code2 = await svc.region_code("경기도 부천시 원미구 심곡동 55-1")
    assert code2 == "4119210100"

    # 폐지된 코드
    with pytest.raises(AppError) as exc:
        await svc.region_code("폐지된지역동 123")
    assert exc.value.code == "no_region_code"

    # 매칭되지 않는 주소
    with pytest.raises(AppError) as exc2:
        await svc.region_code("외계행성 안드로메다 1")
    assert exc2.value.code == "no_region_code"


@pytest.mark.asyncio
async def test_defaulter_matching(db_session: AsyncSession):
    """HUG 악성 임대인 명단 대조 및 공백 정규화 검증 (JSD-MS-006#LookupService.defaulter)."""
    today = date(2026, 9, 17)
    fake_source = FakeDefaulterSource(
        [
            DefaulterRow(name="홍길동", age=45, address="서울 강남구", debt_manwon=50000),
            DefaulterRow(name="김사기", age=39, address="경기 부천시", debt_manwon=120000),
        ]
    )
    svc = LookupService(
        db_session, defaulter_source=fake_source, today_fn=lambda: today
    )

    # 스냅샷 적재 전 조회 시 no_snapshot
    with pytest.raises(AppError) as exc:
        await svc.defaulter("홍길동")
    assert exc.value.code == "no_snapshot"

    # 스냅샷 적재
    count = await svc.refresh_defaulters()
    assert count == 2

    # 공백 포함 성명 조회 -> 일치
    match1 = await svc.defaulter("홍 길 동")
    assert match1.matched is True
    assert match1.match_count == 1
    assert match1.snapshot_date == today

    # 미등재 성명
    match2 = await svc.defaulter("이안심")
    assert match2.matched is False
    assert match2.match_count == 0


@pytest.mark.asyncio
async def test_building_ledger_lookup_and_cache(
    db_session: AsyncSession, seeded_region_codes
):
    """건축물대장 표제부 조회 및 캐시 적중 검증 (JSD-MS-006#LookupService.building)."""
    today = date(2026, 9, 17)
    rows = [
        LedgerRow(
            main_use="근린생활시설",
            ledger_kind=LedgerKind.general,
            households=None,
            families=None,
            approved_at=date(2015, 1, 1),
            dong_name="상가동",
        ),
        LedgerRow(
            main_use="다세대주택",
            ledger_kind=LedgerKind.collective,
            households=8,
            families=None,
            approved_at=date(2018, 5, 20),
            dong_name="101동",
        ),
    ]
    fake_ledger = FakeLedgerSource(rows)
    svc = LookupService(db_session, ledger_source=fake_ledger, today_fn=lambda: today)

    target = Property(
        region="경기도 부천시 원미구 심곡동",
        building_type=BuildingType.multi_family_unit,
        is_collective=True,
        land_right_unregistered=False,
        separate_land_registry=False,
        lot_address="경기도 부천시 원미구 심곡동 55-1",
        exclusive_area_m2=59.8,
        building_name="101동",
    )

    # 첫 조회 -> fake_ledger 호출
    bldg = await svc.building(target)
    assert fake_ledger.call_count == 1
    assert bldg.main_use == "다세대주택"
    assert bldg.households == 8
    assert bldg.multiple_candidates is True

    # 두 번째 조회 -> 캐시 적중 (fake_ledger 호출 증가 없음)
    bldg_cached = await svc.building(target)
    assert fake_ledger.call_count == 1
    assert bldg_cached.main_use == "다세대주택"


@pytest.mark.asyncio
async def test_price_lookup_and_filtering(
    db_session: AsyncSession, seeded_region_codes
):
    """실거래가 12개월 조회 및 면적/단지 필터링 검증 (JSD-MS-006#LookupService.price)."""
    today = date(2026, 9, 17)
    target_month = "202608"

    trades = [
        # 일치 거래: 상계행복아파트 84.97㎡ (50,000만원)
        Trade(
            date=date(2026, 8, 10),
            amount_manwon=50000,
            area_m2=84.97,
            building_name="상계행복아파트",
        ),
        # 일치 거래 2: 상계행복아파트 84.50㎡ (유사 면적 ±3% 이내 -> 48,000만원)
        Trade(
            date=date(2026, 8, 15),
            amount_manwon=48000,
            area_m2=84.50,
            building_name="상계행복아파트",
        ),
        # 불일치 면적: 87.6㎡ (> 3% 초과)
        Trade(
            date=date(2026, 8, 20),
            amount_manwon=60000,
            area_m2=87.60,
            building_name="상계행복아파트",
        ),
        # 불일치 단지: 다른아파트
        Trade(
            date=date(2026, 8, 22),
            amount_manwon=52000,
            area_m2=84.97,
            building_name="다른아파트",
        ),
    ]

    fake_trades = FakeTradeSource({target_month: trades})
    svc = LookupService(db_session, trade_source=fake_trades, today_fn=lambda: today)

    prop = Property(
        region="서울특별시 노원구 상계동",
        building_type=BuildingType.apartment,
        is_collective=True,
        land_right_unregistered=False,
        separate_land_registry=False,
        lot_address="서울특별시 노원구 상계동 715",
        exclusive_area_m2=84.97,
        building_name="상계행복아파트",
    )

    res = await svc.price(prop)
    # 50000과 48000의 평균 = 49000
    assert res.price_manwon == 49000
    assert res.count == 2
    assert res.source == PriceSource.trade_api
    assert len(res.samples) == 2

    # 두 번째 조회 시 캐시 적중 -> 소스 호출 수 증가 없음
    initial_calls = fake_trades.call_count
    res_cached = await svc.price(prop)
    assert res_cached.price_manwon == 49000
    assert fake_trades.call_count == initial_calls


@pytest.mark.asyncio
async def test_purge_cache(db_session: AsyncSession):
    """만료된 캐시 삭제 검증 (JSD-MS-006#LookupService.purge_cache)."""
    now = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
    svc = LookupService(db_session)

    # 1시간 전 만료된 캐시와 1시간 후 만료될 캐시 저장
    await crud.save_cache_payload(
        db_session, "trade", "old_key", {"test": 1}, now - timedelta(hours=1)
    )
    await crud.save_cache_payload(
        db_session, "trade", "future_key", {"test": 2}, now + timedelta(hours=1)
    )

    deleted = await svc.purge_cache(now)
    assert deleted == 1

    # 남아있는 캐시 확인
    cached = await crud.get_cached_payload(db_session, "future_key", now)
    assert cached == {"test": 2}

