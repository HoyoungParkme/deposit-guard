"""gate 도메인 서비스 단위 테스트.

항목 ID: JSD-MS-011#gate.check_file, JSD-MS-011#gate.take_quota, JSD-MS-011#gate.cached_html, JSD-MS-011#gate.remember_html
"""

from datetime import date, timedelta
from io import BytesIO
import pytest
from pypdf import PdfWriter
from sqlalchemy import select

from app.core.config import LIMITS
from app.core.errors import AppError
from app.domains.gate.models import IpQuota
from app.domains.gate.service import cached_html, check_file, remember_html, take_quota
from app.shared.types import Upload


def _make_pdf_bytes(page_count: int = 1, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=100, height=100)
    if password:
        writer.encrypt(password)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_check_file_valid_pdf():
    """정상 PDF 검사."""
    pdf_bytes = _make_pdf_bytes(2)
    upload = Upload(data=pdf_bytes, media_type="application/pdf", filename="test.pdf")
    res = check_file(upload)
    assert res.page_count == 2
    assert res.media_type == "application/pdf"
    assert len(res.file_sha256) == 64


def test_check_file_fake_pdf():
    """확장자만 PDF인 일반 텍스트는 거부."""
    upload = Upload(data=b"not a pdf at all", media_type="application/pdf", filename="test.pdf")
    with pytest.raises(AppError) as exc_info:
        check_file(upload)
    assert exc_info.value.code == "invalid_file"


def test_check_file_encrypted_pdf():
    """암호 걸린 PDF는 거부."""
    pdf_bytes = _make_pdf_bytes(1, password="secret")
    upload = Upload(data=pdf_bytes, media_type="application/pdf", filename="secret.pdf")
    with pytest.raises(AppError) as exc_info:
        check_file(upload)
    assert exc_info.value.code == "invalid_file"


def test_check_file_too_many_pages():
    """LIMITS.pages 초과 PDF는 거부."""
    pdf_bytes = _make_pdf_bytes(LIMITS.pages + 1)
    upload = Upload(data=pdf_bytes, media_type="application/pdf", filename="large.pdf")
    with pytest.raises(AppError) as exc_info:
        check_file(upload)
    assert exc_info.value.code == "invalid_file"


def test_check_file_image():
    """PNG/JPEG 이미지는 1페이지로 통과."""
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    upload = Upload(data=png_bytes, media_type="image/png", filename="test.png")
    res = check_file(upload)
    assert res.page_count == 1
    assert res.media_type == "image/png"


@pytest.mark.asyncio
async def test_take_quota_sample_free(db_session):
    """예시 케이스는 쿼터를 차감하지 않는다."""
    today = date(2026, 9, 18)
    await take_quota("1.2.3.4", "sha256_dummy", is_sample=True, today=today)
    res = await db_session.execute(select(IpQuota))
    assert res.fetchall() == []


@pytest.mark.asyncio
async def test_take_quota_rate_limiting(db_session):
    """5회까지 성공하고 6번째 요청은 rate_limited 예외 발생."""
    today = date(2026, 9, 18)
    client_ip = "192.168.1.100"

    for i in range(LIMITS.ip_daily):
        await take_quota(client_ip, f"hash_{i}", is_sample=False, today=today)

    with pytest.raises(AppError) as exc_info:
        await take_quota(client_ip, "hash_extra", is_sample=False, today=today)
    assert exc_info.value.code == "rate_limited"

    # 다음 날이면 다시 허용
    tomorrow = today + timedelta(days=1)
    await take_quota(client_ip, "hash_next_day", is_sample=False, today=tomorrow)


@pytest.mark.asyncio
async def test_cached_and_remember_html(db_session):
    """remember_html로 저장하고 cached_html로 조회."""
    file_sha256 = "test_sha256_abc123"
    html_content = "<div>등기부 내용</div>"

    # 아직 없으면 None
    cached = await cached_html(file_sha256)
    assert cached is None

    # 저장
    await remember_html(
        file_sha256=file_sha256,
        html=html_content,
        page_count=2,
        is_sample=False,
    )

    # 조회
    cached = await cached_html(file_sha256)
    assert cached is not None
    assert cached.html == html_content
    assert cached.page_count == 2
    assert cached.billed_pages == 0
