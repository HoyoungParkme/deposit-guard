"""등기부 표 읽기(service_parse) 정답표 4장 및 순수 함수 단위 테스트.

근거: JSD-MS-004 3장 정답표, JSD-DOM-002 4.4
"""

from datetime import date
from pathlib import Path
import pytest

from app.core.errors import AppError
from app.domains.registry.service_parse import (
    clean_html,
    purpose_code,
    read_extract,
    split_blocks,
    won_to_manwon,
)
from app.shared.types import BuildingType, DocKind, PurposeCode


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "registry" / "fixtures"


def _read_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


def test_won_to_manwon():
    assert won_to_manwon("금210,000,000원") == 21000
    assert won_to_manwon("금 80,000,000 원") == 8000
    assert won_to_manwon("금15,555원") == 1
    assert won_to_manwon("일억원") is None
    assert won_to_manwon("") is None


def test_purpose_code():
    assert purpose_code("소유권이전청구권가등기") == PurposeCode.provisional_registration
    assert purpose_code("1번근저당권설 정등기말소") == PurposeCode.cancellation
    assert purpose_code("근저당권변경") == PurposeCode.mortgage_change
    assert purpose_code("주택임차권") == PurposeCode.lease_right
    assert purpose_code("임의경매개시결정") == PurposeCode.auction


def test_not_registry_error():
    """갑구/을구가 없는 일반 HTML -> not_registry."""
    html = "<h1>계약서</h1><p>내용입니다.</p>"
    with pytest.raises(AppError) as exc_info:
        read_extract(html)
    assert exc_info.value.code == "not_registry"


def test_multi_family_caution_answer_sheet():
    """정답표 1: 신축 빌라 (다세대·주의)."""
    html = _read_fixture("multi_family_caution.html")
    parsed = read_extract(html)

    assert parsed.kind == DocKind.collective
    assert parsed.property is not None
    assert parsed.property.lot_address == "서울특별시 강서구 화곡동 123-4"
    assert parsed.property.building_name == "해피빌"
    assert parsed.property.building_type == BuildingType.multi_family_unit
    assert parsed.property.exclusive_area_m2 == 44.91
    assert parsed.property.land_right_unregistered is False
    assert parsed.property.separate_land_registry is False
    assert parsed.warnings == []

    assert len(parsed.entries) == 3

    # gap-1
    e0 = parsed.entries[0]
    assert e0.entry_id == "gap-1"
    assert e0.purpose_code == PurposeCode.ownership_preserve
    assert e0.received_at == date(2025, 11, 3)
    assert e0.receipt_no == "제88213호"
    assert e0.holder == "화곡건설주식회사"
    assert e0.holder_is_corporation is True
    assert e0.block_ids == ["11-1"]

    # gap-2
    e1 = parsed.entries[1]
    assert e1.entry_id == "gap-2"
    assert e1.purpose_code == PurposeCode.ownership_transfer
    assert e1.received_at == date(2026, 2, 10)
    assert e1.receipt_no == "제5521호"
    assert e1.price_manwon == 50000
    assert e1.holder == "이서연"
    assert e1.holder_is_corporation is False
    assert e1.block_ids == ["11-2"]

    # eul-1
    e2 = parsed.entries[2]
    assert e2.entry_id == "eul-1"
    assert e2.purpose_code == PurposeCode.mortgage
    assert e2.received_at == date(2026, 7, 18)
    assert e2.receipt_no == "제30112호"
    assert e2.amount_manwon == 21000
    assert e2.holder == "화곡새마을금고"
    assert e2.holder_is_corporation is True
    assert e2.block_ids == ["13-1"]


def test_apartment_safe_answer_sheet():
    """정답표 2: 아파트 (안전, 을구가 두 표로 분할)."""
    html = _read_fixture("apartment_safe.html")
    parsed = read_extract(html)

    assert parsed.kind == DocKind.collective
    assert parsed.property is not None
    assert parsed.property.lot_address == "서울특별시 노원구 상계동 715"
    assert parsed.property.building_name == "상계행복아파트"
    assert parsed.property.building_type == BuildingType.apartment
    assert parsed.property.exclusive_area_m2 == 84.97
    assert parsed.property.land_right_unregistered is False
    assert parsed.property.separate_land_registry is False
    assert parsed.warnings == []

    assert len(parsed.entries) == 6

    # gap-1
    e0 = parsed.entries[0]
    assert e0.entry_id == "gap-1"
    assert e0.purpose_code == PurposeCode.ownership_preserve
    assert e0.received_at == date(1994, 5, 1)
    assert e0.holder == "상계주택건설주식회사"
    assert e0.holder_is_corporation is True
    assert e0.block_ids == ["11-1"]

    # gap-2
    e1 = parsed.entries[1]
    assert e1.entry_id == "gap-2"
    assert e1.purpose_code == PurposeCode.ownership_transfer
    assert e1.received_at == date(2004, 9, 3)
    assert e1.holder == "정수현"
    assert e1.holder_is_corporation is False
    assert e1.block_ids == ["11-2"]

    # gap-3
    e2 = parsed.entries[2]
    assert e2.entry_id == "gap-3"
    assert e2.purpose_code == PurposeCode.ownership_transfer
    assert e2.received_at == date(2019, 3, 12)
    assert e2.price_manwon == 48000
    assert e2.holder == "김민수"
    assert e2.holder_is_corporation is False
    assert e2.block_ids == ["11-3"]

    # eul-1 (말소됨)
    e3 = parsed.entries[3]
    assert e3.entry_id == "eul-1"
    assert e3.purpose_code == PurposeCode.mortgage
    assert e3.amount_manwon == 15600
    assert e3.holder == "주식회사우리은행"
    assert e3.holder_is_corporation is True
    assert e3.cancelled is True
    assert e3.cancelled_by_entry_id == "eul-2"
    assert e3.block_ids == ["13-1"]

    # eul-2 (말소등기)
    e4 = parsed.entries[4]
    assert e4.entry_id == "eul-2"
    assert e4.purpose_code == PurposeCode.cancellation
    assert e4.cancelled is False
    assert e4.block_ids == ["13-2"]

    # eul-3 (두 번째 을구 표)
    e5 = parsed.entries[5]
    assert e5.entry_id == "eul-3"
    assert e5.purpose_code == PurposeCode.mortgage
    assert e5.amount_manwon == 12000
    assert e5.holder == "주식회사국민은행"
    assert e5.holder_is_corporation is True
    assert e5.cancelled is False
    assert e5.block_ids == ["14-1"]


