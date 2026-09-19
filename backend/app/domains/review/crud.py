"""Review 도메인 CRUD (DB 접근).

근거: JSD-DOM-002 4.1, JSD-MS-001, JSD-DOM-003
"""

from datetime import datetime, timezone
import json
from typing import Any
import uuid
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.review.models import (
    FollowUpTurn,
    QuestionRow,
    Review,
    ReviewRecord,
)


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    return val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))


def _json_safe(val: Any) -> Any:
    if val is None:
        return None
    return json.loads(json.dumps(val, default=str))


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
        facts=_json_safe(facts) or {},
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
        data=_json_safe(data),
        turn_id=turn_id,
    )
    session.add(rec)
    await session.flush()
    return rec


async def list_review_records(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    after_seq: int = 0,
    limit: int = 200,
) -> list[ReviewRecord]:
    """after_seq 이후의 대화 메시지 행들을 seq 순으로 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        select(ReviewRecord)
        .where(ReviewRecord.review_id == r_id, ReviewRecord.seq > after_seq)
        .order_by(ReviewRecord.seq.asc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def update_review_status_if_created(
    session: AsyncSession, review_id: str | uuid.UUID
) -> int:
    """status가 created일 때만 running으로 변경하고 변경된 행 수를 반환한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        update(Review)
        .where(Review.id == r_id, Review.status == "created")
        .values(status="running")
    )
    res = await session.execute(stmt)
    return res.rowcount


async def update_review_status(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    status: str,
    finished_at: datetime | None = None,
) -> None:
    """Review의 status와 finished_at을 갱신한다."""
    r_id = _to_uuid(review_id)
    values: dict[str, Any] = {"status": status}
    if finished_at is not None:
        values["finished_at"] = finished_at
    stmt = update(Review).where(Review.id == r_id).values(**values)
    await session.execute(stmt)


async def increment_review_tokens_and_cost(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    tokens_in: int,
    tokens_out: int,
    cost_krw: int,
) -> None:
    """Review의 토큰 수와 비용(LLM 비용 포함)을 누적한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        update(Review)
        .where(Review.id == r_id)
        .values(
            tokens_in=Review.tokens_in + tokens_in,
            tokens_out=Review.tokens_out + tokens_out,
            llm_cost_krw=Review.llm_cost_krw + cost_krw,
            cost_krw=Review.cost_krw + cost_krw,
        )
    )
    await session.execute(stmt)


async def increment_review_tool_calls(
    session: AsyncSession, review_id: str | uuid.UUID
) -> None:
    """Review의 tool_calls 카운터를 1 증가시킨다."""
    r_id = _to_uuid(review_id)
    stmt = (
        update(Review)
        .where(Review.id == r_id)
        .values(tool_calls=Review.tool_calls + 1)
    )
    await session.execute(stmt)


async def increment_review_corrections(
    session: AsyncSession, review_id: str | uuid.UUID, count: int = 1
) -> None:
    """Review의 corrections 카운터를 증가시킨다."""
    r_id = _to_uuid(review_id)
    stmt = (
        update(Review)
        .where(Review.id == r_id)
        .values(corrections=Review.corrections + count)
    )
    await session.execute(stmt)


async def update_review_facts(
    session: AsyncSession, review_id: str | uuid.UUID, facts: dict[str, Any]
) -> None:
    """Review의 facts 열을 갱신한다."""
    r_id = _to_uuid(review_id)
    stmt = update(Review).where(Review.id == r_id).values(facts=_json_safe(facts) or {})
    await session.execute(stmt)


async def insert_question(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    asked_no: int,
    kind: str,
    text: str,
    why: str,
    input_type: str,
    options: list[str] | None = None,
    help_url: str | None = None,
) -> QuestionRow:
    """새 Question 행을 삽입한다."""
    r_id = _to_uuid(review_id)
    q = QuestionRow(
        review_id=r_id,
        asked_no=asked_no,
        kind=kind,
        text=text,
        why=why,
        input_type=input_type,
        options=options,
        help_url=help_url,
        status="pending",
    )
    session.add(q)
    await session.flush()
    return q


async def get_question(
    session: AsyncSession,
    question_id: int | str,
    review_id: str | uuid.UUID | None = None,
) -> QuestionRow | None:
    """질문 행을 조회한다."""
    q_id = int(question_id) if isinstance(question_id, str) and question_id.isdigit() else question_id
    stmt = select(QuestionRow).where(QuestionRow.id == q_id)
    if review_id:
        stmt = stmt.where(QuestionRow.review_id == _to_uuid(review_id))
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def update_question_answered(
    session: AsyncSession,
    question_id: int | str,
    answer: str,
    answer_document_id: uuid.UUID | None = None,
) -> None:
    """질문을 답변 완료(answered) 처리한다."""
    q_id = int(question_id) if isinstance(question_id, str) and question_id.isdigit() else question_id
    now = datetime.now(timezone.utc)
    stmt = (
        update(QuestionRow)
        .where(QuestionRow.id == q_id)
        .values(
            status="answered",
            answer=answer,
            answered_at=now,
            answer_document_id=answer_document_id,
        )
    )
    await session.execute(stmt)


async def update_question_timeout(
    session: AsyncSession,
    question_id: int | str,
) -> None:
    """질문을 타임아웃(timeout) 처리한다."""
    q_id = int(question_id) if isinstance(question_id, str) and question_id.isdigit() else question_id
    stmt = (
        update(QuestionRow)
        .where(QuestionRow.id == q_id)
        .values(status="timeout", answer="unknown")
    )
    await session.execute(stmt)


async def insert_follow_up_turn(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    document_id: uuid.UUID | None = None,
) -> FollowUpTurn:
    """새 되묻기 차례 행을 삽입한다."""
    r_id = _to_uuid(review_id)
    turn = FollowUpTurn(
        review_id=r_id,
        document_id=document_id,
        status="running",
        tool_calls=0,
    )
    session.add(turn)
    await session.flush()
    return turn


async def get_follow_up_turn(
    session: AsyncSession,
    turn_id: int,
    review_id: str | uuid.UUID | None = None,
) -> FollowUpTurn | None:
    """되묻기 차례 행을 조회한다."""
    stmt = select(FollowUpTurn).where(FollowUpTurn.id == turn_id)
    if review_id:
        stmt = stmt.where(FollowUpTurn.review_id == _to_uuid(review_id))
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def update_follow_up_turn_status(
    session: AsyncSession,
    turn_id: int,
    status: str,
    ended_at: datetime | None = None,
) -> None:
    """되묻기 차례의 상태를 갱신한다."""
    values: dict[str, Any] = {"status": status}
    if ended_at is not None:
        values["ended_at"] = ended_at
    stmt = update(FollowUpTurn).where(FollowUpTurn.id == turn_id).values(**values)
    await session.execute(stmt)


async def increment_follow_up_tool_calls(
    session: AsyncSession, turn_id: int
) -> None:
    """되묻기 차례의 tool_calls 카운터를 1 증가시킨다."""
    stmt = (
        update(FollowUpTurn)
        .where(FollowUpTurn.id == turn_id)
        .values(tool_calls=FollowUpTurn.tool_calls + 1)
    )
    await session.execute(stmt)


async def has_running_follow_up(
    session: AsyncSession, review_id: str | uuid.UUID
) -> bool:
    """열려 있는(running) 되묻기 차례가 있는지 확인한다."""
    r_id = _to_uuid(review_id)
    stmt = select(func.count(FollowUpTurn.id)).where(
        FollowUpTurn.review_id == r_id, FollowUpTurn.status == "running"
    )
    res = await session.execute(stmt)
    return (res.scalar_one() or 0) > 0


async def delete_review_and_children(
    session: AsyncSession, review_id: str | uuid.UUID
) -> None:
    """검토 및 하위 테이블(review_records, questions, follow_up_turns, review)을 삭제한다."""
    r_id = _to_uuid(review_id)
    await session.execute(delete(ReviewRecord).where(ReviewRecord.review_id == r_id))
    await session.execute(delete(QuestionRow).where(QuestionRow.review_id == r_id))
    await session.execute(delete(FollowUpTurn).where(FollowUpTurn.review_id == r_id))
    await session.execute(delete(Review).where(Review.id == r_id))


async def upsert_usage_log(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    is_sample: bool,
    status: str,
    tool_calls: int,
    tokens_in: int,
    tokens_out: int,
    parsed_pages: int,
    cost_krw: int,
    corrections: int,
    llm_fallback: bool,
) -> None:
    """사용량 로그를 삽입하거나 갱신한다."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.domains.review.models import UsageLog

    r_id = _to_uuid(review_id)
    stmt = (
        pg_insert(UsageLog)
        .values(
            review_id=r_id,
            is_sample=is_sample,
            status=status,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            parsed_pages=parsed_pages,
            cost_krw=cost_krw,
            corrections=corrections,
            llm_fallback=llm_fallback,
        )
        .on_conflict_do_update(
            index_elements=[UsageLog.review_id],
            set_={
                "status": status,
                "tool_calls": tool_calls,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "parsed_pages": parsed_pages,
                "cost_krw": cost_krw,
                "corrections": corrections,
                "llm_fallback": llm_fallback,
                "updated_at": func.now(),
            },
        )
    )
    await session.execute(stmt)


