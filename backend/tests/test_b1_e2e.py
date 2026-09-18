"""슬라이스 B1 E2E 통합 테스트.

근거: JSD-CODE-001 B1 테스트 관점:
- 예시 카드 선택 → 검토 시작 201 → 검토 화면에 문서 탭과 원문
- 같은 예시 두 번째는 업스테이지 가짜 호출 0
- 등기부가 아닌 PDF → 400, 행 없음
- 여섯 번째 업로드 → 429
- GET /api/samples
"""

from io import BytesIO
from pathlib import Path
import pytest
import httpx
from pypdf import PdfWriter

from app.core.config import LIMITS
from app.domains.registry.ports import DocumentParser
from app.domains.registry.service import RegistryService
from app.domains.review.router import router as review_router
from app.domains.review.service import ReviewService
from app.main import app
from app.shared.types import ParsedDocument


FIXTURES_DIR = Path(__file__).resolve().parent / "registry" / "fixtures"


def _make_pdf_bytes(page_count: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=100, height=100)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TrackingFixtureParser:
    """호출 횟수를 추적하며 fixture HTML을 반환하는 가짜 파서."""

    def __init__(self) -> None:
        self.calls = 0

    async def parse(self, data: bytes, media_type: str) -> ParsedDocument:
        self.calls += 1
        html = (FIXTURES_DIR / "multi_family_caution.html").read_text(encoding="utf-8")
        return ParsedDocument(html=html, page_count=1, billed_pages=1)


@pytest.fixture
def tracking_parser() -> TrackingFixtureParser:
    return TrackingFixtureParser()


from app.domains.registry.router import get_registry_service
from app.domains.review.router import get_review_service


@pytest.fixture(autouse=True)
def override_parser_dependency(tracking_parser: TrackingFixtureParser):
    """테스트 시 ReviewService와 RegistryService에 tracking_parser를 주입."""
    mock_reg_service = RegistryService(parser=tracking_parser)
    mock_review_service = ReviewService(registry_service=mock_reg_service)

    app.dependency_overrides[get_registry_service] = lambda: mock_reg_service
    app.dependency_overrides[get_review_service] = lambda: mock_review_service
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_b1_e2e_flow(tracking_parser: TrackingFixtureParser, db_session):
    """예시 카드 선택 -> 검토 시작 201 -> 문서 탭과 원문 확인 E2E 플로우."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 예시 목록 조회
        res_samples = await client.get("/api/samples")
        assert res_samples.status_code == 200
        samples_data = res_samples.json()["samples"]
        assert len(samples_data) == 3
        sample = next(s for s in samples_data if s["sample_id"] == "multi_family_caution")

        # 2. 첫 번째 검토 시작 (예시 카드 선택)
        res_create = await client.post(
            "/api/reviews",
            data={
                "sample_id": sample["sample_id"],
                "deposit_manwon": 18000,
                "contract_type": "jeonse",
                "counterparty_name": "이서연",
            },
        )
        assert res_create.status_code == 201
        created = res_create.json()
        review_id = created["review_id"]
        assert created["is_sample"] is True
        assert tracking_parser.calls == 1

        # 3. 검토 상태 조회
        res_get = await client.get(f"/api/reviews/{review_id}")
        assert res_get.status_code == 200
        view = res_get.json()
        assert view["review_id"] == review_id
        assert view["subject"]["deposit_manwon"] == 18000
        assert len(view["documents"]) == 1
        doc_id = view["documents"][0]["document_id"]

        # 4. 문서 목록 및 원문 HTML 확인
        res_docs = await client.get(f"/api/reviews/{review_id}/documents")
        assert res_docs.status_code == 200
        assert len(res_docs.json()["documents"]) == 1

        res_html = await client.get(f"/api/reviews/{review_id}/documents/{doc_id}")
        assert res_html.status_code == 200
        assert "text/html" in res_html.headers["content-type"]
        assert "data-block-id" in res_html.text

        # 5. 같은 예시로 두 번째 검토 시작 -> 파서 가짜 호출 0회 증가 (캐시 적중)
        res_create_2 = await client.post(
            "/api/reviews",
            data={
                "sample_id": sample["sample_id"],
                "deposit_manwon": 18000,
                "contract_type": "jeonse",
            },
        )
        assert res_create_2.status_code == 201
        assert tracking_parser.calls == 1  # 여전히 1 (새 호출 0회)


@pytest.mark.asyncio
async def test_b1_e2e_not_registry_pdf(db_session):
    """등기부가 아닌 내용의 PDF -> 400 not_registry."""
    # 파서가 등기부가 아닌 HTML(표 없음)을 반환하는 경우
    class NotRegistryParser:
        async def parse(self, data: bytes, media_type: str) -> ParsedDocument:
            return ParsedDocument(html="<h1>계약서</h1><p>내용</p>", page_count=1, billed_pages=1)

    reg_service = RegistryService(parser=NotRegistryParser())
    review_service = ReviewService(registry_service=reg_service)
    app.dependency_overrides[get_review_service] = lambda: review_service

    valid_pdf = _make_pdf_bytes(1)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/reviews",
            data={"deposit_manwon": 10000, "contract_type": "jeonse"},
            files={"file": ("contract.pdf", valid_pdf, "application/pdf")},
        )
        assert res.status_code == 400
        assert res.json()["code"] == "not_registry"


@pytest.mark.asyncio
async def test_b1_e2e_rate_limit_sixth_upload(tracking_parser: TrackingFixtureParser, db_session):
    """동일 IP에서 여섯 번째 직접 업로드는 429 rate_limited."""
    transport = httpx.ASGITransport(app=app)
    headers = {"X-Forwarded-For": "203.0.113.199"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        # 1~5회 업로드
        for i in range(LIMITS.ip_daily):
            pdf_bytes = _make_pdf_bytes(1)
            res = await client.post(
                "/api/reviews",
                data={"deposit_manwon": 10000, "contract_type": "jeonse"},
                files={"file": (f"test_{i}.pdf", pdf_bytes, "application/pdf")},
            )
            assert res.status_code == 201

        # 6회째 업로드 -> 429
        pdf_bytes = _make_pdf_bytes(1)
        res_six = await client.post(
            "/api/reviews",
            data={"deposit_manwon": 10000, "contract_type": "jeonse"},
            files={"file": ("test_6.pdf", pdf_bytes, "application/pdf")},
        )
        assert res_six.status_code == 429
        assert res_six.json()["code"] == "rate_limited"
