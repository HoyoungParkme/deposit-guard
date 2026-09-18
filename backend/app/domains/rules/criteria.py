"""공식 판정 기준 및 규칙 상수.

근거: JSD-MS-005 3장, JSD-PRD-001 R4, R5, R6, R11, JSD-API-001 GET /api/criteria
규칙: 순수 상수 및 데이터 정의. 외부 종속성 없음.
"""

from datetime import date
from app.shared.types import BuildingType, Severity

RULE_VERSION = "2026-09-15"

DEBT_RATIO = {
    "formula": "부채비율 = (선순위 채권최고액 + 선순위 보증금 + 내 보증금) ÷ 주택 가격",
    "danger": 0.90,
    "caution": 0.70,
    "senior": 0.54,
}

GRADES = {
    "danger": "부채비율 90% 초과 또는 즉시 위험 신호(경매, 압류, 신탁 등) 확인",
    "caution": "부채비율 70% 초과 90% 이하 또는 주의 신호(최근 근저당, 잦은 소유권 이전 등) 확인",
    "safe": "부채비율 70% 이하 및 위험·주의 신호 없음",
}

SIGNALS: dict[str, dict] = {
    "rights_infringement": {
        "code": "rights_infringement",
        "severity": Severity.danger,
        "label": "소유권 침해 등기(압류·가압류·가처분·경매 등)",
        "source": "LH 전세임대 권리분석 기준",
        "source_date": date(2026, 9, 15),
    },
    "trust": {
        "code": "trust",
        "severity": Severity.danger,
        "label": "신탁 등기 (수탁자 동의 없는 계약 위험)",
        "source": "대법원 판례 및 HUG 보증 요건",
        "source_date": date(2026, 9, 15),
    },
    "lease_registration": {
        "code": "lease_registration",
        "severity": Severity.danger,
        "label": "기존 임차권등기명령 (보증금 미반환 이력)",
        "source": "주택임대차보호법 제3조의3",
        "source_date": date(2026, 9, 15),
    },
    "owner_mismatch": {
        "code": "owner_mismatch",
        "severity": Severity.danger,
        "label": "등기부 소유자와 계약 상대방 불일치",
        "source": "주택임대차표준계약서",
        "source_date": date(2026, 9, 15),
    },
    "defaulter_listed": {
        "code": "defaulter_listed",
        "severity": Severity.danger,
        "label": "HUG 상습 채무불이행자(악성 임대인) 명단 등재",
        "source": "HUG 주택도시보증공사",
        "source_date": date(2026, 9, 15),
    },
    "illegal_or_commercial": {
        "code": "illegal_or_commercial",
        "severity": Severity.danger,
        "label": "위반건축물 또는 근린생활시설(상가)",
        "source": "건축법 및 서울시 전세 체크리스트",
        "source_date": date(2026, 9, 15),
    },
    "land_right_issue": {
        "code": "land_right_issue",
        "severity": Severity.caution,
        "label": "대지권 미등기 또는 토지 별도등기 있음",
        "source": "LH 전세임대 권리분석 기준",
        "source_date": date(2026, 9, 15),
    },
    "recent_mortgage": {
        "code": "recent_mortgage",
        "severity": Severity.caution,
        "label": "최근 90일 이내 근저당권 설정",
        "source": "서울시 전세사기 예방 가이드",
        "source_date": date(2026, 9, 15),
    },
    "frequent_transfer": {
        "code": "frequent_transfer",
        "severity": Severity.caution,
        "label": "단기간 잦은 소유권 변동 (1년 내 보존 또는 2년 내 2회 이상 이전)",
        "source": "국토교통부 전세사기 의심 유형",
        "source_date": date(2026, 9, 15),
    },
    "corporate_landlord": {
        "code": "corporate_landlord",
        "severity": Severity.caution,
        "label": "임대인이 법인 (우선변제권 및 보증 가입 제한 가능성)",
        "source": "HUG 보증 가입 요건",
        "source_date": date(2026, 9, 15),
    },
    "senior_excess": {
        "code": "senior_excess",
        "severity": Severity.caution,
        "label": "선순위 채권 비율 54% 초과 (보증 한도 제한 가능성)",
        "source": "HUG 전세보증금반환보증 기준",
        "source_date": date(2026, 9, 15),
    },
    "multi_household_unknown": {
        "code": "multi_household_unknown",
        "severity": Severity.caution,
        "label": "다가구주택 기존 세입자 보증금 미확인",
        "source": "LH 전세임대 권리분석 기준",
        "source_date": date(2026, 9, 15),
    },
}

