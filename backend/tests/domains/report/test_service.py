"""Report 도메인 단위 및 통합 테스트.

항목 ID: JSD-MS-008
근거: JSD-DOM-002 4.8, JSD-DOM-003, JSD-MS-008
"""

import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.citation.service import CitationService
from app.domains.registry.models import RegistryEntryRow, RegistryExtract
from app.domains.registry.service import RegistryService
from app.domains.report.ports import SentenceWriter
from app.domains.report.service import ReportService
from app.domains.review.models import Review
from app.shared.types import (
    BuildingType,
    ChecklistItem,
    CheckResult,
    ContractType,
    DocKind,
    Grade,
    GradeLevel,
    PriceSource,
    Property,
    PurposeCode,
    RegistryEntry,
    ReportInput,
    RightsSummary,
    RiskSignal,
    Section,
    SentenceRequest,
    Sentences,
    Severity,
    SignalCheck,
    TodoStage,
    UnknownItem,
    UnknownReason,
)


class FakeSentenceWriter:
    """테스트용 문장 작성기 목업."""

    def __init__(
        self,
        conclusion: str = "가짜 결론 문장입니다.",
        explanations: dict[str, str] | None = None,
        questions: list[str] | None = None,
        should_fail: bool = False,
    ):
        self.conclusion = conclusion
        self.explanations = explanations or {}
        self.questions = questions or []
        self.should_fail = should_fail
        self.call_count = 0
        self.last_request: SentenceRequest | None = None

    async def write(self, req: SentenceRequest) -> Sentences:
        self.call_count += 1
        self.last_request = req
        if self.should_fail:
            raise RuntimeError("LLM 호출 실패")
        return Sentences(
            conclusion=self.conclusion,
            explanations=self.explanations,
            questions=self.questions,
            tokens_in=100,
            tokens_out=50,
        )


@pytest.fixture
def make_report_input():
    def _create(
        deposit_manwon: int = 15000,
        building_type: BuildingType = BuildingType.multi_family_unit,
        grade_level: GradeLevel = GradeLevel.caution,
        deciders: list[str] | None = None,
        signals: list[RiskSignal] | None = None,
        unknowns: list[UnknownItem] | None = None,
        entries: list[RegistryEntry] | None = None,
        use_model: bool = True,
    ) -> ReportInput:
        deciders = deciders or ["debt_ratio"]
        signals = signals or [
            RiskSignal(
                code="senior_heavy",
                severity=Severity.caution,
                label="선순위 채권 과다",
                source="HUG",
                entry_ids=["eul-1"],
                source_date=date(2026, 9, 1),
            )
        ]
        unknowns = unknowns or []
        entries = entries or [
            RegistryEntry(
                entry_id="eul-1",
                rank_no="1",
                purpose_code=PurposeCode.mortgage,
                received_at=date(2020, 1, 1),
                amount_manwon=7000,
                price_manwon=None,
                holder="우리은행",
                holder_is_corporation=True,
                cancelled=False,
                document_id="doc-1",
                block_ids=["blk-1"],
                location_label="을구 1번",
                section=Section.eul,
            )
        ]
        rights = RightsSummary(
            senior_mortgage_manwon=7000,
            senior_lease_manwon=0,
            other_tenants_manwon=0,
            senior_total_manwon=7000,
            deposit_manwon=deposit_manwon,
            price_manwon=25000,
            price_source=PriceSource.trade_api,
            debt_ratio=0.88,
            senior_ratio=0.28,
            multi_household_unknown=False,
            based_on=["eul-1"],
        )
        prop = Property(
            region="서울 관악구 신림동",
            building_type=building_type,
            is_collective=True,
            land_right_unregistered=False,
            separate_land_registry=False,
        )
        grade = Grade(
            level=grade_level,
            deciders=deciders,
            unknowns=[u.code for u in unknowns],
            rule_version="2026.09.1",
        )
        check = SignalCheck(
            grade=grade,
            signals=signals,
            checked=[
                ChecklistItem(
                    code="infringement",
                    label="권리침해 등기",
                    result=CheckResult.ok,
                    entry_ids=[],
                )
            ],
            unknowns=unknowns,
        )
        return ReportInput(
            rights=rights,
            check=check,
            property=prop,
            deposit_manwon=deposit_manwon,
            contract_type=ContractType.jeonse,
            answers={},
            entries=entries,
            use_model=use_model,
        )

    return _create


