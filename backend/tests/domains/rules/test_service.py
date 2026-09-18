"""RulesService 단위 테스트.

항목 ID: JSD-MS-005
근거: JSD-MS-005 테스트 관점, JSD-DOM-002 4.5
"""

from datetime import date, timedelta
import pytest

from app.shared.types import (
    BuildingType,
    CheckResult,
    CriteriaTopic,
    EntryFact,
    GradeLevel,
    IllegalBuilding,
    Limits,
    OwnerType,
    PriceSource,
    PropertyFact,
    ProxyStatus,
    PurposeCode,
    RightsInput,
    RightsSummary,
    Section,
    Severity,
    SignalInput,
    UnknownReason,
)
from app.domains.rules.service import RulesService
from app.domains.rules.criteria import CHECKLIST, RULE_VERSION, get_priority_repayment


@pytest.fixture
def rules_service() -> RulesService:
    return RulesService()


@pytest.fixture
def mock_limits() -> Limits:
    return Limits(
        tool_calls=20,
        questions=5,
        asks=3,
        answer_timeout_sec=300,
        file_mb=10,
        pages=20,
        retention_hours=24,
        follow_up_tools=5,
        ip_daily=5,
        cost_krw=300,
        text_only_strikes=3,
        share_days=7,
    )


def test_other_tenants(rules_service: RulesService):
    """다가구 기존 세입자 및 공실 최우선변제금 계산 검증 (JSD-MS-005#RulesService.other_tenants)."""
    # 서울 다가구
    inp_seoul = RightsInput(
        entries=[],
        deposit_manwon=10000,
        building_type=BuildingType.multi_household,
        region="서울특별시 관악구 신림동",
        other_tenants_manwon=12000,
        vacant_rooms=2,
    )
    res_seoul = rules_service.other_tenants(inp_seoul)
    assert res_seoul.added_manwon == 12000 + (5500 * 2)  # 23000

    # 부천 다가구
    inp_bucheon = RightsInput(
        entries=[],
        deposit_manwon=10000,
        building_type=BuildingType.multi_household,
        region="경기도 부천시 원미구 심곡동",
        other_tenants_manwon=10000,
        vacant_rooms=1,
    )
    res_bucheon = rules_service.other_tenants(inp_bucheon)
    assert res_bucheon.added_manwon == 10000 + 4800  # 14800

    # 답이 없을 때
    inp_none = RightsInput(
        entries=[],
        deposit_manwon=10000,
        building_type=BuildingType.multi_household,
        region="서울특별시 마포구",
        other_tenants_manwon=None,
        vacant_rooms=None,
    )
    res_none = rules_service.other_tenants(inp_none)
    assert res_none.added_manwon == 0

    # 다세대: 항상 0
    inp_villa = RightsInput(
        entries=[],
        deposit_manwon=10000,
        building_type=BuildingType.multi_family_unit,
        region="서울특별시 강남구",
        other_tenants_manwon=50000,
        vacant_rooms=5,
    )
    res_villa = rules_service.other_tenants(inp_villa)
    assert res_villa.added_manwon == 0


def test_senior_claims(rules_service: RulesService):
    """선순위 권리 추출 및 부기등기/말소등기 반영 검증 (JSD-MS-005#RulesService.senior_claims)."""
    entries = [
        # 말소된 근저당
        EntryFact(
            entry_id="eul-1",
            section=Section.eul,
            rank_no="1",
            purpose_code=PurposeCode.mortgage,
            amount_manwon=15000,
            cancelled=True,
        ),
        # 살아 있는 근저당 24000
        EntryFact(
            entry_id="eul-2",
            section=Section.eul,
            rank_no="2",
            purpose_code=PurposeCode.mortgage,
            amount_manwon=24000,
            cancelled=False,
        ),
        # 2번 근저당의 18000 감액 부기등기
        EntryFact(
            entry_id="eul-2-1",
            section=Section.eul,
            rank_no="2-1",
            parent_entry_id="eul-2",
            purpose_code=PurposeCode.mortgage_change,
            amount_manwon=18000,
            cancelled=False,
        ),
        # 금액 누락된 근저당 -> 제외
        EntryFact(
            entry_id="eul-3",
            section=Section.eul,
            rank_no="3",
            purpose_code=PurposeCode.mortgage,
            amount_manwon=None,
            cancelled=False,
        ),
        # 토지 등기부 근저당 -> 포함
        EntryFact(
            entry_id="land-eul-1",
            section=Section.eul,
            rank_no="1",
            purpose_code=PurposeCode.mortgage,
            amount_manwon=5000,
            cancelled=False,
        ),
    ]

    claims = rules_service.senior_claims(entries, amount_overrides={})
    assert len(claims) == 2
    # eul-2는 부기등기에 의해 18000
    assert claims[0].entry_id == "eul-2"
    assert claims[0].amount_manwon == 18000
    assert claims[1].entry_id == "land-eul-1"
    assert claims[1].amount_manwon == 5000

    # 금액 직접 override 검증
    claims_ovr = rules_service.senior_claims(
        entries, amount_overrides={"eul-2": 20000}
    )
    assert claims_ovr[0].amount_manwon == 20000


