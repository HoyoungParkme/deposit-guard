"""error 봉투 및 예외 처리 테스트.

근거: JSD-API-001 2장, JSD-DOM-002 4.14
"""

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.core.errors import AppError, app_error_handler, unhandled_error_handler

dummy_error_app = FastAPI()
dummy_error_app.add_exception_handler(AppError, app_error_handler)  # type: ignore
dummy_error_app.add_exception_handler(Exception, unhandled_error_handler)  # type: ignore


@dummy_error_app.get("/trigger-app-error")
async def trigger_app_error():
    raise AppError(code="invalid_file", field="file")


@dummy_error_app.get("/trigger-internal-error")
async def trigger_internal_error():
    raise ValueError("sensitive internal db password failure")


@pytest.mark.asyncio
async def test_app_error_envelope():
    """테스트 관점: AppError 에러 봉투 구조 및 상태 코드."""
    transport = ASGITransport(app=dummy_error_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/trigger-app-error")
        assert resp.status_code == 400
        data = resp.json()
        assert data["code"] == "invalid_file"
        assert "형식" in data["detail"]
        assert data["field"] == "file"


@pytest.mark.asyncio
async def test_unhandled_error_no_exception_leak():
    """테스트 관점: 예상 밖 예외 시 예외 문자열이 응답에 절대 노출되지 않음."""
    transport = ASGITransport(app=dummy_error_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/trigger-internal-error")
        assert resp.status_code == 500
        data = resp.json()
        assert data["code"] == "internal"
        # 민감한 예외 문자열 노출 차단 확인
        assert "sensitive" not in data["detail"]
        assert "password" not in data["detail"]
