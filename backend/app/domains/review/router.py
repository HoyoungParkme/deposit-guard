"""Review 도메인 라우터.

근거: JSD-API-001 3.1, JSD-UI-001#UI-1, JSD-UI-001#UI-2
"""

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Request,
    UploadFile,
    status,
)

from app.core.config import LIMITS
from app.core.errors import AppError
from app.domains.review.schemas import (
    CreateReviewResponse,
    QuestionResponse,
    ReviewCountersResponse,
    ReviewDocumentResponse,
    ReviewSubjectResponse,
    ReviewViewResponse,
)
from app.domains.review.service import ReviewService
from app.shared.types import ContractType, Upload

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _extract_client_ip(request: Request) -> str:
    """프록시 헤더를 반영한 클라이언트 원문 IP 추출."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


def get_review_service() -> ReviewService:
    return ReviewService()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateReviewResponse,
)
async def create_review(
    request: Request,
    deposit_manwon: int = Form(...),
    contract_type: ContractType = Form(...),
    sample_id: str | None = Form(None),
    counterparty_name: str | None = Form(None),
    file: UploadFile | None = None,
    review_service: ReviewService = Depends(get_review_service),
) -> CreateReviewResponse:
    """등기부와 조건을 받아 검토를 만든다.

    B1 스텁: 에이전트 루프를 백그라운드로 띄우지 않는다 (B2가 푼다).
    """
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