def test_price(rules_service: RulesService):
    """주택 가격 후보 선택 우선순위 검증 (JSD-MS-005#RulesService.price)."""
    today = date(2026, 9, 17)
    entries = [
        # 2026-02-10 실거래가 50000 (219일 전 -> 365일 이내)
        EntryFact(
            entry_id="gap-2",
            section=Section.gap,
            rank_no="2",
            purpose_code=PurposeCode.ownership_transfer,
            price_manwon=50000,
            received_at=date(2026, 2, 10),
            cancelled=False,
        )
    ]

    inp = RightsInput(
        entries=entries,
        deposit_manwon=18000,
        building_type=BuildingType.multi_family_unit,
        region="서울",
        override_price_manwon=None,
        trade_price_manwon=None,
        user_price_manwon=None,
        today=today,
    )
    # 거래가액 50000 채택
    p = rules_service.price(inp)
    assert p is not None
    assert p.source == PriceSource.registry_sale
    assert p.amount_manwon == 50000

    # 국토부 실거래가와 직접 입력이 함께 있으면 직접 입력 우선
    inp2 = RightsInput(
        entries=entries,
        deposit_manwon=18000,
        building_type=BuildingType.multi_family_unit,
        region="서울",
        override_price_manwon=48000,
        trade_price_manwon=52000,
        today=today,
    )
    p2 = rules_service.price(inp2)
    assert p2 is not None
    assert p2.source == PriceSource.user_input
    assert p2.amount_manwon == 48000

    # 400일 전 거래가액이면 registry_sale 미사용
    old_entries = [
        EntryFact(
            entry_id="gap-1",
            section=Section.gap,
            rank_no="1",
            purpose_code=PurposeCode.ownership_transfer,
            price_manwon=50000,
            received_at=today - timedelta(days=400),
            cancelled=False,
        )
    ]
    inp3 = RightsInput(
        entries=old_entries,
        deposit_manwon=18000,
        building_type=BuildingType.multi_family_unit,
        region="서울",
        today=today,
    )
    assert rules_service.price(inp3) is None


def test_summarize(rules_service: RulesService):
    """선순위 합산 및 부채비율 계산 검증 (JSD-MS-005#RulesService.summarize)."""
    today = date(2026, 9, 17)
    # 다세대 예시: 을구 2.1억, 보증금 1.8억, 거래가액 5억
    entries = [
        EntryFact(
            entry_id="gap-1",
            section=Section.gap,
            rank_no="1",
            purpose_code=PurposeCode.ownership_preserve,
            received_at=date(2020, 1, 1),
            cancelled=False,
        ),
        EntryFact(
            entry_id="gap-2",
            section=Section.gap,
            rank_no="2",
            purpose_code=PurposeCode.ownership_transfer,
            price_manwon=50000,
            received_at=date(2026, 2, 10),
            cancelled=False,
        ),
        EntryFact(
            entry_id="eul-1",
            section=Section.eul,
            rank_no="1",
            purpose_code=PurposeCode.mortgage,
            amount_manwon=21000,
            cancelled=False,
        ),
    ]

    inp = RightsInput(
        entries=entries,
        deposit_manwon=18000,
        building_type=BuildingType.multi_family_unit,
        region="서울",
        today=today,
    )
    s = rules_service.summarize(inp)
    assert s.senior_total_manwon == 21000
    assert s.price_manwon == 50000
    assert s.price_source == PriceSource.registry_sale
    # (21000 + 18000) / 50000 = 39000 / 50000 = 0.78
    assert s.debt_ratio == 0.78
    assert s.senior_ratio == 0.42
    assert s.based_on == ["eul-1", "gap-2"]

    # 같은 예시에 직접 입력 30000 -> 39000 / 30000 = 1.3
    inp_ovr = RightsInput(
        entries=entries,
        deposit_manwon=18000,
        building_type=BuildingType.multi_family_unit,
        region="서울",
        override_price_manwon=30000,
        today=today,
    )
    s_ovr = rules_service.summarize(inp_ovr)
    assert s_ovr.debt_ratio == 1.3


