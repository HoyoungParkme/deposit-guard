"""Review 도메인 라우터.

근거: JSD-API-001 3.1, 3.2, 3.3, 3.4, JSD-UI-001
"""

from dataclasses import asdict
from typing import Any
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import LIMITS
from app.core.errors import AppError
from app.domains.citation.service import CitationService
from app.domains.report.service import ReportService
from app.domains.review.adapters.openai_agent import OpenAIAgentModel
from app.domains.review.schemas import (
    CreateReviewResponse,
    EntryOverride,
    QuestionResponse,
    ReviewCountersResponse,
    ReviewDocumentResponse,
    ReviewSubjectResponse,
    ReviewViewResponse,
    UserInput,
    ValueOverrides,
)
from app.domains.review.service import ReviewService
from app.domains.review.service_agent import run_follow_up, run_review
from app.shared.types import (
    ContractType,
    InputKind,
    Upload,
)

from app.domains.review.ports import AgentModel

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _extract_client_ip(request: Request) -> str:
    """프록시 헤더를 반영한 클라이언트 원문 IP 추출."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


def get_agent_model() -> AgentModel:
    return OpenAIAgentModel()


def get_review_service() -> ReviewService:
    return ReviewService()


def get_citation_service() -> CitationService:
    return CitationService()


def get_report_service() -> ReportService:
    return ReportService()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateReviewResponse,
)
async def create_review(
    request: Request,
    background_tasks: BackgroundTasks,
    deposit_manwon: int = Form(...),
    contract_type: ContractType = Form(...),
    sample_id: str | None = Form(None),
    counterparty_name: str | None = Form(None),
    file: UploadFile | None = None,
    review_service: ReviewService = Depends(get_review_service),
    model: AgentModel = Depends(get_agent_model),
) -> CreateReviewResponse:
    """등기부와 조건을 받아 검토를 만들고 에이전트 루프를 시작한다."""
    # 폼 읽기 전에 크기 제한 사전 검사
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > LIMITS.file_mb * 1024 * 1024 + 1024 * 1024:
        raise AppError("invalid_file", field="file")

    upload_dto: Upload | None = None
    if file is not None:
        data = await file.read()
        if len(data) > 0:
            upload_dto = Upload(
                data=data,
                media_type=file.content_type or "application/octet-stream",
                filename=file.filename or "upload",
            )

    client_ip = _extract_client_ip(request)
    created = await review_service.create(
        upload=upload_dto,
        sample_id=sample_id,
        deposit_manwon=deposit_manwon,
        contract_type=contract_type,
        counterparty_name=counterparty_name,
        client_ip=client_ip,
    )

    # 백그라운드로 에이전트 루프 실행 (JSD-DOM-002 5장 결정 6)
    background_tasks.add_task(run_review, created.review_id, model)

    return CreateReviewResponse(
        review_id=created.review_id,
        status=created.status,
        is_sample=created.is_sample,
        expires_at=created.expires_at,
    )


@router.get(
    "/{review_id}",
    response_model=ReviewViewResponse,
)
async def get_review(
    review_id: str,
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewViewResponse:
    """상단 바 요약과 진행 수치를 반환한다."""
    view = await review_service.get(review_id)

    pending_q = (
        QuestionResponse(
            question_id=view.pending_question.question_id,
            kind=view.pending_question.kind,
            text=view.pending_question.text,
            why=view.pending_question.why,
            input_type=view.pending_question.input_type,
            options=view.pending_question.options,
            help_url=view.pending_question.help_url,
            asked_no=view.pending_question.asked_no,
        )
        if view.pending_question
        else None
    )

    return ReviewViewResponse(
        review_id=view.review_id,
        status=view.status,
        subject=ReviewSubjectResponse(
            building_type=view.subject.building_type,
            deposit_manwon=view.subject.deposit_manwon,
            contract_type=view.subject.contract_type,
            region=view.subject.region,
        ),
        counters=ReviewCountersResponse(
            tool_calls=view.counters.tool_calls,
            questions_asked=view.counters.questions_asked,
            asks_used=view.counters.asks_used,
            elapsed_sec=view.counters.elapsed_sec,
            cost_krw=view.counters.cost_krw,
        ),
        pending_question=pending_q,
        documents=[
            ReviewDocumentResponse(
                document_id=d.document_id,
                kind=d.kind,
                label=d.label,
            )
            for d in view.documents
        ],
        has_report=view.has_report,
        expires_at=view.expires_at,
    )


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_review(
    review_id: str,
    review_service: ReviewService = Depends(get_review_service),
) -> None:
    """진행 중이면 멈추고 원문·대화·의견서 데이터를 즉시 지운다."""
    await review_service.cancel(review_id)


@router.get(
    "/{review_id}/messages",
)
async def list_messages(
    review_id: str,
    after_seq: int = 0,
    limit: int = 200,
    review_service: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    """재방문·재접속·스트림 폴백용 대화 메시지 목록 조회."""
    page = await review_service.list_messages(review_id, after_seq, limit)
    return {
        "messages": [asdict(m) for m in page.messages],
        "next_seq": page.next_seq,
        "status": page.status,
    }


@router.get(
    "/{review_id}/stream",
)
async def stream_messages(
    review_id: str,
    request: Request,
    last_event_id: int | None = None,
    review_service: ReviewService = Depends(get_review_service),
):
    """대화 SSE 스트림 (JSD-API-001 GET /api/reviews/{id}/stream)."""
    header_id = request.headers.get("last-event-id")
    seq = int(header_id) if (header_id and header_id.isdigit()) else (last_event_id or 0)

    async def event_generator():
        async for ev in review_service.stream(review_id, seq):
            yield ev.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class PostMessageBody(BaseModel):
    kind: InputKind
    question_id: str | None = None
    text: str | None = None
    choice: str | None = None


@router.post(
    "/{review_id}/messages",
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_message(
    review_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    kind: InputKind = Form(None),
    question_id: str | None = Form(None),
    text: str | None = Form(None),
    choice: str | None = Form(None),
    file: UploadFile | None = None,
    review_service: ReviewService = Depends(get_review_service),
    model: AgentModel = Depends(get_agent_model),
) -> dict[str, Any]:
    """질문에 답하거나 되묻기 발화를 보낸다 (JSON or multipart)."""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body_dict = await request.json()
        input_kind = InputKind(body_dict.get("kind"))
        user_input = UserInput(
            kind=input_kind,
            question_id=body_dict.get("question_id"),
            text=body_dict.get("text"),
            choice=body_dict.get("choice"),
            file=None,
        )
    else:
        upload_dto: Upload | None = None
        if file is not None:
            data = await file.read()
            if len(data) > 0:
                upload_dto = Upload(
                    data=data,
                    media_type=file.content_type or "application/octet-stream",
                    filename=file.filename or "upload",
                )
        if kind is None:
            raise AppError("missing_input", field="kind")
        user_input = UserInput(
            kind=kind,
            question_id=question_id,
            text=text,
            choice=choice,
            file=upload_dto,
        )

    accepted = await review_service.receive(review_id, user_input)

    # 되묻기인 경우 백그라운드 에이전트 루프 실행
    if user_input.kind == InputKind.ask and accepted.turn_id is not None:
        background_tasks.add_task(run_follow_up, review_id, accepted.turn_id, model)

    return {
        "message_id": accepted.message_id,
        "seq": accepted.seq,
    }


@router.get(
    "/{review_id}/blocks/{block_id}",
)
async def get_block_usages(
    review_id: str,
    block_id: str,
    citation_service: CitationService = Depends(get_citation_service),
    review_service: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    """등기부 한 줄(블록)이 쓰인 곳을 조회한다."""
    await review_service.require_live(review_id)
    usages = await citation_service.usages(review_id, block_id)
    return asdict(usages)


@router.get(
    "/{review_id}/report",
)
async def get_report(
    review_id: str,
    report_service: ReportService = Depends(get_report_service),
    review_service: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    """의견서 전체를 조회한다."""
    await review_service.require_live(review_id)
    report = await report_service.get(review_id)
    return asdict(report)


class EntryOverrideItem(BaseModel):
    entry_id: str
    amount_manwon: int


class ValueOverridesBody(BaseModel):
    price_manwon: int | None = None
    entries: list[EntryOverrideItem] | None = None


@router.patch(
    "/{review_id}/values",
)
async def override_values(
    review_id: str,
    body: ValueOverridesBody,
    review_service: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    """시세·금액 직접 입력으로 의견서를 재판정한다."""
    entries_list = (
        [EntryOverride(entry_id=e.entry_id, amount_manwon=e.amount_manwon) for e in body.entries]
        if body.entries is not None
        else None
    )
    overrides = ValueOverrides(
        price_manwon=body.price_manwon,
        entries=entries_list,
    )
    report = await review_service.override_values(review_id, overrides)
    return asdict(report)