def test_multi_household_danger_answer_sheet():
    """정답표 3: 다가구 (위험, 건물)."""
    html = _read_fixture("multi_household_danger.html")
    parsed = read_extract(html)

    assert parsed.kind == DocKind.building
    assert parsed.property is not None
    assert parsed.property.lot_address == "경기도 부천시 원미구 심곡동 55-1"
    assert parsed.property.building_name is None
    assert parsed.property.building_type == BuildingType.multi_household
    assert parsed.property.exclusive_area_m2 is None
    assert parsed.property.land_right_unregistered is False
    assert parsed.warnings == []

    assert len(parsed.entries) == 5

    # gap-1
    assert parsed.entries[0].entry_id == "gap-1"
    assert parsed.entries[0].holder == "박영호"
    assert parsed.entries[0].holder_is_corporation is False
    assert parsed.entries[0].block_ids == ["7-1"]

    # gap-2
    assert parsed.entries[1].entry_id == "gap-2"
    assert parsed.entries[1].holder == "주식회사부천하우징"
    assert parsed.entries[1].holder_is_corporation is True
    assert parsed.entries[1].block_ids == ["7-2"]

    # eul-1
    assert parsed.entries[2].entry_id == "eul-1"
    assert parsed.entries[2].amount_manwon == 18000
    assert parsed.entries[2].holder == "농협은행주식회사"
    assert parsed.entries[2].holder_is_corporation is True
    assert parsed.entries[2].block_ids == ["9-1"]

    # eul-2
    assert parsed.entries[3].entry_id == "eul-2"
    assert parsed.entries[3].amount_manwon == 12000
    assert parsed.entries[3].holder == "페퍼저축은행주식회사"
    assert parsed.entries[3].holder_is_corporation is True
    assert parsed.entries[3].block_ids == ["9-2"]

    # eul-3 (주택임차권)
    assert parsed.entries[4].entry_id == "eul-3"
    assert parsed.entries[4].purpose_code == PurposeCode.lease_right
    assert parsed.entries[4].amount_manwon == 8000
    assert parsed.entries[4].holder == "최지우"
    assert parsed.entries[4].holder_is_corporation is False
    assert parsed.entries[4].block_ids == ["9-3"]


def test_multi_household_danger_land_answer_sheet():
    """정답표 4: 다가구의 토지 등기부 (토지)."""
    html = _read_fixture("multi_household_danger_land.html")
    parsed = read_extract(html)

    assert parsed.kind == DocKind.land
    assert parsed.property is None
    assert parsed.warnings == []

    assert len(parsed.entries) == 2

    # gap-1
    assert parsed.entries[0].entry_id == "gap-1"
    assert parsed.entries[0].purpose_code == PurposeCode.ownership_transfer
    assert parsed.entries[0].holder == "주식회사부천하우징"
    assert parsed.entries[0].holder_is_corporation is True
    assert parsed.entries[0].block_ids == ["7-1"]

    # eul-1
    assert parsed.entries[1].entry_id == "eul-1"
    assert parsed.entries[1].purpose_code == PurposeCode.mortgage
    assert parsed.entries[1].amount_manwon == 10000
    assert parsed.entries[1].holder == "농협은행주식회사"
    assert parsed.entries[1].holder_is_corporation is True
    assert parsed.entries[1].block_ids == ["9-1"]


def test_clean_html_structure():
    """clean_html이 올바른 data-block-id를 부여하고 태그를 안전하게 정제하는지 검증."""
    blocks = split_blocks('<h1 id="10">등기</h1><table id="11"><thead><tr><th>순위</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>')
    result = clean_html(blocks)
    assert 'data-block-id="10"' in result
    assert 'data-block-id="11"' in result
    assert 'data-block-id="11-1"' in result
    assert "<script" not in result
