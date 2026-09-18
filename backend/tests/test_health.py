"""health 엔드포인트 및 서비스 단위 테스트.

근거: JSD-MS-012, JSD-API-001 GET/health
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.core.health import Health, HealthService
from app.main import app


@pytest.mark.asyncio
async def test_health_service_ok():
    """테스트 관점: DB 정상이면 status ok, db ok."""
    with patch("app.core.health.async_session_factory") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value = None

        h = await HealthService.check()
        assert h.status == "ok"
        assert h.db == "ok"


@pytest.mark.asyncio
async def test_health_service_degraded_no_leak():
    """테스트 관점: DB 실패 시 degraded, db fail 반환 및 예외 문자열 노출 없음."""
    with patch("app.core.health.async_session_factory") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        mock_session.execute.side_effect = Exception("sensitive-connection-string-leak")

        h = await HealthService.check()
        assert h.status == "degraded"
        assert h.db == "fail"
        # 연결 문자열 누출 확인
        assert "sensitive" not in str(h)


@pytest.mark.asyncio
async def test_health_api_200():
    """테스트 관점: /health 200 반환."""
    with patch.object(
        HealthService,
        "check",
        return_value=Health(status="ok", db="ok", version="0.1.0"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["db"] == "ok"
            assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_api_503():
    """테스트 관점: /health 503 반환."""
    with patch.object(
        HealthService,
        "check",
        return_value=Health(status="degraded", db="fail", version="0.1.0"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "degraded"
            assert data["db"] == "fail"
