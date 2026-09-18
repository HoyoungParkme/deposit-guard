"""RegistryService 단위/통합 테스트.

근거: JSD-MS-003, JSD-DOM-002 4.3
"""

from pathlib import Path
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domains.registry.schemas import DocumentBrief
from app.domains.registry.service import RegistryService
from app.shared.types import DocKind, PurposeCode


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "registry" / "fixtures"


def _read_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


async def _create_dummy_review(session: AsyncSession) -> uuid.UUID:
    """테스트용 더미 Review 레코드 생성."""
    review_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO reviews (id, status, deposit_manwon, contract_type, facts, parsed_pages, cost_krw, expires_at)
            VALUES (:id, 'created', 18000, 'jeonse', '{}', 1, 100, NOW() + INTERVAL '1 day')
            """
        ),
        {"id": review_id},
    )
    await session.commit()
    return review_id


@pytest.mark.asyncio
async def test_registry_service_create_and_read(db_session):
    """create_extract 후 read, list, property, owner, holder_names, entries, block_excerpt 테스트."""
    service = RegistryService()
    review_id = await _create_dummy_review(db_session)

    # 1. 신축 빌라(다세대) HTML 등록
    html_caution = _read_fixture("multi_family_caution.html")
    brief1 = await service.create_extract(
        review_id=review_id,
        html=html_caution,
        page_count=1,
        file_sha256="sha256_caution",
        session=db_session,
    )
    await db_session.commit()

    assert brief1.kind == DocKind.collective
    assert brief1.label == "집합건물 등기부"

    # list 조회
    docs = await service.list(review_id)
    assert len(docs) == 1
    assert docs[0].document_id == brief1.document_id

    # get_html
    raw_html = await service.get_html(review_id, brief1.document_id)
    assert 'data-block-id="11-1"' in raw_html

    # property
    prop = await service.property(review_id)
    assert prop is not None
    assert prop.building_name == "해피빌"
    assert prop.exclusive_area_m2 == 44.91

    # owner: gap-1 보존(화곡건설주식회사) -> gap-2 이전(이서연) => 현재 소유자 이서연
    owner_info = await service.owner(review_id)
    assert owner_info is not None
    assert owner_info.name == "이서연"
    assert owner_info.is_corporation is False
    assert owner_info.cause == PurposeCode.ownership_transfer

    # holder_names: 법인 제외 개인 이름만
    holders = await service.holder_names(review_id)
    assert "이서연" in holders
    assert "화곡건설주식회사" not in holders
    assert "화곡새마을금고" not in holders

    # entries 조회
    all_entries = await service.entries(review_id)
    assert len(all_entries) == 3
    # 필터링
    filtered = await service.entries(review_id, entry_ids=["eul-1"])
    assert len(filtered) == 1
    assert filtered[0].entry_id == "eul-1"
    assert filtered[0].amount_manwon == 21000

    # block_excerpt 조회
    excerpt = await service.block_excerpt(review_id, "13-1")
    assert excerpt is not None
    assert excerpt.entry_id == "eul-1"
    assert "근저당권설정" in excerpt.excerpt

    # read: 첫 번째 호출 시 읽지 않은 문서 반환 및 read_by_agent=True 처리
    reg = await service.read(review_id)
    assert reg.document_id == brief1.document_id
    assert len(reg.gap) == 2
    assert len(reg.eul) == 1


@pytest.mark.asyncio
async def test_registry_service_two_documents_limit(db_session):
    """토지 등기부를 2번째로 추가, 건물 등기부 2번째 추가 시 wrong_state."""
    service = RegistryService()
    review_id = await _create_dummy_review(db_session)

    # 1. 다가구(건물) 등록
    html_building = _read_fixture("multi_household_danger.html")
    await service.create_extract(
        review_id=review_id,
        html=html_building,
        page_count=1,
        file_sha256="sha256_danger_building",
        session=db_session,
    )
    await db_session.commit()

    # 2. 건물 등기부를 또 추가하려고 하면 wrong_state
    with pytest.raises(AppError) as exc_info:
        await service.create_extract(
            review_id=review_id,
            html=html_building,
            page_count=1,
            file_sha256="sha256_dup",
            session=db_session,
        )
    assert exc_info.value.code == "wrong_state"

    # 3. 토지 등기부 등록 (성공, land- prefix 붙음)
    html_land = _read_fixture("multi_household_danger_land.html")
    brief_land = await service.create_extract(
        review_id=review_id,
        html=html_land,
        page_count=1,
        file_sha256="sha256_danger_land",
        session=db_session,
    )
    await db_session.commit()
    assert brief_land.kind == DocKind.land

    # 토지 등기부 항목 prefix 확인
    land_entries = await service.entries(review_id, entry_ids=["land-gap-1"])
    assert len(land_entries) == 1
    assert land_entries[0].location_label == "토지 갑구 1번"

    # 4. 세 번째 문서는 wrong_state
    with pytest.raises(AppError) as exc_info:
        await service.create_extract(
            review_id=review_id,
            html=html_land,
            page_count=1,
            file_sha256="sha256_third",
            session=db_session,
        )
    assert exc_info.value.code == "wrong_state"
