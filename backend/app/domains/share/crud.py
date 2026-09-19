"""Share 도메인 DB 접근 모듈 (shared_opinions 테이블).

근거: JSD-DOM-002 4.9, JSD-DOM-003 shared_opinions, JSD-MS-009
"""

from datetime import datetime
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.share.models import SharedOpinion


async def insert_shared_opinion(
    session: AsyncSession,
    token: str,
    report: dict[str, Any],
    subject: dict[str, Any],
    expires_at: datetime,
) -> SharedOpinion:
    """공유 의견서를 생성한다."""
    row = SharedOpinion(
        token=token,
        report=report,
        subject=subject,
        expires_at=expires_at,
    )
    session.add(row)
    await session.flush()
    return row


async def get_shared_opinion_by_token(
    session: AsyncSession,
    token: str,
) -> SharedOpinion | None:
    """토큰으로 공유 의견서를 조회한다."""
    stmt = select(SharedOpinion).where(SharedOpinion.token == token)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def purge_expired_shared_opinions(
    session: AsyncSession,
    now: datetime,
) -> int:
    """만료된 공유 의견서의 본문과 대상을 비운다 (행은 410 gone을 위해 유지)."""
    stmt = (
        update(SharedOpinion)
        .where(
            SharedOpinion.expires_at < now,
            SharedOpinion.report.isnot(None),
        )
        .values(report=None, subject=None)
    )
    res = await session.execute(stmt)
    return res.rowcount
