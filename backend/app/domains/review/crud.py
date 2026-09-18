"""Review 도메인 CRUD (DB 접근).

근거: JSD-DOM-002 4.1, JSD-MS-001, JSD-DOM-003
"""

from datetime import datetime
from typing import Any
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.review.models import (
    FollowUpTurn,
    QuestionRow,
    Review,
    ReviewRecord,
)


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    return val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))


async def create_review(
    session: AsyncSession,
    deposit_manwon: int,
    contract_type: str,
    counterparty_name: str | None,
    sample_id: str | None,
    facts: dict[str, Any],
    parsed_pages: int,
    cost_krw: int,
    expires_at: datetime,
) -> Review:
    """새 Review 행을 삽입한다."""
    review = Review(
        status="created",
        deposit_manwon=deposit_manwon,
        contract_type=contract_type,
        counterparty_name=counterparty_name,
        sample_id=sample_id,
        facts=facts,
        tool_calls=0,
        tokens_in=0,
        tokens_out=0,
        parsed_pages=parsed_pages,
        cost_krw=cost_krw,
        llm_cost_krw=0,
        corrections=0,
        expires_at=expires_at,
    )
    session.add(review)
    await session.flush()
    return review


async def get_review(
    session: AsyncSession, review_id: str | uuid.UUID
) -> Review | None:
    """Review 행을 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = select(Review).where(Review.id == r_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_review_for_update(
    session: AsyncSession, review_id: str | uuid.UUID
) -> Review | None:
    """행 잠금(FOR UPDATE)을 걸고 Review를 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = select(Review).where(Review.id == r_id).with_for_update()
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_review_status(
    session: AsyncSession, review_id: str | uuid.UUID
) -> str | None:
    """Review의 status 열만 조회한다 (require_live 판정용)."""
    r_id = _to_uuid(review_id)
    stmt = select(Review.status).where(Review.id == r_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def count_questions(
    session: AsyncSession, review_id: str | uuid.UUID
) -> int:
    """이 검토에 등록된 질문 수를 센다."""
    r_id = _to_uuid(review_id)
    stmt = select(func.count(QuestionRow.id)).where(QuestionRow.review_id == r_id)
    res = await session.execute(stmt)
    return res.scalar_one() or 0


async def get_latest_pending_question(
    session: AsyncSession, review_id: str | uuid.UUID
) -> QuestionRow | None:
    """가장 최근의 대기 중(pending) 질문을 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        select(QuestionRow)
        .where(
            QuestionRow.review_id == r_id,
            QuestionRow.status == "pending",
        )
        .order_by(QuestionRow.asked_at.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def count_follow_up_turns(
    session: AsyncSession, review_id: str | uuid.UUID
) -> int:
    """이 검토의 되묻기 차례 수를 센다."""
    r_id = _to_uuid(review_id)
    stmt = select(func.count(FollowUpTurn.id)).where(FollowUpTurn.review_id == r_id)
    res = await session.execute(stmt)
    return res.scalar_one() or 0


async def get_max_seq(
    session: AsyncSession, review_id: str | uuid.UUID
) -> int:
    """검토의 현재 최대 메시지 seq 번호를 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = select(func.coalesce(func.max(ReviewRecord.seq), 0)).where(
        ReviewRecord.review_id == r_id
    )
    res = await session.execute(stmt)
    return res.scalar_one() or 0


async def insert_review_record(
    session: AsyncSession,
    record_id: uuid.UUID,
    review_id: str | uuid.UUID,
    seq: int,
    role: str,
    kind: str,
    text: str,
    data: dict[str, Any] | None = None,
    turn_id: int | None = None,
) -> ReviewRecord:
    """대화 메시지 행 하나를 삽입한다."""
    r_id = _to_uuid(review_id)
    rec = ReviewRecord(
        id=record_id,
        review_id=r_id,
        seq=seq,
        role=role,
        kind=kind,
        text=text,
        data=data,
        turn_id=turn_id,
    )
    session.add(rec)
    await session.flush()
    return rec
