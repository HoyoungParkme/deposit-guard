"""Rules 도메인 라우터 (GET /api/criteria).

근거: JSD-API-001 3.5, JSD-UI-001#UI-4, JSD-PRD-001#R6
"""

from dataclasses import asdict
from typing import Any
from fastapi import APIRouter, Depends, Query

from app.core.config import LIMITS
from app.domains.rules.service import RulesService
from app.shared.types import CriteriaTopic

router = APIRouter(tags=["rules"])


def get_rules_service() -> RulesService:
    return RulesService()


@router.get("/api/criteria")
async def get_criteria(
    topic: CriteriaTopic | None = Query(None),
    signal_code: str | None = Query(None),
    rules_service: RulesService = Depends(get_rules_service),
) -> dict[str, Any]:
    """판정 규칙 상수를 반환한다."""
    criteria = rules_service.criteria(limits=LIMITS, topic=topic, signal_code=signal_code)
    res = asdict(criteria)
    return {k: v for k, v in res.items() if v is not None}
