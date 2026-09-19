"""ShareService 공유 링크 및 의견서 사본 관리 서비스.

항목 ID: JSD-MS-009
근거: JSD-DOM-002 4.9, JSD-DOM-003, JSD-SEQ-001, JSD-API-001
규칙: 원본 검토·대화·인용에 닿지 않음. ReportService.shareable 사본만 보관.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LIMITS
from app.core.db import async_session_factory
from app.core.errors import AppError
from app.domains.report.service import ReportService
from app.domains.share import crud
from app.shared.types import (
    CheckResult,
    Grade,
    GradeLevel,
    PriceSource,
    Report,
    ReportCheckedItem,
    ReportConclusion,
    ReportSignalItem,
    RightsSummary,
    Severity,
    Shareable,
    SharedView,
    ShareLink,
    Todo,
    TodoStage,
)


def _deserialize_report(data: dict[str, Any]) -> Report:
    """JSON 딕셔너리를 Report dataclass로 복원한다."""
    grade_data = data.get("grade", {})
    grade = Grade(
        level=GradeLevel(grade_data["level"]) if isinstance(grade_data.get("level"), str) else grade_data.get("level"),
        deciders=grade_data.get("deciders", []),
        unknowns=grade_data.get("unknowns", []),
        rule_version=grade_data.get("rule_version", ""),
    )
    conclusion_data = data.get("conclusion", {})
    conclusion = ReportConclusion(
        text=conclusion_data.get("text", ""),
        citations=[],
    )
    rights_data = data.get("rights", {})
    ps = rights_data.get("price_source")
    rights = RightsSummary(
        senior_mortgage_manwon=rights_data.get("senior_mortgage_manwon", 0),
        senior_lease_manwon=rights_data.get("senior_lease_manwon", 0),
        other_tenants_manwon=rights_data.get("other_tenants_manwon", 0),
        senior_total_manwon=rights_data.get("senior_total_manwon", 0),
        deposit_manwon=rights_data.get("deposit_manwon", 0),
        price_manwon=rights_data.get("price_manwon"),
        price_source=PriceSource(ps) if isinstance(ps, str) else ps,
        debt_ratio=rights_data.get("debt_ratio"),
        senior_ratio=rights_data.get("senior_ratio"),
        multi_household_unknown=rights_data.get("multi_household_unknown", False),
        based_on=rights_data.get("based_on", []),
    )
    signals = [
        ReportSignalItem(
            code=s["code"],
            severity=Severity(s["severity"]) if isinstance(s.get("severity"), str) else s.get("severity"),
            label=s["label"],
            explanation=s["explanation"],
            source=s["source"],
            source_date=datetime.fromisoformat(s["source_date"]).date() if s.get("source_date") else None,
            citations=[],
        )
        for s in data.get("signals", [])
    ]
    checked = [
        ReportCheckedItem(
            code=c["code"],
            label=c["label"],
            result=CheckResult(c["result"]) if isinstance(c.get("result"), str) else c.get("result"),
            citations=[],
        )
        for c in data.get("checked", [])
    ]
    todos = [
        Todo(
            stage=TodoStage(t["stage"]) if isinstance(t.get("stage"), str) else t.get("stage"),
            title=t["title"],
            how=t["how"],
            cost=t["cost"],
            because=t["because"] if isinstance(t.get("because"), list) else [t.get("because", "")],
        )
        for t in data.get("todos", [])
    ]

    return Report(
        grade=grade,
        conclusion=conclusion,
        rights=rights,
        signals=signals,
        checked=checked,
        todos=todos,
        clauses=[],
        questions_to_ask=[],
        notices=data.get("notices", []),
        corrections=data.get("corrections", 0),
        llm_fallback=data.get("llm_fallback", False),
        revision_no=data.get("revision_no", 1),
        revision_reason=data.get("revision_reason"),
    )


class ShareService:
    """의견서 공유 링크 생성 및 조회 서비스."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        report_service: ReportService | None = None,
    ):
        self._session = session
        self._report_service = report_service or ReportService(session=session)

    @asynccontextmanager
    async def _session_ctx(self, session: AsyncSession | None = None):
        if session is not None:
            yield session
        elif self._session is not None:
            yield self._session
        else:
            async with async_session_factory() as sess:
                async with sess.begin():
                    yield sess

    async def create(
        self,
        review_id: str,
        session: AsyncSession | None = None,
    ) -> ShareLink:
        """공유 링크 만들기.

        항목 ID: JSD-MS-009#ShareService.create
        근거: JSD-SEQ-001#SEQ-14, JSD-API-001#POST/api/reviews/{id}/shares, JSD-UC-001#UC-A4
        """
        s: Shareable = await self._report_service.shareable(review_id, session=session)
        token = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=LIMITS.share_days)

        report_dict = asdict(s.report)
        # 날짜 문자열 변환
        for sig in report_dict.get("signals", []):
            if sig.get("source_date"):
                sig["source_date"] = str(sig["source_date"])

        async with self._session_ctx(session) as sess:
            for _ in range(2):
                try:
                    await crud.insert_shared_opinion(
                        session=sess,
                        token=token,
                        report=report_dict,
                        subject=s.subject,
                        expires_at=expires_at,
                    )
                    break
                except Exception:
                    token = secrets.token_urlsafe(24)

        return ShareLink(
            token=token,
            url=f"/s/{token}",
            expires_at=expires_at,
        )

    async def get(
        self,
        token: str,
        session: AsyncSession | None = None,
    ) -> SharedView:
        """공유본 보기.

        항목 ID: JSD-MS-009#ShareService.get
        근거: JSD-SEQ-001#SEQ-14, JSD-API-001#GET/api/shares/{token}, JSD-UI-001#UI-5
        """
        async with self._session_ctx(session) as sess:
            row = await crud.get_shared_opinion_by_token(sess, token)
            if not row:
                raise AppError("not_found", "공유 링크를 찾을 수 없습니다.")

            now = datetime.now(timezone.utc)
            if row.expires_at <= now or row.report is None:
                raise AppError("gone", "공유 링크가 만료되었습니다.")

            report_obj = _deserialize_report(row.report)
            return SharedView(
                report=report_obj,
                subject=row.subject or {},
                expires_at=row.expires_at,
            )

    async def purge_expired(
        self,
        now: datetime,
        session: AsyncSession | None = None,
    ) -> int:
        """만료 공유본 비우기.

        항목 ID: JSD-MS-009#ShareService.purge_expired
        근거: JSD-SEQ-001#SEQ-16, JSD-DOM-002 5장 결정 4
        """
        async with self._session_ctx(session) as sess:
            return await crud.purge_expired_shared_opinions(sess, now)
