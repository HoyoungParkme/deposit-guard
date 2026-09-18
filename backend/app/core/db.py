"""비동기 데이터베이스 엔진 및 세션 관리.

근거: JSD-DOM-002 1장, 4.14, 6장 부록
규칙: hide_parameters=True (바인드 값을 예외 문자열에 싣지 않음)
"""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 비동기 엔진 생성: 바인드 값을 예외 문자열에 남기지 않도록 hide_parameters=True 설정
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    hide_parameters=True,
    future=True,
)

# 비동기 세션 팩토리
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy DeclarativeBase."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 종속성용 비동기 DB 세션 제너레이터."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