PRICE_ORDER = ["trade_api", "registry_sale", "user_input"]

# 최우선변제금 지역 구분 (시 단위 보수적 매칭)
PRIORITY_REPAYMENT_TIERS = [
    ("서울특별시", 5500),
    ("서울", 5500),
    ("세종특별자치시", 4800),
    ("세종", 4800),
    ("인천광역시", 4800),
    ("인천", 4800),
    ("의정부시", 4800),
    ("구리시", 4800),
    ("하남시", 4800),
    ("고양시", 4800),
    ("수원시", 4800),
    ("성남시", 4800),
    ("안양시", 4800),
    ("부천시", 4800),
    ("광명시", 4800),
    ("과천시", 4800),
    ("의왕시", 4800),
    ("군포시", 4800),
    ("남양주시", 4800),
    ("시흥시", 4800),
    ("용인시", 4800),
    ("화성시", 4800),
    ("김포시", 4800),
    # 광역시 및 지정 시
    ("부산광역시", 2800),
    ("부산", 2800),
    ("대구광역시", 2800),
    ("대구", 2800),
    ("광주광역시", 2800),
    ("대전광역시", 2800),
    ("대전", 2800),
    ("울산광역시", 2800),
    ("울산", 2800),
    ("안산시", 2800),
    ("광주시", 2800),
    ("파주시", 2800),
    ("이천시", 2800),
    ("평택시", 2800),
]

DEFAULT_PRIORITY_REPAYMENT = 2500


def get_priority_repayment(region: str) -> int:
    """주소/지역명에 맞는 방당 최우선변제금(만원)을 계산한다."""
    if not region:
        return DEFAULT_PRIORITY_REPAYMENT
    # 가장 긴 일치 기준
    matched_tier: tuple[str, int] | None = None
    for name, amount in PRIORITY_REPAYMENT_TIERS:
        if name in region:
            if matched_tier is None or len(name) > len(matched_tier[0]):
                matched_tier = (name, amount)
    if matched_tier:
        return matched_tier[1]
    return DEFAULT_PRIORITY_REPAYMENT


REQUIRED_CHECKS: dict[str, list[str]] = {
    "common": [
        "owner_match",
        "gap_infringement",
        "trust",
        "history",
        "eul_sum",
        "lease_jeonse",
        "debt_ratio",
        "defaulter_list",
    ],
    BuildingType.apartment: ["trade_price"],
    BuildingType.multi_family_unit: [
        "trade_price",
        "land_right",
        "ledger_main_use",
        "illegal_building",
    ],
    BuildingType.multi_household: [
        "trade_price",
        "land_registry",
        "ledger_households",
        "illegal_building",
        "tenants",
    ],
    BuildingType.officetel: ["trade_price", "residential_use", "illegal_building"],
    BuildingType.other: ["trade_price", "illegal_building"],
}

