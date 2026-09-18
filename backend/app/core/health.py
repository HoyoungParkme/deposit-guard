"""헬스체크 서비스.

근거: JSD-DOM-002 4.12, JSD-MS-012, JSD-API-001 GET/health
규칙: DB SELECT 1을 2초 타임아웃으로 확인. 예외 문자열을 노출하지 않는다.
"""

import asyncio
from dataclasses import dataclass
from sqlalchemy import text

from app.core.config import settings
from app.core.db import async_session_factory


@dataclass(frozen=True)
class Health:
    """헬스체크 응답 DTO (JSD-DOM-002 2.8)."""

    status: str
    db: str
    version: str | None = None


class HealthService:
    """DB 연결 확인 서비스."""

    @staticmethod
    async def check() -> Health:
        """DB 연결 확인.

        항목 ID: JSD-MS-012#HealthService.check
        근거: JSD-API-001#GET/health, JSD-SEQ-001#SEQ-C1
        """
        try:
            async with async_session_factory() as session:
                # 2초 제한으로 SELECT 1 실행
                await asyncio.wait_for(
                    session.execute(text("SELECT 1")),
                    timeout=2.0,
                )
            return Health(
                status="ok",
                db="ok",
                version=settings.APP_VERSION,
            )
        except Exception:
            # 예외 문자열은 절대 담지 않고 degraded/fail만 반환
            return Health(
                status="degraded",
                db="fail",
                version=settings.APP_VERSION,
            )
