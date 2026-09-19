"""Share 도메인 라우터.

근거: JSD-API-001 3.4, JSD-UI-001#UI-3, JSD-UI-001#UI-5
"""

from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.domains.share.service import ShareService

router = APIRouter(tags=["shares"])


class ShareLinkResponse(BaseModel):
    token: str
    url: str
    expires_at: datetime


class SharedViewResponse(BaseModel):
    report: dict[str, Any]
    subject: dict[str, Any]
    expires_at: datetime


def get_share_service() -> ShareService:
    return ShareService()


@router.post(
    "/api/reviews/{review_id}/shares",
    status_code=status.HTTP_201_CREATED,
    response_model=ShareLinkResponse,
)
async def create_share_link(
    review_id: str,
    share_service: ShareService = Depends(get_share_service),
) -> ShareLinkResponse:
    """마스킹한 사본을 만들고 공유 링크 토큰을 반환한다."""
    link = await share_service.create(review_id)
    return ShareLinkResponse(
        token=link.token,
        url=link.url,
        expires_at=link.expires_at,
    )


@router.get(
    "/api/shares/{token}",
    response_model=SharedViewResponse,
)
async def get_shared_view(
    token: str,
    share_service: ShareService = Depends(get_share_service),
) -> SharedViewResponse:
    """공유본 의견서를 조회한다."""
    view = await share_service.get(token)
    from dataclasses import asdict
    return SharedViewResponse(
        report=asdict(view.report),
        subject=view.subject,
        expires_at=view.expires_at,
    )