CHECKLIST: dict[str, dict] = {
    "owner_match": {
        "code": "owner_match",
        "label": "소유자 일치 확인",
        "stage": "before",
        "method": "A",
        "how_to_check": "신분증 및 등기부등본 갑구 소유자 성명 대조",
    },
    "gap_infringement": {
        "code": "gap_infringement",
        "label": "소유권 침해 등기 확인",
        "stage": "before",
        "method": "A",
        "how_to_check": "갑구 압류·가압류·가처분·경매개시결정 유무 확인",
    },
    "trust": {
        "code": "trust",
        "label": "신탁 등기 확인",
        "stage": "before",
        "method": "A",
        "how_to_check": "갑구 신탁등기 유무 및 신탁원부 확인",
    },
    "history": {
        "code": "history",
        "label": "단기 소유권 변동 확인",
        "stage": "before",
        "method": "A",
        "how_to_check": "갑구 소유권 이전 내역 및 보존등기 일자 확인",
    },
    "eul_sum": {
        "code": "eul_sum",
        "label": "선순위 근저당권 합산",
        "stage": "before",
        "method": "A",
        "how_to_check": "을구 근저당 채권최고액 합산",
    },
    "lease_jeonse": {
        "code": "lease_jeonse",
        "label": "선순위 전세권·임차권 확인",
        "stage": "before",
        "method": "A",
        "how_to_check": "을구 전세권 설정 및 임차권등기명령 확인",
    },
    "debt_ratio": {
        "code": "debt_ratio",
        "label": "부채비율 계산",
        "stage": "before",
        "method": "A",
        "how_to_check": "선순위 채권 및 보증금 합계 대비 시세 비율 확인",
    },
    "defaulter_list": {
        "code": "defaulter_list",
        "label": "상습 채무불이행자 명단 대조",
        "stage": "before",
        "method": "B",
        "how_to_check": "HUG 안심전세포털 악성 임대인 공개 명단 대조",
    },
    "trade_price": {
        "code": "trade_price",
        "label": "시세 및 실거래가 확인",
        "stage": "before",
        "method": "B",
        "how_to_check": "국토부 실거래가 공개시스템 및 부동산 공시가격 알리미 확인",
    },
    "land_right": {
        "code": "land_right",
        "label": "대지권 상태 확인",
        "stage": "before",
        "method": "A",
        "how_to_check": "표제부 대지권등록 및 토지등기부 확인",
    },
    "ledger_main_use": {
        "code": "ledger_main_use",
        "label": "건축물대장 주용도 확인",
        "stage": "before",
        "method": "B",
        "how_to_check": "정부24 건축물대장상 주거용도 여부 확인",
    },
    "ledger_households": {
        "code": "ledger_households",
        "label": "다가구 가구수 확인",
        "stage": "before",
        "method": "B",
        "how_to_check": "건축물대장상 가구수 및 호수 대조",
    },
    "residential_use": {
        "code": "residential_use",
        "label": "주거용 사용 확인",
        "stage": "before",
        "method": "C",
        "how_to_check": "오피스텔의 주거용 전입신고 가능 여부 확인",
    },
    "land_registry": {
        "code": "land_registry",
        "label": "토지 등기부등본 확인",
        "stage": "before",
        "method": "A",
        "how_to_check": "토지등기부 갑구·을구 권리관계 확인",
    },
    "illegal_building": {
        "code": "illegal_building",
        "label": "위반건축물 등재 여부 확인",
        "stage": "before",
        "method": "C",
        "how_to_check": "건축물대장 표제부 우측 상단 위반건축물 노란색 표기 확인",
    },
    "tenants": {
        "code": "tenants",
        "label": "기존 세입자 보증금 확인",
        "stage": "before",
        "method": "C",
        "how_to_check": "임대인 전입세대확인서 및 확정일자 부여현황 확인",
    },
    "landlord_type": {
        "code": "landlord_type",
        "label": "임대인 법인 여부 확인",
        "stage": "before",
        "method": "A",
        "how_to_check": "법인등기부등본 및 사업자등록증 확인",
    },
    "tax_arrears": {
        "code": "tax_arrears",
        "label": "국세·지방세 체납 확인",
        "stage": "signing",
        "method": "C",
        "how_to_check": "임대인 국세·지방세 납세증명서 확인",
    },
}

SOURCES: list[dict] = [
    {
        "organization": "LH 한국토지주택공사",
        "document": "LH 전세임대 권리분석 기준",
        "scope": "부채비율 90% 한도 및 필수 확인 사항",
        "date": "2026-09-15",
    },
    {
        "organization": "HUG 주택도시보증공사",
        "document": "전세보증금반환보증 가입 요건",
        "scope": "선순위 채권 54% 한도 및 악성 임대인 명단",
        "date": "2026-09-15",
    },
    {
        "organization": "법무부·국토교통부",
        "document": "주택임대차표준계약서",
        "scope": "임대인 권리관계 확인 및 표준 특약",
        "date": "2023-10-06",
    },
    {
        "organization": "대한민국 법령",
        "document": "주택임대차보호법 시행령",
        "scope": "지역별 소액임차인 최우선변제금 범위",
        "date": "2026-09-15",
    },
    {
        "organization": "서울특별시",
        "document": "전세사기 피해 예방 체크리스트",
        "scope": "부채비율 70% 권장선 및 단계별 점검 수칙",
        "date": "2026-09-15",
    },
]
