"""UpstageParser 단위 테스트.

항목 ID: JSD-MS-013#UpstageParser.parse
"""

import httpx
import pytest

from app.core.errors import AppError
from app.domains.registry.adapters.upstage import UpstageParser


@pytest.mark.asyncio
async def test_upstage_parser_success():
    """성공적인 HTML 파싱 및 페이지 수 반환."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        assert "document-digitization" in str(request.url)
        return httpx.Response(
            status_code=200,
            json={
                "content": {"html": "<div>등기부 내용</div>"},
                "usage": {"pages": 2},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = UpstageParser(client=client)
        result = await parser.parse(b"%PDF-test", "application/pdf")

    assert call_count == 1
    assert result.html == "<div>등기부 내용</div>"
    assert result.page_count == 2
    assert result.billed_pages == 2


@pytest.mark.asyncio
async def test_upstage_parser_422_no_retry():
    """4xx 에러 시 재시도 없이 즉시 parse_failed."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(status_code=422, json={"error": "unprocessable"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = UpstageParser(client=client)
        with pytest.raises(AppError) as exc_info:
            await parser.parse(b"corrupt data", "application/pdf")

    assert call_count == 1
    assert exc_info.value.code == "parse_failed"


@pytest.mark.asyncio
async def test_upstage_parser_500_retry_and_success():
    """5xx 에러 1회 발생 후 재시도에서 성공."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(status_code=500, text="Internal Server Error")
        return httpx.Response(
            status_code=200,
            json={
                "content": {"html": "<p>성공</p>"},
                "usage": {"pages": 1},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = UpstageParser(client=client)
        result = await parser.parse(b"%PDF-test", "application/pdf")

    assert call_count == 2
    assert result.html == "<p>성공</p>"
    assert result.page_count == 1


@pytest.mark.asyncio
async def test_upstage_parser_empty_html_error():
    """content.html이 빈 문자열이면 parse_failed."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "content": {"html": ""},
                "usage": {"pages": 1},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = UpstageParser(client=client)
        with pytest.raises(AppError) as exc_info:
            await parser.parse(b"%PDF-test", "application/pdf")

    assert exc_info.value.code == "parse_failed"
