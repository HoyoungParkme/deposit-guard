"""Review 도메인 ORM 모델 (Review, ReviewRecord, QuestionRow, FollowUpTurn, UsageLog).

근거: JSD-DOM-002 2.1, 2.8, JSD-DOM-003 1장, 2장
"""

import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Review(Base):
    """검토 세션 모델 (JSD-DOM-003 reviews)."""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="created",
    )
    deposit_manwon: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_type: Mapped[str] = mapped_column(Text, nullable=False)
    counterparty_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    facts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_krw: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_cost_krw: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    corrections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'waiting_user', 'done', 'failed', 'expired')",
            name="ck_reviews_status",
        ),
        CheckConstraint(
            "contract_type IN ('jeonse', 'monthly')",
            name="ck_reviews_contract_type",
        ),
    )


class FollowUpTurn(Base):
    """되묻기 차례 모델 (JSD-DOM-003 follow_up_turns)."""

    __tablename__ = "follow_up_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'done', 'failed')",
            name="ck_follow_up_turns_status",
        ),
    )


class ReviewRecord(Base):
    """검토 진행 메시지 모델 (JSD-DOM-003 review_records)."""

    __tablename__ = "review_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    turn_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("follow_up_turns.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("review_id", "seq", name="uq_review_records_review_seq"),
        CheckConstraint(
            "role IN ('agent', 'user', 'system')",
            name="ck_review_records_role",
        ),
        CheckConstraint(
            "kind IN ('say', 'tool', 'question', 'answer', 'numbers', 'report', 'notice', 'error')",
            name="ck_review_records_kind",
        ),
    )


class QuestionRow(Base):
    """에이전트 질문 모델 (JSD-DOM-003 questions)."""

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    asked_no: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    why: Mapped[str] = mapped_column(Text, nullable=False)
    input_type: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    help_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    asked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('illegal_building', 'price', 'tenants', 'proxy', 'owner_type', 'land_registry', 'other')",
            name="ck_questions_kind",
        ),
        CheckConstraint(
            "input_type IN ('choice', 'number', 'text', 'file')",
            name="ck_questions_input_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'answered', 'timeout')",
            name="ck_questions_status",
        ),
    )


class UsageLog(Base):
    """사용량 및 비용 로그 모델 (JSD-DOM-003 usage_logs, review_id FK 아님)."""

    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_krw: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    corrections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'waiting_user', 'done', 'failed', 'expired')",
            name="ck_usage_logs_status",
        ),
    )
