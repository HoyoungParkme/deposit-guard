"""CitationService 단위 테스트.

항목 ID: JSD-MS-007
근거: JSD-MS-007 테스트 관점, JSD-DOM-002 4.7
"""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domains.citation.service import CitationService
from app.domains.registry.schemas import Property, RegistryEntry
from app.domains.review.models import Review
from app.shared.types import (
    BlockExcerpt,
    BuildingType,
    CitationUse,
    ContractType,
    DocKind,
    PurposeCode,
    ReviewStatus,
)


class FakeRegistryService:
    def __init__(self, entries_map: dict[str, RegistryEntry] | None = None):
        self.entries_map = entries_map or {}
        self.excerpts_map: dict[str, BlockExcerpt] = {}

    async def entries(
        self, review_id: str, entry_ids: list[str]
    ) -> list[RegistryEntry]:
        return [self.entries_map[eid] for eid in entry_ids if eid in self.entries_map]

    async def block_excerpt(
        self, review_id: str, block_id: str
    ) -> BlockExcerpt | None:
        return self.excerpts_map.get(block_id)


@pytest.fixture
async def sample_review(db_session: AsyncSession) -> Review:
    """테스트용 Review 생성."""
    rev_id = uuid.uuid4()
    row = Review(
        id=rev_id,
        status=ReviewStatus.running.value,
        deposit_manwon=18000,
        contract_type=ContractType.jeonse.value,
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    await db_session.commit()
    return row



@pytest.mark.asyncio
async def test_resolve_markers(
    db_session: AsyncSession, sample_review: Review
):
    """문장 속 {{entry:...}} 인용 표식 치환 및 유효성 검증 (JSD-MS-007#CitationService.resolve_markers)."""
    rev_id_str = str(sample_review.id)
    doc_id_1 = str(uuid.uuid4())
    doc_id_2 = str(uuid.uuid4())

    entry_eul_2 = RegistryEntry(
        entry_id="eul-2",
        rank_no="2",
        purpose_code=PurposeCode.mortgage,
        document_id=doc_id_1,
        block_ids=["13-2"],
        location_label="을구 2번",
    )
    entry_land = RegistryEntry(
        entry_id="land-eul-1",
        rank_no="1",
        purpose_code=PurposeCode.mortgage,
        document_id=doc_id_2,
        block_ids=["20-1"],
        location_label="토지 을구 1번",
    )

    fake_reg = FakeRegistryService({"eul-2": entry_eul_2, "land-eul-1": entry_land})
    svc = CitationService(db_session, registry_service=fake_reg)

    # 1. 단일 유효 표식
    text1 = "근저당권 {{entry:eul-2}} 설정이 확인되었습니다."
    res1 = await svc.resolve_markers(
        rev_id_str, text1, CitationUse.message, "msg-1"
    )
    assert res1.text == "근저당권 {{c1}} 설정이 확인되었습니다."
    assert len(res1.citations) == 1
    assert res1.citations[0].key == "c1"
    assert res1.citations[0].label == "을구 2번"
    assert res1.dropped == 0

    # 2. 존재하지 않는 표식 (dropped)
    text_invalid = "압류 내역 {{entry:eul-99}} 존재합니다."
    res_inv = await svc.resolve_markers(
        rev_id_str, text_invalid, CitationUse.message, "msg-2"
    )
    assert res_inv.text == "압류 내역 존재합니다."
    assert len(res_inv.citations) == 0
    assert res_inv.dropped == 1

    # 3. 다른 등기부에 걸친 복수 표식 -> 등기부마다 행 생성 (c2, c3)
    text_multi = "선순위 권리로 {{entry:eul-2, land-eul-1}} 확인됨"
    res_multi = await svc.resolve_markers(
        rev_id_str, text_multi, CitationUse.message, "msg-3"
    )
    assert res_multi.text == "선순위 권리로 {{c1}}{{c2}} 확인됨"
    assert len(res_multi.citations) == 2
    assert res_multi.citations[0].document_id == doc_id_1
    assert res_multi.citations[1].document_id == doc_id_2


@pytest.mark.asyncio
async def test_cite_and_for_report(
    db_session: AsyncSession, sample_review: Review
):
    """직접 인용 생성 및 의견서용 인용 조회 (JSD-MS-007#CitationService.cite, for_report)."""
    rev_id_str = str(sample_review.id)
    doc_id = str(uuid.uuid4())

    entry1 = RegistryEntry(
        entry_id="gap-1",
        rank_no="1",
        purpose_code=PurposeCode.ownership_transfer,
        document_id=doc_id,
        block_ids=["10-1"],
        location_label="갑구 1번",
    )
    fake_reg = FakeRegistryService({"gap-1": entry1})
    svc = CitationService(db_session, registry_service=fake_reg)

    # 1. 메시지 인용 1건 생성
    await svc.cite(
        rev_id_str,
        CitationUse.message,
        "msg-1",
        "에이전트 설명 문장",
        ["gap-1"],
    )

    # 2. 의견서 신호 인용 1건 생성
    await svc.cite(
        rev_id_str,
        CitationUse.signal,
        "frequent_transfer",
        "소유권 이전 신호 근거",
        ["gap-1"],
    )

    # for_report 조회 -> 메시지 인용은 제외되고 signal 인용만 반환되어야 함
    report_citations = await svc.for_report(rev_id_str)
    assert len(report_citations) == 1
    assert report_citations[0].used_in == CitationUse.signal
    assert report_citations[0].ref == "frequent_transfer"
    assert report_citations[0].citation.label == "갑구 1번"

    # for_messages 조회
    msg_citations = await svc.for_messages(rev_id_str, ["msg-1"])
    assert "msg-1" in msg_citations
    assert len(msg_citations["msg-1"]) == 1

    # clear_report -> 의견서 인용만 삭제되고 메시지 인용은 유지
    await svc.clear_report(rev_id_str)
    assert len(await svc.for_report(rev_id_str)) == 0
    assert len(await svc.for_messages(rev_id_str, ["msg-1"])) == 1


@pytest.mark.asyncio
async def test_usages(db_session: AsyncSession, sample_review: Review):
    """원문 블록 역방향 쓰인 곳 조회 (JSD-MS-007#CitationService.usages)."""
    rev_id_str = str(sample_review.id)
    doc_id = str(uuid.uuid4())

    entry1 = RegistryEntry(
        entry_id="eul-1",
        rank_no="1",
        purpose_code=PurposeCode.mortgage,
        document_id=doc_id,
        block_ids=["14-1"],
        location_label="을구 1번",
    )
    fake_reg = FakeRegistryService({"eul-1": entry1})
    fake_reg.excerpts_map["14-1"] = BlockExcerpt(
        entry_id="eul-1",
        document_id=doc_id,
        excerpt="1번 근저당권설정 채권최고액 금 120,000,000원",
    )
    svc = CitationService(db_session, registry_service=fake_reg)

    # 인용 생성 (메시지 및 합산에 쓰임)
    await svc.cite(
        rev_id_str,
        CitationUse.message,
        "msg-10",
        "근저당 1.2억원이 설정되어 있습니다.",
        ["eul-1"],
    )
    await svc.cite(
        rev_id_str,
        CitationUse.rights,
        "",
        "선순위 채권최고액 합산",
        ["eul-1"],
    )

    usages = await svc.usages(rev_id_str, "14-1")
    assert usages.block_id == "14-1"
    assert "근저당권설정" in usages.excerpt
    assert len(usages.used_in) == 2
    kinds = [u.kind for u in usages.used_in]
    assert "message" in kinds
    assert "rights" in kinds

    # 존재하지 않는 블록 -> 404 AppError
    with pytest.raises(AppError) as exc:
        await svc.usages(rev_id_str, "non-existent-block")
    assert exc.value.code == "not_found"