@pytest.mark.asyncio
async def test_pick_todos_rules(make_report_input, db_session: AsyncSession):
    """pick_todos 규칙 및 정렬 순서 검증."""
    # 1. 시세 확인 못 함 -> 계약 전 첫 할 일이 시세 확인
    inp_unknown_price = make_report_input(
        unknowns=[
            UnknownItem(
                code="trade_price",
                reason=UnknownReason.lookup_failed,
                how_to_check="인근 부동산 시세를 직접 확인하세요",
            )
        ]
    )
    service = ReportService(session=db_session, citation_service=CitationService(db_session))
    todos = service.pick_todos(inp_unknown_price)

    assert len(todos) > 0
    assert todos[0].stage == TodoStage.before
    assert todos[0].title.startswith("시세를 직접 확인하세요")
    assert "시세" in todos[0].because[0]

    # 2. 다가구 주택 -> 확정일자 부여현황 및 전입세대확인서 포함
    inp_multi = make_report_input(building_type=BuildingType.multi_household)
    todos_multi = service.pick_todos(inp_multi)
    titles_multi = [t.title for t in todos_multi]
    assert any("확정일자 부여현황" in t for t in titles_multi)
    assert any("전입세대확인서" in t for t in titles_multi)

    # 3. 아파트 (unknown에 위반건축물 없음) -> 위반건축물 확인이 없음
    inp_apt = make_report_input(building_type=BuildingType.apartment)
    todos_apt = service.pick_todos(inp_apt)
    assert not any("위반건축물" in t.title for t in todos_apt)

    # 4. 보증금 800만원 -> 계약 직후 미납세 열람(1000만원 초과) 없음
    inp_small_deposit = make_report_input(deposit_manwon=800)
    todos_small = service.pick_todos(inp_small_deposit)
    assert not any("계약 직후 동의 없이 미납세를 열람" in t.title for t in todos_small)


@pytest.mark.asyncio
async def test_pick_clauses_rules(make_report_input, db_session: AsyncSession):
    """pick_clauses 규칙 및 빈칸 채우기 검증."""
    # 법인 근저당권자
    inp_corp = make_report_input(
        deposit_manwon=15000,
        signals=[
            RiskSignal(
                code="frequent_transfer",
                severity=Severity.caution,
                label="잦은 소유권 이전",
                source="등기부",
                entry_ids=["gap-2"],
                source_date=date(2026, 9, 1),
            )
        ],
    )
    service = ReportService(session=db_session, citation_service=CitationService(db_session))
    clauses = service.pick_clauses(inp_corp)
    titles = [c.title for c in clauses]

    assert "담보권 설정 금지" in titles
    assert "위반 시 계약 해제" in titles
    assert "잔금일 근저당 말소 조건" in titles
    assert "소유권 변경 즉시 통지" in titles
    assert "미납세 열람 동의" in titles

    # 근저당 특약 빈칸 채워짐 확인
    mortgage_clause = next(c for c in clauses if c.title == "잔금일 근저당 말소 조건")
    assert "우리은행" in mortgage_clause.body
    assert "7,000만원" in mortgage_clause.body
    assert mortgage_clause.filled["mortgagee"] == "우리은행"

    # 개인 근저당권자일 때 개인 이름 미노출 ("근저당권자"로 표기)
    personal_entry = RegistryEntry(
        entry_id="eul-2",
        rank_no="2",
        purpose_code=PurposeCode.mortgage,
        received_at=date(2021, 1, 1),
        amount_manwon=5000,
        price_manwon=None,
        holder="홍길동",
        holder_is_corporation=False,
        cancelled=False,
        document_id="doc-1",
        block_ids=["blk-2"],
        location_label="을구 2번",
        section=Section.eul,
    )
    inp_personal = make_report_input(entries=[personal_entry])
    clauses_personal = service.pick_clauses(inp_personal)
    m_clause_personal = next(c for c in clauses_personal if c.title == "잔금일 근저당 말소 조건")
    assert "홍길동" not in m_clause_personal.body
    assert "근저당권자" in m_clause_personal.body
    assert m_clause_personal.filled["mortgagee"] == "근저당권자"


