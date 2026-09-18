"""Registry 도메인 라우터.

근거: JSD-API-001 3.3, JSD-UI-001#UI-2
"""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.domains.registry.service import RegistryService
from app.domains.review.service import ReviewService
from app.shared.types import DocKind

router = APIRouter(prefix="/api/reviews/{review_id}/documents", tags=["documents"])


class DocumentBriefResponse(BaseModel):
    document_id: str
    kind: DocKind
    label: str
    page_count: int


class DocumentsListResponse(BaseModel):
    documents: list[DocumentBriefResponse]


from app.domains.review.router import get_review_service

def get_registry_service() -> RegistryService:
    return RegistryService()


async def require_live_review(
    review_id: str,
    review_service: ReviewService = Depends(get_review_service),
) -> None:
    """검토 만료/미존재 검증 공통 종속성."""
    await review_service.require_live(review_id)


@router.get(
    "",
    response_model=DocumentsListResponse,
    dependencies=[Depends(require_live_review)],
)
async def list_documents(
    review_id: str,
    registry_service: RegistryService = Depends(get_registry_service),
) -> DocumentsListResponse:
    """문서 패널의 탭 목록을 조회한다."""
    docs = await registry_service.list(review_id)
    items = [
        DocumentBriefResponse(
            document_id=d.document_id,
            kind=d.kind,
            label=d.label,
            page_count=d.page_count,
        )
        for d in docs
    ]
    return DocumentsListResponse(documents=items)


@router.get(
    "/{document_id}",
    response_class=Response,
    dependencies=[Depends(require_live_review)],
)
async def get_document_html(
    review_id: str,
    document_id: str,
    registry_service: RegistryService = Depends(get_registry_service),
) -> Response:
    """파싱된 등기부 원문 HTML을 반환한다."""
    html_content = await registry_service.get_html(review_id, document_id)
    return Response(
        content=html_content,
        media_type="text/html; charset=utf-8",
    )
