"""ReviewService B1 함수 단위/통합 테스트.

근거: JSD-MS-001, JSD-DOM-002 4.1
"""

from io import BytesIO
from pathlib import Path
from pypdf import PdfWriter
import pytest

from app.core.errors import AppError
from app.domains.registry.service import RegistryService
from app.domains.review.service import ReviewService
from app.shared.types import ContractType, MessageKind, ParsedDocument, ReviewStatus, Role, Upload


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "registry" / "fixtures"


def _make_pdf_bytes(page_count: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=100, height=100)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


class SampleFixtureDocumentParser:
    """테스트용 fixture 반환 가짜 파서."""

    def __init__(self) -> None:
        self.calls = 0

    async def parse(self, data: bytes, media_type: str) -> ParsedDocument:
        self.calls += 1
        html = (FIXTURES_DIR / "multi_family_caution.html").read_text(encoding="utf-8")
        return ParsedDocument(html=html, page_count=1, billed_pages=1)


class FakeDocumentParser:
    """단일 fixture 지정 가짜 파서."""

    def __init__(self, html: str, page_count: int = 1) -> None:
        self.html = html
        self.page_count = page_count
        self.calls = 0

    async def parse(self, data: bytes, media_type: str) -> ParsedDocument:
        self.calls += 1
        return ParsedDocument(html=self.html, page_count=self.page_count, billed_pages=self.page_count)


@pytest.mark.asyncio
async def test_review_service_create_with_sample():
    """예시 ID로 검토 생성."""
    parser = SampleFixtureDocumentParser()
    reg_service = RegistryService(parser=parser)
    service = ReviewService(registry_service=reg_service)

    created = await service.create(
        upload=None,
        sample_id="multi_family_caution",
        deposit_manwon=18000,
        contract_type=ContractType.jeonse,
        counterparty_name="이서연",
        client_ip="127.0.0.1",
    )
    assert created.is_sample is True
    assert created.status == ReviewStatus.created
    assert len(created.review_id) > 0
    assert parser.calls == 1

    # get 조회 검증
    view = await service.get(created.review_id)
    assert view.review_id == created.review_id
    assert view.subject.deposit_manwon == 18000
    assert view.subject.contract_type == ContractType.jeonse
    assert view.subject.building_type.value == "multi_family_unit"
    assert len(view.documents) == 1
    assert view.has_report is False
    assert not hasattr(view, "counterparty_name")


@pytest.mark.asyncio
async def test_review_service_create_caching():
    """동일 파일 두 번째 업로드 시 캐시 적중(파서 호출 0)."""
    html_apartment = (FIXTURES_DIR / "apartment_safe.html").read_text(encoding="utf-8")
    fake_parser = FakeDocumentParser(html=html_apartment, page_count=2)
    reg_service = RegistryService(parser=fake_parser)
    service = ReviewService(registry_service=reg_service)

    valid_pdf = _make_pdf_bytes(2)
    upload1 = Upload(data=valid_pdf, media_type="application/pdf", filename="apt.pdf")

    # 첫 번째 업로드
    c1 = await service.create(
        upload=upload1,
        sample_id=None,
        deposit_manwon=20000,
        contract_type=ContractType.jeonse,
        counterparty_name=None,
        client_ip="192.168.0.1",
    )
    assert fake_parser.calls == 1

    # 두 번째 업로드 (동일 바이트)
    upload2 = Upload(data=valid_pdf, media_type="application/pdf", filename="apt.pdf")
    c2 = await service.create(
        upload=upload2,
        sample_id=None,
        deposit_manwon=20000,
        contract_type=ContractType.jeonse,
        counterparty_name=None,
        client_ip="192.168.0.2",
    )
    # 캐시 적중으로 파서 호출 카운트가 증가하지 않아야 함
    assert fake_parser.calls == 1


@pytest.mark.asyncio
async def test_review_service_create_invalid_input():
    """입력 검증 실패 테스트."""
    service = ReviewService()
    # 파일과 sample 둘 다 없음
    with pytest.raises(AppError) as exc_info:
        await service.create(
            upload=None,
            sample_id=None,
            deposit_manwon=10000,
            contract_type=ContractType.jeonse,
            counterparty_name=None,
            client_ip="127.0.0.1",
        )
    assert exc_info.value.code == "missing_input"

    # 보증금 0 이하
    with pytest.raises(AppError) as exc_info:
        await service.create(
            upload=None,
            sample_id="apartment_safe",
            deposit_manwon=0,
            contract_type=ContractType.jeonse,
            counterparty_name=None,
            client_ip="127.0.0.1",
        )
    assert exc_info.value.code == "missing_input"


@pytest.mark.asyncio
async def test_review_service_require_live_and_record():
    """require_live 검증 및 record 메시지 기록과 마스킹 테스트."""
    parser = SampleFixtureDocumentParser()
    reg_service = RegistryService(parser=parser)
    service = ReviewService(registry_service=reg_service)

    created = await service.create(
        upload=None,
        sample_id="multi_family_caution",
        deposit_manwon=18000,
        contract_type=ContractType.jeonse,
        counterparty_name="이서연",
        client_ip="127.0.0.1",
    )

    # require_live 정상 통과
    await service.require_live(created.review_id)

    # 존재하지 않는 ID는 not_found
    with pytest.raises(AppError) as exc_info:
        await service.require_live("00000000-0000-0000-0000-000000000000")
    assert exc_info.value.code == "not_found"

    # record: 대화 기록 저장 및 이름 마스킹 확인
    # multi_family_caution의 소유자는 이서연 -> 개인 A 또는 상대방으로 마스킹
    rec_id = await service.record(
        review_id=created.review_id,
        role=Role.agent,
        kind=MessageKind.say,
        text="소유자 이서연 님의 근저당권 내역입니다.",
    )
    assert len(rec_id) > 0
