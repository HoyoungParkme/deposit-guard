"""Pytest 공통 fixture.

근거: JSD-DOM-002 1장 tests/
"""

from collections.abc import AsyncGenerator
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """테스트용 비동기 DB 세션 fixture."""
    async with async_session_factory() as session:
        yield session
        # 테스트 종료 후 생성된 데이터 정리
        await session.execute(
            text(
                "TRUNCATE ip_quotas, file_caches, review_records, questions, "
                "follow_up_turns, usage_logs, registry_entries, registry_extracts, "
                "reviews CASCADE"
            )
        )
        await session.commit()
