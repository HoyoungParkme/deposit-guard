"""Review 도메인 DTO 및 스키마.

근거: JSD-DOM-002 2.8, JSD-API-001, JSD-MS-001
"""

from dataclasses import dataclass, field
from datetime import datetime
from pydantic import BaseModel
from app.shared.types import (
    BuildingType,
    ContractType,
    DocKind,
    InputType,
    MessageKind,
    QuestionKind,
    ReviewStatus,
    Role,
)


@dataclass(frozen=True)
class ReviewCreated:
    """검토 생성 응답 DTO (JSD-DOM-002 2.8 ReviewCreated)."""

    review_id: str
    status: ReviewStatus
    is_sample: bool
    expires_at: datetime


@dataclass(frozen=True)
class QuestionDTO:
    """질문 DTO (JSD-DOM-002 2.8 Question)."""

    question_id: str
    kind: QuestionKind
    text: str
    why: str
    input_type: InputType
    options: list[str] | None
    help_url: str | None
    asked_no: int


@dataclass(frozen=True)
class ReviewSubject:
    """검토 대상 DTO."""

    building_type: BuildingType
    deposit_manwon: int
    contract_type: ContractType
    region: str


@dataclass(frozen=True)
class ReviewCounters:
    """진행 카운터 DTO."""

    tool_calls: int
    questions_asked: int
    asks_used: int
    elapsed_sec: int
    cost_krw: int


@dataclass(frozen=True)
class ReviewDocumentItem:
    """문서 요약 항목 DTO (page_count 제외)."""

    document_id: str
    kind: DocKind
    label: str


@dataclass(frozen=True)
class ReviewView:
    """상단 바 요약과 진행 수치 DTO (JSD-DOM-002 2.8 ReviewView)."""

    review_id: str
    status: ReviewStatus
    subject: ReviewSubject
    counters: ReviewCounters
    pending_question: QuestionDTO | None
    documents: list[ReviewDocumentItem]
    has_report: bool
    expires_at: datetime


class CreateReviewResponse(BaseModel):
    """POST /api/reviews 응답 모델 (JSD-API-001 3장)."""

    review_id: str
    status: ReviewStatus
    is_sample: bool
    expires_at: datetime


class ReviewSubjectResponse(BaseModel):
    building_type: BuildingType
    deposit_manwon: int
    contract_type: ContractType
    region: str


class ReviewCountersResponse(BaseModel):
    tool_calls: int
    questions_asked: int
    asks_used: int
    elapsed_sec: int
    cost_krw: int


class ReviewDocumentResponse(BaseModel):
    document_id: str
    kind: DocKind
    label: str


class QuestionResponse(BaseModel):
    question_id: str
    kind: QuestionKind
    text: str
    why: str
    input_type: InputType
    options: list[str] | None = None
    help_url: str | None = None
    asked_no: int


class ReviewViewResponse(BaseModel):
    """GET /api/reviews/{id} 응답 모델 (JSD-API-001 3장)."""

    review_id: str
    status: ReviewStatus
    subject: ReviewSubjectResponse
    counters: ReviewCountersResponse
    pending_question: QuestionResponse | None = None
    documents: list[ReviewDocumentResponse]
    has_report: bool
    expires_at: datetime