def test_grade(rules_service: RulesService):
    """등급 결정 및 deciders 검증 (JSD-MS-005#RulesService.grade)."""
    rights_base = RightsSummary(
        senior_mortgage_manwon=0,
        senior_lease_manwon=0,
        other_tenants_manwon=0,
        senior_total_manwon=0,
        deposit_manwon=10000,
        price_manwon=50000,
        price_source=PriceSource.user_input,
        debt_ratio=0.70,
        senior_ratio=0.0,
        multi_household_unknown=False,
        based_on=[],
    )

    # 0.70 안전
    g_safe = rules_service.grade([], rights_base, [])
    assert g_safe.level == GradeLevel.safe
    assert g_safe.deciders == []

    # 0.90 주의
    r_90 = RightsSummary(
        **{**rights_base.__dict__, "debt_ratio": 0.90}
    )
    g_90 = rules_service.grade([], r_90, [])
    assert g_90.level == GradeLevel.caution
    assert "debt_ratio" in g_90.deciders

    # 0.9001 위험
    r_9001 = RightsSummary(
        **{**rights_base.__dict__, "debt_ratio": 0.9001}
    )
    g_9001 = rules_service.grade([], r_9001, [])
    assert g_9001.level == GradeLevel.danger
    assert "debt_ratio" in g_9001.deciders


def test_check_signals_and_unknowns(rules_service: RulesService):
    """12개 신호 및 미확인 항목 검증 (JSD-MS-005#RulesService.check)."""
    today = date(2026, 9, 17)
    owner_entry = EntryFact(
        entry_id="gap-1",
        section=Section.gap,
        rank_no="1",
        purpose_code=PurposeCode.ownership_transfer,
        holder="김민수",
        holder_is_corporation=False,
        received_at=today - timedelta(days=200),
        cancelled=False,
    )
    # 가압류 항목
    seizure_entry = EntryFact(
        entry_id="gap-2",
        section=Section.gap,
        rank_no="2",
        purpose_code=PurposeCode.provisional_seizure,
        received_at=today - timedelta(days=50),
        cancelled=False,
    )

    prop = PropertyFact(
        region="서울특별시",
        building_type=BuildingType.multi_family_unit,
        is_collective=True,
        land_right_unregistered=False,
        separate_land_registry=False,
    )
    rights = RightsSummary(
        senior_mortgage_manwon=0,
        senior_lease_manwon=0,
        other_tenants_manwon=0,
        senior_total_manwon=0,
        deposit_manwon=10000,
        price_manwon=50000,
        price_source=PriceSource.user_input,
        debt_ratio=0.20,
        senior_ratio=0.0,
        multi_household_unknown=False,
        based_on=[],
    )

    inp = SignalInput(
        entries=[owner_entry, seizure_entry],
        property=prop,
        rights=rights,
        owner_matches_counterparty=True,
        proxy_status=ProxyStatus.self,
        illegal_building=IllegalBuilding.no,
        owner_type=OwnerType.individual,
        ledger_main_use="다세대주택",
        defaulter_matched=False,
        tenants_answered=True,
        today=today,
    )

    chk = rules_service.check(inp)
    assert chk.grade.level == GradeLevel.danger
    # rights_infringement 신호 발생
    sig_codes = [s.code for s in chk.signals]
    assert "rights_infringement" in sig_codes
    assert chk.signals[0].entry_ids == ["gap-2"]

    # 가압류가 말소되면 신호 없음
    seizure_cancelled = EntryFact(**{**seizure_entry.__dict__, "cancelled": True})
    inp_clean = SignalInput(**{**inp.__dict__, "entries": [owner_entry, seizure_cancelled]})
    chk_clean = rules_service.check(inp_clean)
    assert chk_clean.grade.level == GradeLevel.safe
    assert len(chk_clean.signals) == 0


def test_criteria(rules_service: RulesService, mock_limits: Limits):
    """판정 기준 공개 API 데이터 검증 (JSD-MS-005#RulesService.criteria)."""
    full = rules_service.criteria(mock_limits)
    assert full.rule_version == RULE_VERSION
    assert full.grades is not None
    assert full.debt_ratio is not None
    assert full.limits is not None
    assert "cost_krw" not in full.limits  # 내부 비용 한도는 숨김
    assert full.limits["tool_calls"] == 20

    # topic debt_ratio 필터링
    sub = rules_service.criteria(mock_limits, topic=CriteriaTopic.debt_ratio)
    assert sub.rule_version == RULE_VERSION
    assert sub.debt_ratio is not None
    assert sub.grades is None


def test_required_steps(rules_service: RulesService):
    """건물 종류별 필수 검토 항목 검증 (JSD-MS-005#RulesService.required_steps)."""
    steps_apt = rules_service.required_steps(BuildingType.apartment)
    assert "trade_price" in steps_apt
    assert "illegal_building" not in steps_apt

    steps_multi = rules_service.required_steps(BuildingType.multi_household)
    assert "tenants" in steps_multi
    assert "illegal_building" in steps_multi
    assert len(steps_multi) == 13

    for code in steps_multi:
        assert code in CHECKLIST