@pytest.mark.asyncio
async def test_template_sentences(make_report_input, db_session: AsyncSession):
    """template_sentences 생성 및 근거 표식 확인."""
    service = ReportService(session=db_session, citation_service=CitationService(db_session))

    # 1. 위험 등급 -> 결론에 결정 신호 표식
    inp_danger = make_report_input(
        grade_level=GradeLevel.danger,
        deciders=["senior_heavy"],
        signals=[
            RiskSignal(
                code="senior_heavy",
                severity=Severity.danger,
                label="선순위 채권 과다",
                source="HUG",
                entry_ids=["eul-1"],
                source_date=date(2026, 9, 1),
            )
        ],
    )
    s_danger = service.template_sentences(inp_danger)
    assert "보증금 1.5억을 넣기엔 위험합니다" in s_danger.conclusion
    assert "{{entry:eul-1}}" in s_danger.conclusion
    assert "senior_heavy" in s_danger.explanations

    # 2. 안전 등급 및 신호 0개 -> 물어볼 것 3개 (common에서 채워짐)
    inp_safe = make_report_input(
        grade_level=GradeLevel.safe,
        deciders=[],
        signals=[],
        unknowns=[],
    )
    s_safe = service.template_sentences(inp_safe)
    assert "큰 위험이 보이지 않습니다" in s_safe.conclusion
    assert len(s_safe.questions) == 3


