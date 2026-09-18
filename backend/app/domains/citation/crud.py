"""Citation 도메인 데이터베이스 CRUD 연산.

근거: JSD-DOM-002 4.7, JSD-DOM-003 citations, JSD-MS-007
"""

import uuid
import json
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.citation.models import CitationRow


async def count_existing_citations(
    session: AsyncSession, review_id: uuid.UUID, used_in: str, ref: str
) -> int:
    """특정 자리의 기존 인용 수를 계산하여 다음 c{n} 키를 결정한다."""
    stmt = select(func.count(CitationRow.id)).where(
        CitationRow.review_id == review_id,
        CitationRow.used_in == used_in,
        CitationRow.ref == ref,
    )
    res = await session.execute(stmt)
    return res.scalar() or 0


async def insert_citation_row(
    session: AsyncSession,
    review_id: uuid.UUID,
    used_in: str,
    ref: str,
    key: str,
    label: str,
    usage_label: str,
    document_id: uuid.UUID,
    entry_ids: list[str],
    block_ids: list[str],
) -> CitationRow:
    """새 인용 행을 추가한다."""
    row = CitationRow(
        review_id=review_id,
        used_in=used_in,
        ref=ref,
        key=key,
        label=label,
        usage_label=usage_label,
        document_id=document_id,
        entry_ids=entry_ids,
        block_ids=block_ids,
    )
    session.add(row)
    await session.flush()
    return row


async def list_citations_for_messages(
    session: AsyncSession, review_id: uuid.UUID, message_ids: list[str]
) -> list[CitationRow]:
    """메시지들의 인용 목록을 조회한다."""
    if not message_ids:
        return []
    stmt = (
        select(CitationRow)
        .where(
            CitationRow.review_id == review_id,
            CitationRow.used_in == "message",
            CitationRow.ref.in_(message_ids),
        )
        .order_by(CitationRow.ref, CitationRow.id)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def list_citations_for_report(
    session: AsyncSession, review_id: uuid.UUID
) -> list[CitationRow]:
    """의견서의 인용 목록을 조회한다."""
    stmt = (
        select(CitationRow)
        .where(
            CitationRow.review_id == review_id,
            CitationRow.used_in != "message",
        )
        .order_by(CitationRow.id)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def list_citations_for_block(
    session: AsyncSession, review_id: uuid.UUID, block_id: str
) -> list[CitationRow]:
    """원문 block_id를 포함하는 인용 목록을 조회한다."""
    block_arr = json.dumps([block_id])
    stmt = (
        select(CitationRow)
        .where(
            CitationRow.review_id == review_id,
            CitationRow.block_ids.contains([block_id]),
        )
        .order_by(CitationRow.id)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def delete_citations_for_report(
    session: AsyncSession, review_id: uuid.UUID
) -> int:
    """이전 의견서의 인용을 모두 삭제한다."""
    stmt = delete(CitationRow).where(
        CitationRow.review_id == review_id,
        CitationRow.used_in != "message",
    )
    res = await session.execute(stmt)
    return res.rowcount or 0


async def delete_all_citations_for_review(
    session: AsyncSession, review_id: uuid.UUID
) -> int:
    """검토의 모든 인용을 삭제한다."""
    stmt = delete(CitationRow).where(CitationRow.review_id == review_id)
    res = await session.execute(stmt)
    return res.rowcount or 0
