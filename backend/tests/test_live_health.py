"""실제 DB 연동 헬스체크 테스트.

근거: JSD-CODE-001 슬라이스 A 테스트 관점
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.health import HealthService
from app.main import app


@pytest.mark.asyncio
async def test_live_db_health():
    """실제 구동 중인 DB를 대상으로 한 HealthService.check 및 /health 엔드포인트 검증."""
    health = await HealthService.check()
    assert health.status == "ok"
    assert health.db == "ok"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"
        assert data["version"] == "0.1.0"