@pytest.mark.asyncio
async def test_write_and_get_lifecycle(make_report_input, db_session: AsyncSession):
    """write -> get -> revision 증가 라이프사이클 테스트."""
    review_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    rev_uuid = uuid.UUID(review_id)
    doc_uuid = uuid.UUID(doc_id)

    # 1. 검토 세션 및 문서 데이터베이스에 등록
    await db_session.execute(
        insert(Review).values(
            id=rev_uuid,
            status="done",
            deposit_manwon=15000,
            contract_type="jeonse",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    await db_session.execute(
        insert(RegistryExtract).values(
            id=doc_uuid,
            review_id=rev_uuid,
            kind="collective",
            label="등기부",
            page_count=2,
            file_sha256="test-sha256",
            html="<p>등기부</p>",
            warnings=[],
        )
    )
    await db_session.execute(
        insert(RegistryEntryRow).values(
            entry_id="eul-1",
            review_id=rev_uuid,
            extract_id=doc_uuid,
            section=Section.eul.value,
            rank_no="1",
            purpose_code=PurposeCode.mortgage.value,
            purpose_text="근저당권설정",
            amount_manwon=7000,
            location_label="을구 1번",
            block_ids=["blk-1"],
            cancelled=False,
        )
    )
    await db_session.commit()

    reg_service = RegistryService()
    cite_service = CitationService(session=db_session, registry_service=reg_service)
    service = ReportService(
        session=db_session,
        citation_service=cite_service,
        sentence_writer=None,  # 템플릿 사용
    )

    inp = make_report_input(
        entries=[
            RegistryEntry(
                entry_id="eul-1",
                rank_no="1",
                purpose_code=PurposeCode.mortgage,
                received_at=date(2020, 1, 1),
                amount_manwon=7000,
                price_manwon=None,
                holder="우리은행",
                holder_is_corporation=True,
                cancelled=False,
                document_id=doc_id,
                block_ids=["blk-1"],
                location_label="을구 1번",
                section=Section.eul,
            )
        ]
    )

    # 2. 첫 번째 작성
    res1 = await service.write(review_id, inp)
    assert res1.revision_no == 1
    assert await service.exists(review_id) is True

    # 3. get 호출 및 인용 매핑 확인
    rep1 = await service.get(review_id)
    assert rep1.revision_no == 1
    assert len(rep1.signals) > 0
    # 신호 eul-1에 대한 인용이 매핑되었는지 확인
    signal_cites = rep1.signals[0].citations
    assert len(signal_cites) > 0
    assert signal_cites[0].document_id == doc_id

    # 4. 두 번째 작성 -> revision_no 2
    res2 = await service.write(review_id, inp, revision_reason="직접 입력")
    assert res2.revision_no == 2
    rep2 = await service.get(review_id)
    assert rep2.revision_no == 2
    assert rep2.revision_reason == "직접 입력"


@pytest.mark.asyncio
async def test_write_llm_contradiction_and_fallback(
    make_report_input, db_session: AsyncSession
):
    """LLM 결론 문장 모순 시 템플릿 대체 및 실패 시 fallback 테스트."""
    review_id = str(uuid.uuid4())
    rev_uuid = uuid.UUID(review_id)
    await db_session.execute(
        insert(Review).values(
            id=rev_uuid,
            status="done",
            deposit_manwon=15000,
            contract_type="jeonse",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    await db_session.commit()

    cite_service = CitationService(session=db_session)

    # 1. 모순 문장 (허용 목록에 없는 3억 근저당 문구)
    fake_writer = FakeSentenceWriter(
        conclusion="보증금을 넣기엔 위험합니다. 근저당이 3억 원이나 있습니다.",
    )
    service = ReportService(
        session=db_session,
        citation_service=cite_service,
        sentence_writer=fake_writer,
    )
    inp = make_report_input()
    res = await service.write(review_id, inp)

    # factcheck.contradicts 로 인해 결론이 base로 치환되고 corrections가 1 이상이어야 함
    assert res.corrections >= 1
    rep = await service.get(review_id)
    assert "3억" not in rep.conclusion.text

    # 2. LLM 호출 실패 시 fallback
    failing_writer = FakeSentenceWriter(should_fail=True)
    service_fail = ReportService(
        session=db_session,
        citation_service=cite_service,
        sentence_writer=failing_writer,
    )
    res_fail = await service_fail.write(review_id, inp)
    assert res_fail.llm_fallback is True

    # 3. use_model=False 면 writer 호출 안 함
    clean_writer = FakeSentenceWriter()
    service_no_model = ReportService(
        session=db_session,
        citation_service=cite_service,
        sentence_writer=clean_writer,
    )
    inp_no_model = make_report_input(use_model=False)
    res_no_model = await service_no_model.write(review_id, inp_no_model)
    assert clean_writer.call_count == 0
    assert res_no_model.llm_fallback is True


@pytest.mark.asyncio
async def test_shareable_and_delete(make_report_input, db_session: AsyncSession):
    """shareable 사본 마스킹 및 delete_for_review 검증."""
    review_id = str(uuid.uuid4())
    rev_uuid = uuid.UUID(review_id)
    await db_session.execute(
        insert(Review).values(
            id=rev_uuid,
            status="done",
            deposit_manwon=15000,
            contract_type="jeonse",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    await db_session.commit()

    cite_service = CitationService(session=db_session)
    service = ReportService(session=db_session, citation_service=cite_service)

    inp = make_report_input()
    await service.write(review_id, inp)

    # 1. shareable 조회
    shared = await service.shareable(review_id)
    assert len(shared.report.clauses) == 0
    assert len(shared.report.questions_to_ask) == 0
    assert "{{c" not in shared.report.conclusion.text
    for s in shared.report.signals:
        assert len(s.citations) == 0

    # 2. delete_for_review
    await service.delete_for_review(review_id)
    assert await service.exists(review_id) is False
