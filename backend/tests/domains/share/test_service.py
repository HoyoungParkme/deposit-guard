"""ShareService 단위 및 통합 테스트.

근거: JSD-MS-009, JSD-DOM-002 4.9, JSD-API-001 3.4
"""

from datetime import date, datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domains.citation.service import CitationService
from app.domains.registry.models import RegistryExtract
from app.domains.report.models import Opinion
from app.domains.report.service import ReportService
from app.domains.review.models import Review
from app.domains.share import crud
from app.domains.share.service import ShareService
from app.shared.types import (
    BuildingType,
    CheckResult,
    ContractType,
    Grade,
    GradeLevel,
    PriceSource,
    Property,
    Report,
    ReportCheckedItem,
    ReportConclusion,
    ReportInput,
    ReportSignalItem,
    RightsSummary,
    RiskSignal,
    Section,
    Severity,
    SignalCheck,
    Todo,
    TodoStage,
)


@pytest.mark.asyncio
async def test_share_service_lifecycle(db_session: AsyncSession):
    """공유 링크 생성, 조회, 410 만료 동작 검증."""
    review_id = str(uuid.uuid4())
    rev_uuid = uuid.UUID(review_id)
    now = datetime.now(timezone.utc)

    # 1. 검토 및 의견서 등록
    await db_session.execute(
        insert(Review).values(
            id=rev_uuid,
            status="done",
            deposit_manwon=15000,
            contract_type="jeonse",
            facts={},
            expires_at=now + timedelta(hours=24),
        )
    )

    body_dict = {
        "grade": {"level": "safe", "deciders": [], "unknowns": [], "rule_version": "1.0"},
        "conclusion": {"text": "안전한 계약입니다.", "citations": []},
        "rights": {"senior_total_manwon": 0, "deposit_manwon": 15000, "debt_ratio": 0.5},
        "signals": [],
        "checked": [],
        "todos": [],
        "clauses": [],
        "questions_to_ask": [],
        "notices": [],
        "corrections": 0,
        "llm_fallback": False,
        "revision_no": 1,
    }
    subject_dict = {
        "region_short": "서울 강서구 화곡동",
        "building_type": "apartment",
        "deposit_manwon": 15000,
        "contract_type": "jeonse",
        "reviewed_at": now.isoformat(),
    }

    await db_session.execute(
        insert(Opinion).values(
            review_id=rev_uuid,
            body=body_dict,
            subject=subject_dict,
            revision_no=1,
            written_at=now,
        )
    )
    await db_session.commit()

    # 2. 공유 링크 생성
    share_service = ShareService(session=db_session)
    link = await share_service.create(review_id)
    assert link.token is not None
    assert len(link.token) == 32
    assert link.url == f"/s/{link.token}"

    # 3. 공유본 조회
    shared = await share_service.get(link.token)
    assert shared.report.conclusion.text == "안전한 계약입니다."
    assert shared.subject["region_short"] == "서울 강서구 화곡동"
    assert len(shared.report.clauses) == 0  # 공유본에는 특약 제외

    # 4. 만료 비우기
    future = now + timedelta(days=8)
    purged = await share_service.purge_expired(future)
    assert purged == 1

    # 5. 비운 후 조회 시 410 gone
    with pytest.raises(AppError) as exc_info:
        await share_service.get(link.token)
    assert exc_info.value.code == "gone"