async def list_expired_review_ids(
    session: AsyncSession, now: datetime
) -> list[uuid.UUID]:
    """보관 기간이 지난(expires_at < now) 검토 ID 목록을 조회한다 (status != 'expired')."""
    stmt = (
        select(Review.id)
        .where(Review.expires_at < now, Review.status != "expired")
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def expire_review(
    session: AsyncSession, review_id: str | uuid.UUID
) -> None:
    """검토의 딸린 행(records, questions, follow_up_turns)을 지우고 reviews 행을 만료 처리한다."""
    r_id = _to_uuid(review_id)
    await session.execute(delete(ReviewRecord).where(ReviewRecord.review_id == r_id))
    await session.execute(delete(QuestionRow).where(QuestionRow.review_id == r_id))
    await session.execute(delete(FollowUpTurn).where(FollowUpTurn.review_id == r_id))
    stmt = (
        update(Review)
        .where(Review.id == r_id)
        .values(counterparty_name=None, facts={}, status="expired")
    )
    await session.execute(stmt)


async def get_usage_summary_for_period(
    session: AsyncSession, start_dt: datetime, end_dt: datetime
) -> tuple[int, int, float]:
    """지정 기간(start_dt <= updated_at < end_dt)의 사용량 로그 통계(총 검토 수, 실패 수, 평균 비용)를 반환한다."""
    from app.domains.review.models import UsageLog

    stmt = select(
        func.count(UsageLog.review_id),
        func.count(UsageLog.review_id).filter(UsageLog.status == "failed"),
        func.coalesce(func.avg(UsageLog.cost_krw), 0.0),
    ).where(UsageLog.updated_at >= start_dt, UsageLog.updated_at < end_dt)

    res = await session.execute(stmt)
    row = res.one()
    total_reviews = row[0] or 0
    failed_reviews = row[1] or 0
    avg_cost = float(row[2] or 0.0)
    return total_reviews, failed_reviews, avg_cost

