"""Sample 도메인 라우터.

근거: JSD-API-001 3.4 GET /api/samples, JSD-UI-001#UI-1
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.domains.sample.schemas import SampleCaseResponse
from app.domains.sample.service import SampleService

router = APIRouter(prefix="/api/samples", tags=["samples"])


class SamplesListResponse(BaseModel):
    samples: list[SampleCaseResponse]


@router.get("", response_model=SamplesListResponse)
def get_samples() -> SamplesListResponse:
    """시작 화면의 예시 카드 목록을 반환한다."""
    cases = SampleService.list()
    items = [
        SampleCaseResponse(
            sample_id=c.sample_id,
            title=c.title,
            summary=c.summary,
            region=c.region,
            deposit_manwon=c.deposit_manwon,
            contract_type=c.contract_type,
        )
        for c in cases
    ]
    return SamplesListResponse(samples=items)
