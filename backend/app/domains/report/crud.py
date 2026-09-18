"""Report 도메인 DB 접근 모듈 (opinions 테이블).

근거: JSD-DOM-002 4.8, JSD-DOM-003 opinions, JSD-MS-008
"""

import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.report.models import Opinion


async def upsert_opinion(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    body: dict[str, Any],
    subject: dict[str, Any],
    revision_no: int,
    revision_reason: str | None,
    written_at: datetime,
) -> Opinion:
    """의견서를 생성하거나 업데이트한다 (on conflict do update)."""
    rev_uuid = uuid.UUID(str(review_id)) if isinstance(review_id, str) else review_id

    stmt = (
        insert(Opinion)
        .values(
            review_id=rev_uuid,
            body=body,
            subject=subject,
            revision_no=revision_no,
            revision_reason=revision_reason,
            written_at=written_at,
        )
        .on_conflict_do_update(
            index_elements=[Opinion.review_id],
            set_={
                "body": body,
                "subject": subject,
                "revision_no": revision_no,
                "revision_reason": revision_reason,
                "written_at": written_at,
            },
        )
        .returning(Opinion)
    )
    res = await session.execute(stmt)
    return res.scalar_one()


async def get_opinion(
    session: AsyncSession,
    review_id: str | uuid.UUID,
) -> Opinion | None:
    """검토의 의견서를 조회한다."""
    rev_uuid = uuid.UUID(str(review_id)) if isinstance(review_id, str) else review_id
    stmt = select(Opinion).where(Opinion.review_id == rev_uuid)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def exists_opinion(
    session: AsyncSession,
    review_id: str | uuid.UUID,
) -> bool:
    """의견서 존재 여부를 확인한다."""
    rev_uuid = uuid.UUID(str(review_id)) if isinstance(review_id, str) else review_id
    stmt = select(func.count(Opinion.id)).where(Opinion.review_id == rev_uuid)
    res = await session.execute(stmt)
    return (res.scalar_one() or 0) > 0


async def get_revision_no(
    session: AsyncSession,
    review_id: str | uuid.UUID,
) -> int | None:
    """이전 판 번호를 조회한다."""
    rev_uuid = uuid.UUID(str(review_id)) if isinstance(review_id, str) else review_id
    stmt = select(Opinion.revision_no).where(Opinion.review_id == rev_uuid)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def delete_opinion(
    session: AsyncSession,
    review_id: str | uuid.UUID,
) -> None:
    """검토의 의견서를 삭제한다."""
    rev_uuid = uuid.UUID(str(review_id)) if isinstance(review_id, str) else review_id
    stmt = delete(Opinion).where(Opinion.review_id == rev_uuid)
    await session.execute(stmt)
