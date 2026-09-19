"""Review 도메인 서비스 (ReviewService).

근거: JSD-DOM-002 4.1, JSD-MS-001, JSD-SEQ-001, JSD-API-001, JSD-DOM-003
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import time
from typing import Any, AsyncIterator
import uuid
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LIMITS, PRICES
from app.core.db import async_session_factory
from app.core.errors import AppError
from app.domains.citation.service import CitationService
from app.domains.gate import service as gate
from app.domains.registry.service import RegistryService
from app.domains.report.service import ReportService
from app.domains.review import crud
from app.domains.review.schemas import (
    Accepted,
    AnswerData,
    AskAnswer,
    AskArgs,
    EntryOverride,
    Message,
    MessagesPage,
    NoticeData,
    QuestionDTO,
    ReportCard,
    ReviewCounters,
    ReviewCreated,
    ReviewDocumentItem,
    ReviewFacts,
    ReviewSubject,
    ReviewView,
    StreamEvent,
    UsageSummary,
    UserInput,
    ValueOverrides,
)
from app.domains.rules.service import RulesService
from app.domains.sample.service import SampleService
from app.infra.openai import usage_krw
from app.shared import factcheck, money, privacy
from app.shared.types import (
    BuildingType,
    ChecklistItem,
    CheckResult,
    Citation,
    CitationUse,
    ContractType,
    DocKind,
    EntryFact,
    FileCheck,
    Grade,
    GradeLevel,
    IllegalBuilding,
    InputKind,
    InputType,
    MessageKind,
    OwnerType,
    ParsedDocument,
    PriceSource,
    Property,
    PropertyFact,
    ProxyStatus,
    QuestionKind,
    Report,
    ReportInput,
    ReportResult,
    ReviewStatus,
    RightsInput,
    RightsSummary,
    RiskSignal,
    Role,
    Severity,
    SignalCheck,
    SignalInput,
    UnknownItem,
    UnknownReason,
    Upload,
)

# 고정 선택지 라벨 -> 열거형 값 매핑 (JSD-PRD-001 R8)
CHOICE_VALUE_MAP: dict[str, dict[str, str]] = {
    "illegal_building": {
        "해당 없음 (위반건축물 아님)": "no",
        "위반건축물 아님": "no",
        "아님": "no",
        "no": "no",
        "위반건축물 표기 있음": "yes",
        "위반건축물 맞음": "yes",
        "맞음": "yes",
        "yes": "yes",
        "모름": "unknown",
        "unknown": "unknown",
    },
    "proxy": {
        "소유자 본인": "self",
        "본인": "self",
        "self": "self",
        "대리인 (위임장·인감증명서 있음)": "proxy_with_poa",
        "대리인(위임장 있음)": "proxy_with_poa",
        "proxy_with_poa": "proxy_with_poa",
        "대리인 (위임장 없음/미확인)": "proxy_without_poa",
        "대리인(위임장 없음)": "proxy_without_poa",
        "proxy_without_poa": "proxy_without_poa",
        "모름": "unknown",
        "미정": "unknown",
        "unknown": "unknown",
    },
    "owner_type": {
        "개인": "individual",
        "individual": "individual",
        "법인 (회사·공공기관)": "corporation",
        "법인": "corporation",
        "corporation": "corporation",
        "모름": "unknown",
        "unknown": "unknown",
    },
}

QUESTION_FIXED_OPTIONS: dict[str, list[str]] = {
    "illegal_building": [
        "해당 없음 (위반건축물 아님)",
        "위반건축물 표기 있음",
        "모름",
    ],
    "proxy": [
        "소유자 본인",
        "대리인 (위임장·인감증명서 있음)",
        "대리인 (위임장 없음/미확인)",
        "모름",
    ],
    "owner_type": [
        "개인",
        "법인 (회사·공공기관)",
        "모름",
    ],
}


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    return val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))


def _deserialize_rights_summary(data: dict[str, Any] | RightsSummary) -> RightsSummary:
    if isinstance(data, RightsSummary):
        return data
    ps = data.get("price_source")
    if isinstance(ps, str):
        ps = PriceSource(ps)
    return RightsSummary(
        senior_mortgage_manwon=data.get("senior_mortgage_manwon", 0),
        senior_lease_manwon=data.get("senior_lease_manwon", 0),
        other_tenants_manwon=data.get("other_tenants_manwon", 0),
        senior_total_manwon=data.get("senior_total_manwon", 0),
        deposit_manwon=data.get("deposit_manwon", 0),
        price_manwon=data.get("price_manwon"),
        price_source=ps,
        debt_ratio=data.get("debt_ratio"),
        senior_ratio=data.get("senior_ratio"),
        multi_household_unknown=data.get("multi_household_unknown", False),
        based_on=data.get("based_on", []),
    )


def _deserialize_signal_check(data: dict[str, Any] | SignalCheck) -> SignalCheck:
    if isinstance(data, SignalCheck):
        return data
    g_data = data.get("grade", {})
    grade_obj = g_data if isinstance(g_data, Grade) else Grade(
        level=GradeLevel(g_data["level"]) if isinstance(g_data.get("level"), str) else g_data.get("level", GradeLevel.safe),
        deciders=g_data.get("deciders", []),
        unknowns=g_data.get("unknowns", []),
        rule_version=g_data.get("rule_version", "2026.03"),
    )
    signals = []
    for s in data.get("signals", []):
        if isinstance(s, RiskSignal):
            signals.append(s)
        else:
            s_date = s.get("source_date")
            if isinstance(s_date, str):
                try:
                    s_date = date.fromisoformat(s_date)
                except Exception:
                    s_date = date.today()
            elif not isinstance(s_date, date):
                s_date = date.today()
            signals.append(RiskSignal(
                code=s["code"],
                severity=Severity(s["severity"]) if isinstance(s.get("severity"), str) else s.get("severity", Severity.caution),
                label=s.get("label", ""),
                source=s.get("source", ""),
                entry_ids=s.get("entry_ids", []),
                source_date=s_date,
            ))
    checked = []
    for c in data.get("checked", []):
        if isinstance(c, ChecklistItem):
            checked.append(c)
        else:
            checked.append(ChecklistItem(
                code=c["code"],
                label=c.get("label", ""),
                result=CheckResult(c["result"]) if isinstance(c.get("result"), str) else c.get("result", CheckResult.pass_),
                entry_ids=c.get("entry_ids", []),
            ))
    unknowns = []
    for u in data.get("unknowns", []):
        if isinstance(u, UnknownItem):
            unknowns.append(u)
        else:
            unknowns.append(UnknownItem(
                code=u["code"],
                reason=UnknownReason(u["reason"]) if isinstance(u.get("reason"), str) else u.get("reason", UnknownReason.other),
                how_to_check=u.get("how_to_check", ""),
            ))
    return SignalCheck(
        grade=grade_obj,
        signals=signals,
        checked=checked,
        unknowns=unknowns,
    )


class ReviewService:
    """검토의 상태·한도·대화 기록·세션 정보 채우기 서비스 (ReviewService 22개 함수)."""

    def __init__(
        self,
        registry_service: RegistryService | None = None,
        citation_service: CitationService | None = None,
        rules_service: RulesService | None = None,
        report_service: ReportService | None = None,
    ) -> None:
        self.registry_service: RegistryService = registry_service or RegistryService()
        self.citation_service: CitationService = citation_service or CitationService()
        self.rules_service: RulesService = rules_service or RulesService()
        self.report_service: ReportService = report_service or ReportService()

    async def parse_upload(
        self,
        upload: Upload,
        check: FileCheck,
        is_sample: bool,
        sample_id: str | None = None,
    ) -> tuple[ParsedDocument, bool]:
        """파싱 캐시를 보고 없으면 업스테이지로 파싱.

        항목 ID: JSD-MS-001#ReviewService.parse_upload
        근거: JSD-SEQ-001#SEQ-1, JSD-DOM-002 5장 결정 3
        """
        cached = await gate.cached_html(check.file_sha256)
        if cached is not None:
            return cached, True

        try:
            parsed = await self.registry_service.parse(upload.data, check.media_type)
            return parsed, False
        except Exception:
            if is_sample and sample_id:
                fixture_html = SampleService.fixture_html(sample_id)
                if fixture_html is not None:
                    parsed = ParsedDocument(html=fixture_html, page_count=1, billed_pages=1)
                    async with async_session_factory() as session:
                        async with session.begin():
                            await gate.remember_html(
                                check.file_sha256,
                                parsed.html,
                                parsed.page_count,
                                is_sample=True,
                                session=session,
                            )
                    return parsed, False
            raise

    async def create(
        self,
        upload: Upload | None,
        sample_id: str | None,
        deposit_manwon: int,
        contract_type: ContractType,
        counterparty_name: str | None,
        client_ip: str,
    ) -> ReviewCreated:
        """업로드를 검사·파싱하고 검토를 만든다.

        항목 ID: JSD-MS-001#ReviewService.create
        근거: JSD-SEQ-001#SEQ-1, JSD-API-001#POST/api/reviews, JSD-UC-001#UC-A1 1~3, JSD-UC-001#UC-S10
        """
        # 1. 입력 검증
        if (upload is None and sample_id is None) or (upload is not None and sample_id is not None):
            raise AppError("missing_input", field="file")
        if deposit_manwon < 1:
            raise AppError("missing_input", field="deposit_manwon")

        # 2. 예시 파일 처리
        is_sample = sample_id is not None
        active_upload: Upload
        if is_sample and sample_id is not None:
            active_upload = SampleService.file(sample_id)
        else:
            assert upload is not None
            active_upload = upload

        # 3. 파일 유효성 검사
        check = gate.check_file(active_upload)

        # 4. IP 일일 한도 검사 (Asia/Seoul 기준 오늘 날짜)
        today = datetime.now(ZoneInfo("Asia/Seoul")).date()
        await gate.take_quota(client_ip, check.file_sha256, is_sample, today)

        # 5. 파싱 또는 캐시 조회 (트랜잭션 밖)
        parsed, from_cache = await self.parse_upload(active_upload, check, is_sample, sample_id=sample_id)

        # 6. 짧은 트랜잭션으로 검토 생성 및 추출물 저장
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=LIMITS.retention_hours)
        cleaned_counterparty = counterparty_name.strip() if counterparty_name and counterparty_name.strip() else None
        cost_krw = parsed.billed_pages * PRICES.parse_page_krw

        async with async_session_factory() as session:
            async with session.begin():
                review = await crud.create_review(
                    session=session,
                    deposit_manwon=deposit_manwon,
                    contract_type=contract_type.value,
                    counterparty_name=cleaned_counterparty,
                    sample_id=sample_id,
                    facts={},
                    parsed_pages=parsed.billed_pages,
                    cost_krw=cost_krw,
                    expires_at=expires_at,
                )

                # 등기부 추출물 및 항목 저장 (not_registry면 자동 롤백)
                await self.registry_service.create_extract(
                    review_id=review.id,
                    html=parsed.html,
                    page_count=parsed.page_count,
                    file_sha256=check.file_sha256,
                    session=session,
                )

                # 캐시 신규 등록
                if not from_cache:
                    await gate.remember_html(
                        file_sha256=check.file_sha256,
                        html=parsed.html,
                        page_count=parsed.page_count,
                        is_sample=is_sample,
                        session=session,
                    )

        # 7. upload 참조 해제
        del active_upload
        del upload

        # 8. 반환
        return ReviewCreated(
            review_id=str(review.id),
            status=ReviewStatus.created,
            is_sample=is_sample,
            expires_at=expires_at,
        )

    async def get(
        self,
        review_id: str | uuid.UUID,
        session: AsyncSession | None = None,
    ) -> ReviewView:
        """상단 바 요약과 진행 수치.

        항목 ID: JSD-MS-001#ReviewService.get
        근거: JSD-SEQ-001#SEQ-12, JSD-API-001#GET/api/reviews/{id}
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> ReviewView:
            review = await crud.get_review(sess, r_id)
            if review is None:
                raise AppError("not_found")
            if review.status == "expired":
                raise AppError("gone")

            # 문서 정보 조회
            prop = await self.registry_service.property(r_id, session=sess)
            docs = await self.registry_service.list(r_id, session=sess)

            # 의견서 존재 여부 조회
            has_report = await self.report_service.exists(r_id, session=sess)

            # 질문 수 및 대기 중인 질문
            questions_asked = await crud.count_questions(sess, r_id)
            pending_q_row = await crud.get_latest_pending_question(sess, r_id)
            pending_q: QuestionDTO | None = None
            if pending_q_row is not None:
                pending_q = QuestionDTO(
                    question_id=str(pending_q_row.id),
                    kind=QuestionKind(pending_q_row.kind),
                    text=pending_q_row.text,
                    why=pending_q_row.why,
                    input_type=InputType(pending_q_row.input_type),
                    options=pending_q_row.options,
                    help_url=pending_q_row.help_url,
                    asked_no=pending_q_row.asked_no,
                )

            asks_used = await crud.count_follow_up_turns(sess, r_id)

            # 경과 시간(초)
            finished_or_now = review.finished_at or datetime.now(timezone.utc)
            elapsed_sec = int((finished_or_now - review.created_at).total_seconds())

            # Subject 구성 (counterparty_name은 제외)
            subject = ReviewSubject(
                building_type=prop.building_type if prop else BuildingType.other,
                deposit_manwon=review.deposit_manwon,
                contract_type=ContractType(review.contract_type),
                region=prop.region if prop else "",
            )

            counters = ReviewCounters(
                tool_calls=review.tool_calls,
                questions_asked=questions_asked,
                asks_used=asks_used,
                elapsed_sec=elapsed_sec,
                cost_krw=review.cost_krw,
            )

            doc_items = [
                ReviewDocumentItem(
                    document_id=d.document_id,
                    kind=d.kind,
                    label=d.label,
                )
                for d in docs
            ]

            return ReviewView(
                review_id=str(review.id),
                status=ReviewStatus(review.status),
                subject=subject,
                counters=counters,
                pending_question=pending_q,
                documents=doc_items,
                has_report=has_report,
                expires_at=review.expires_at,
            )

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)

    async def cancel(self, review_id: str | uuid.UUID) -> None:
        """검토와 딸린 것을 즉시 지운다.

        항목 ID: JSD-MS-001#ReviewService.cancel
        근거: JSD-SEQ-001#SEQ-15, JSD-API-001#DELETE/api/reviews/{id}, JSD-DOM-002 5장 결정 4
        """
        r_id = _to_uuid(review_id)
        async with async_session_factory() as session:
            async with session.begin():
                review = await crud.get_review_for_update(session, r_id)
                if review is None:
                    raise AppError("not_found")
                if review.status == "expired":
                    raise AppError("gone")

                hashes = await self.registry_service.delete_for_review(r_id, session=session)
                for h in hashes:
                    await gate.forget(h, session=session)

                await self.citation_service.delete_for_review(r_id, session=session)
                await self.report_service.delete_for_review(r_id, session=session)
                await crud.delete_review_and_children(session, r_id)

    async def list_messages(
        self,
        review_id: str | uuid.UUID,
        after_seq: int = 0,
        limit: int = 200,
        session: AsyncSession | None = None,
    ) -> MessagesPage:
        """대화 한 쪽을 조회한다.

        항목 ID: JSD-MS-001#ReviewService.list_messages
        근거: JSD-SEQ-001#SEQ-11, JSD-API-001#GET/api/reviews/{id}/messages
        """
        r_id = _to_uuid(review_id)
        effective_limit = min(max(limit, 1), 200)

        async def _execute(sess: AsyncSession) -> MessagesPage:
            review = await crud.get_review(sess, r_id)
            if review is None:
                raise AppError("not_found")
            if review.status == "expired":
                raise AppError("gone")

            rows = await crud.list_review_records(sess, r_id, after_seq, effective_limit)
            rec_ids = [row.id for row in rows]
            cites_map = await self.citation_service.for_messages(r_id, rec_ids, session=sess)

            messages = [
                Message(
                    message_id=str(row.id),
                    seq=row.seq,
                    role=Role(row.role),
                    kind=MessageKind(row.kind),
                    text=row.text,
                    citations=cites_map.get(row.id, []),
                    data=row.data,
                    created_at=row.created_at,
                )
                for row in rows
            ]

            next_seq = rows[-1].seq if rows else after_seq
            return MessagesPage(
                messages=messages,
                next_seq=next_seq,
                status=ReviewStatus(review.status),
            )

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)

    async def stream(
        self,
        review_id: str | uuid.UUID,
        last_seq: int = 0,
    ) -> AsyncIterator[StreamEvent]:
        """대화 스트림 이벤트 (제너레이터).

        항목 ID: JSD-MS-001#ReviewService.stream
        근거: JSD-SEQ-001#SEQ-11, JSD-API-001#GET/api/reviews/{id}/stream, JSD-INFRA-001#C4
        """
        r_id = _to_uuid(review_id)

        # 1. 첫 확인 (응답 전 에러 처리)
        async with async_session_factory() as session:
            review = await crud.get_review(session, r_id)
            if review is None:
                raise AppError("not_found")
            if review.status == "expired":
                raise AppError("gone")

        prev_state: dict[str, Any] | None = None
        curr_last_seq = last_seq

        while True:
            try:
                # 2.1 메시지 조회 및 발송
                page = await self.list_messages(r_id, curr_last_seq, 200)
                for msg in page.messages:
                    yield StreamEvent(event="message", id=msg.seq, data=asdict(msg))
                    curr_last_seq = msg.seq

                # 2.2 상태 조회 및 발송
                view = await self.get(r_id)
                state = {
                    "status": view.status.value,
                    "counters": asdict(view.counters),
                    "pending_question": asdict(view.pending_question) if view.pending_question else None,
                }
                if state != prev_state:
                    yield StreamEvent(event="state", data=state)
                    prev_state = state

                # 2.4 종료 조건
                async with async_session_factory() as session:
                    has_running = await crud.has_running_follow_up(session, r_id)

                if (
                    view.status in (ReviewStatus.done, ReviewStatus.failed, ReviewStatus.expired)
                    and not has_running
                    and not page.messages
                ):
                    yield StreamEvent(event="done")
                    break

            except AppError as e:
                if e.code in ("not_found", "gone"):
                    yield StreamEvent(event="error", data={"code": e.code, "detail": "검토가 삭제되었습니다."})
                    break
                raise

            await asyncio.sleep(1)

    async def receive(
        self,
        review_id: str | uuid.UUID,
        user_input: UserInput,
    ) -> Accepted:
        """답변·되묻기·서류 추가를 받는다.

        항목 ID: JSD-MS-001#ReviewService.receive
        근거: JSD-SEQ-001#SEQ-7, JSD-SEQ-001#SEQ-9, JSD-API-001#POST/api/reviews/{id}/messages, JSD-UC-001#UC-A3
        """
        r_id = _to_uuid(review_id)

        # 1. 검토 확인
        async with async_session_factory() as session:
            review = await crud.get_review(session, r_id)
            if review is None:
                raise AppError("not_found")
            if review.status == "expired":
                raise AppError("gone")

        # 2. 입력 검사
        kind = user_input.kind
        if kind == InputKind.answer:
            if not user_input.question_id:
                raise AppError("missing_input", field="question_id")
            if not user_input.choice and not user_input.text and not user_input.file:
                raise AppError("missing_input", field="text")
        elif kind == InputKind.ask:
            if not user_input.text and not user_input.file:
                raise AppError("missing_input", field="text")

        # 3. 상태 검사
        async with async_session_factory() as session:
            if kind == InputKind.answer:
                q = await crud.get_question(session, user_input.question_id, r_id)
                if q is None or q.status != "pending":
                    raise AppError("wrong_state")
            else:
                has_report = await self.report_service.exists(r_id, session=session)
                if not has_report:
                    raise AppError("wrong_state")
                has_running = await crud.has_running_follow_up(session, r_id)
                if has_running:
                    raise AppError("wrong_state")
                turns_count = await crud.count_follow_up_turns(session, r_id)
                if LIMITS.asks is not None and turns_count >= LIMITS.asks:
                    raise AppError("ask_limit")
                if review.llm_cost_krw >= LIMITS.cost_krw:
                    raise AppError("ask_limit")

        # 4. 파일 처리 (트랜잭션 밖)
        check: FileCheck | None = None
        parsed: ParsedDocument | None = None
        from_cache = False
        if user_input.file is not None:
            check = gate.check_file(user_input.file)
            parsed, from_cache = await self.parse_upload(user_input.file, check, False)

        # 5. 이름 마스킹
        holder_names = await self.registry_service.holder_names(r_id)
        names = list(holder_names)
        if review.counterparty_name:
            names.append(review.counterparty_name)
        masked_text = privacy.mask_text(user_input.text or "", names) if user_input.text else None

        # 6. 짧은 트랜잭션
        async with async_session_factory() as session:
            async with session.begin():
                doc_id: uuid.UUID | None = None
                if user_input.file is not None:
                    assert check is not None
                    assert parsed is not None
                    doc = await self.registry_service.create_extract(
                        review_id=r_id,
                        html=parsed.html,
                        page_count=parsed.page_count,
                        file_sha256=check.file_sha256,
                        session=session,
                    )
                    doc_id = _to_uuid(doc.document_id)
                    if not from_cache:
                        await gate.remember_html(
                            file_sha256=check.file_sha256,
                            html=parsed.html,
                            page_count=parsed.page_count,
                            is_sample=False,
                            session=session,
                        )
                    billed_pages = parsed.billed_pages
                    cost_inc = billed_pages * PRICES.parse_page_krw
                    rev_row = await crud.get_review_for_update(session, r_id)
                    if rev_row:
                        rev_row.parsed_pages += billed_pages
                        rev_row.cost_krw += cost_inc

                if kind == InputKind.answer:
                    assert user_input.question_id is not None
                    q = await crud.get_question(session, user_input.question_id, r_id)
                    assert q is not None
                    # 답변 값 정제
                    answer_val: str
                    if q.kind in ("illegal_building", "proxy", "owner_type"):
                        choice = (user_input.choice or "").strip()
                        raw_text = (user_input.text or "").strip()
                        choice_map = CHOICE_VALUE_MAP.get(q.kind, {})
                        if choice in choice_map:
                            answer_val = choice_map[choice]
                        elif raw_text in choice_map:
                            answer_val = choice_map[raw_text]
                        else:
                            # 텍스트 내 유연한 키워드 추론
                            if q.kind == "illegal_building":
                                if any(w in raw_text for w in ("아님", "아니", "없음", "없", "정상")):
                                    answer_val = "no"
                                elif any(w in raw_text for w in ("위반", "표기 있음", "맞음")):
                                    answer_val = "yes"
                                else:
                                    answer_val = "unknown"
                            elif q.kind == "proxy":
                                if any(w in raw_text for w in ("본인", "소유자", "집주인")):
                                    answer_val = "self"
                                elif any(w in raw_text for w in ("위임장 있음", "인감")):
                                    answer_val = "proxy_with_poa"
                                elif any(w in raw_text for w in ("위임장 없음", "위임장없음", "대리인")):
                                    answer_val = "proxy_without_poa"
                                else:
                                    answer_val = "unknown"
                            elif q.kind == "owner_type":
                                if any(w in raw_text for w in ("법인", "회사", "공공")):
                                    answer_val = "corporation"
                                elif "개인" in raw_text:
                                    answer_val = "individual"
                                else:
                                    answer_val = "unknown"
                            else:
                                answer_val = "unknown"
                    else:
                        if user_input.file is not None and not user_input.choice and not user_input.text:
                            answer_val = "file"
                        else:
                            answer_val = user_input.choice or (masked_text or "")

                    await crud.update_question_answered(
                        session=session,
                        question_id=user_input.question_id,
                        answer=answer_val,
                        answer_document_id=doc_id,
                    )

                    ans_text = user_input.choice or (masked_text or "서류 제출")
                    ans_data = AnswerData(
                        question_id=user_input.question_id,
                        choice=user_input.choice,
                        text=masked_text,
                        document_id=str(doc_id) if doc_id else None,
                    )
                    msg_id = await self.record(
                        review_id=r_id,
                        role=Role.user,
                        kind=MessageKind.answer,
                        text=ans_text,
                        data=asdict(ans_data),
                        session=session,
                    )
                    rec = await session.execute(
                        crud.select(crud.ReviewRecord.seq).where(crud.ReviewRecord.id == _to_uuid(msg_id))
                    )
                    seq = rec.scalar_one()
                    return Accepted(message_id=msg_id, seq=seq, turn_id=None)

                else:
                    # kind == InputKind.ask
                    turn = await crud.insert_follow_up_turn(session, r_id, doc_id)
                    say_text = masked_text or "서류를 올렸습니다"
                    msg_id = await self.record(
                        review_id=r_id,
                        role=Role.user,
                        kind=MessageKind.say,
                        text=say_text,
                        turn_id=turn.id,
                        session=session,
                    )
                    rec = await session.execute(
                        crud.select(crud.ReviewRecord.seq).where(crud.ReviewRecord.id == _to_uuid(msg_id))
                    )
                    seq = rec.scalar_one()
                    return Accepted(message_id=msg_id, seq=seq, turn_id=turn.id)

    async def override_values(
        self,
        review_id: str | uuid.UUID,
        overrides: ValueOverrides,
    ) -> Report:
        """시세·금액 직접 입력으로 다시 판정한다.

        항목 ID: JSD-MS-001#ReviewService.override_values
        근거: JSD-SEQ-001#SEQ-10, JSD-API-001#PATCH/api/reviews/{id}/values, JSD-UC-001#UC-A1 8a
        """
        r_id = _to_uuid(review_id)
        async with async_session_factory() as session:
            review = await crud.get_review(session, r_id)
            if review is None:
                raise AppError("not_found")
            if review.status == "expired":
                raise AppError("gone")
            if review.status != "done":
                raise AppError("wrong_state")
            if await crud.has_running_follow_up(session, r_id):
                raise AppError("wrong_state")

        # 3. 입력 검사
        if overrides.price_manwon is None and not overrides.entries:
            raise AppError("missing_input", field="price_manwon")
        if overrides.price_manwon is not None and overrides.price_manwon < 1:
            raise AppError("missing_input", field="price_manwon")

        # 4. 항목 ID 검증
        if overrides.entries:
            all_entries = await self.registry_service.entries(r_id)
            known_ids = {e.entry_id for e in all_entries}
            for entry_ov in overrides.entries:
                if entry_ov.entry_id not in known_ids:
                    raise AppError("missing_input", field="entries")

        # 5. facts.overrides 갱신
        override_texts: list[str] = []
        async with async_session_factory() as session:
            async with session.begin():
                rev = await crud.get_review_for_update(session, r_id)
                assert rev is not None
                facts = ReviewFacts(rev.facts)
                ov_data = facts.overrides

                if overrides.price_manwon is not None:
                    ov_data["price_manwon"] = overrides.price_manwon
                    override_texts.append(f"시세 {money.format_manwon(overrides.price_manwon)}")

                if overrides.entries:
                    existing_entries = ov_data.setdefault("entries", {})
                    if isinstance(existing_entries, list):
                        existing_entries = {e["entry_id"]: e["amount_manwon"] for e in existing_entries}
                        ov_data["entries"] = existing_entries
                    for e in overrides.entries:
                        existing_entries[e.entry_id] = e.amount_manwon
                        override_texts.append(f"{e.entry_id} {money.format_manwon(e.amount_manwon)}")

                await crud.update_review_facts(session, r_id, facts.to_dict())

        # 6. 직접 입력 레코드 기록
        record_text = f"직접 입력: {', '.join(override_texts)}"
        await self.record(r_id, Role.user, MessageKind.say, record_text)

        # 7. 의견서 재작성 및 반환
        await self.write_report(r_id, None, "직접 입력")
        return await self.report_service.get(r_id)

    async def ask(
        self,
        review_id: str | uuid.UUID,
        args: AskArgs,
    ) -> AskAnswer:
        """질문을 내고 답을 기다린다.

        항목 ID: JSD-MS-001#ReviewService.ask
        근거: JSD-SEQ-001#SEQ-7, JSD-API-002#ask_user, JSD-UC-001#UC-S7, JSD-UC-001#UC-A3 2a·2c·3a
        """
        r_id = _to_uuid(review_id)
        kind_str = args.kind.value if hasattr(args.kind, "value") else str(args.kind)

        # 1. 짧은 트랜잭션 (질문 등록)
        async with async_session_factory() as session:
            async with session.begin():
                n = await crud.count_questions(session, r_id)
                if n >= LIMITS.questions:
                    raise AppError("question_limit")

                options = args.options
                input_type_str = args.input_type.value if hasattr(args.input_type, "value") else str(args.input_type)
                help_url = args.help_url

                if kind_str in ("illegal_building", "proxy", "owner_type"):
                    options = QUESTION_FIXED_OPTIONS[kind_str]
                    input_type_str = "choice"
                    if kind_str == "illegal_building":
                        help_url = "https://www.gov.kr"

                q = await crud.insert_question(
                    session=session,
                    review_id=r_id,
                    asked_no=n + 1,
                    kind=kind_str,
                    text=args.text,
                    why=args.why,
                    input_type=input_type_str,
                    options=options,
                    help_url=help_url,
                )
                qid = q.id

                q_dto = QuestionDTO(
                    question_id=str(qid),
                    kind=QuestionKind(kind_str),
                    text=args.text,
                    why=args.why,
                    input_type=InputType(input_type_str),
                    options=options,
                    help_url=help_url,
                    asked_no=n + 1,
                )
                await self.record(
                    review_id=r_id,
                    role=Role.agent,
                    kind=MessageKind.question,
                    text=args.text,
                    data=asdict(q_dto),
                    session=session,
                )
                await crud.update_review_status(session, r_id, "waiting_user")

        # 2. 폴링 (1초마다 새 세션)
        start_time = time.time()
        while True:
            await asyncio.sleep(1)
            async with async_session_factory() as session:
                q_row = await crud.get_question(session, qid, r_id)
                if q_row is None:
                    raise AppError("not_found")
                if q_row.status == "answered":
                    break

                elapsed = time.time() - start_time
                if elapsed >= LIMITS.answer_timeout_sec:
                    async with session.begin():
                        await crud.update_question_timeout(session, qid)
                        await self.record(
                            review_id=r_id,
                            role=Role.system,
                            kind=MessageKind.notice,
                            text="답변 없이 진행합니다",
                            data=asdict(NoticeData("answer_timeout")),
                            session=session,
                        )
                    break

        # 3. 상태 복구 및 결과 반환
        async with async_session_factory() as session:
            async with session.begin():
                await crud.update_review_status(session, r_id, "running")
                final_q = await crud.get_question(session, qid, r_id)
                assert final_q is not None
                doc_str = str(final_q.answer_document_id) if final_q.answer_document_id else None
                return AskAnswer(
                    question_id=str(final_q.id),
                    answer=final_q.answer or "unknown",
                    document_id=doc_str,
                )

    async def record(
        self,
        review_id: str | uuid.UUID,
        role: Role,
        kind: MessageKind,
        text: str,
        data: dict | None = None,
        turn_id: int | None = None,
        message_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> str:
        """대화 메시지 하나를 쌓는다.

        항목 ID: JSD-MS-001#ReviewService.record
        근거: JSD-SEQ-001#SEQ-3, JSD-DOM-003 4장 2
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> str:
            review = await crud.get_review_for_update(sess, r_id)
            if review is None:
                raise AppError("not_found")

            masked_text = text
            if role in (Role.agent, Role.user):
                holder_names = await self.registry_service.holder_names(r_id, session=sess)
                names_to_mask = list(holder_names)
                if review.counterparty_name:
                    names_to_mask.append(review.counterparty_name)
                masked_text = privacy.mask_text(text, names_to_mask)

            max_seq = await crud.get_max_seq(sess, r_id)
            seq = max_seq + 1

            rec_id = _to_uuid(message_id) if message_id else uuid.uuid4()
            await crud.insert_review_record(
                session=sess,
                record_id=rec_id,
                review_id=r_id,
                seq=seq,
                role=role.value,
                kind=kind.value,
                text=masked_text,
                data=data,
                turn_id=turn_id,
            )
            return str(rec_id)

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                async with sess.begin():
                    return await _execute(sess)

    async def owner_matches(self, review_id: str | uuid.UUID) -> bool | None:
        """소유자와 계약 상대방이 같은지 확인한다.

        항목 ID: JSD-MS-001#ReviewService.owner_matches
        근거: JSD-SEQ-001#SEQ-4, JSD-API-002 1.3
        """
        r_id = _to_uuid(review_id)
        owner = await self.registry_service.owner(r_id)
        async with async_session_factory() as session:
            review = await crud.get_review(session, r_id)

        if not owner or not review or not review.counterparty_name:
            return None

        clean_owner = owner.name.replace(" ", "")
        clean_cp = review.counterparty_name.replace(" ", "")
        return clean_owner == clean_cp

    async def rights_input(self, review_id: str | uuid.UUID) -> RightsInput:
        """합산 입력을 채운다.

        항목 ID: JSD-MS-001#ReviewService.rights_input
        근거: JSD-API-002 1.2, JSD-DOM-002 2.8 RightsInput
        """
        r_id = _to_uuid(review_id)
        async with async_session_factory() as session:
            review = await crud.get_review(session, r_id)
            if review is None:
                raise AppError("not_found")
            facts = ReviewFacts(review.facts)

        entries = await self.registry_service.entries(r_id)
        holder_names = await self.registry_service.holder_names(r_id)
        labels = privacy.person_labels(holder_names)

        entry_facts: list[EntryFact] = []
        for e in entries:
            holder_label = e.holder
            if e.holder and not e.holder_is_corporation:
                holder_label = labels.get(e.holder, "개인")

            entry_facts.append(
                EntryFact(
                    entry_id=e.entry_id,
                    section=e.section,
                    rank_no=e.rank_no,
                    parent_entry_id=e.parent_entry_id,
                    purpose_code=e.purpose_code,
                    cause=e.cause,
                    received_at=e.received_at,
                    amount_manwon=e.amount_manwon,
                    price_manwon=e.price_manwon,
                    holder=holder_label,
                    holder_is_corporation=e.holder_is_corporation,
                    cancelled=e.cancelled,
                )
            )

        prop = await self.registry_service.property(r_id)
        stated = facts.stated
        overrides = facts.overrides

        # 금액 오버라이드 딕셔너리 구성
        amt_ov_raw = overrides.get("entries", {})
        if isinstance(amt_ov_raw, list):
            amount_overrides = {e["entry_id"]: e["amount_manwon"] for e in amt_ov_raw}
        else:
            amount_overrides = dict(amt_ov_raw)

        # 다가구 다른 세입자 보증금
        other_tenants_amt = stated.get("other_tenants_manwon")
        if other_tenants_amt is None and "tenants" in facts.answers:
            tenants_ans = facts.answers["tenants"]
            parsed_amts = factcheck.amounts(tenants_ans)
            if parsed_amts:
                other_tenants_amt = parsed_amts[0]

        return RightsInput(
            entries=entry_facts,
            deposit_manwon=review.deposit_manwon,
            building_type=prop.building_type if prop else BuildingType.other,
            region=prop.region if prop else "",
            override_price_manwon=overrides.get("price_manwon"),
            trade_price_manwon=facts.price.get("price_manwon") if facts.price else None,
            user_price_manwon=stated.get("price_manwon"),
            other_tenants_manwon=other_tenants_amt,
            vacant_rooms=stated.get("vacant_rooms"),
            amount_overrides=amount_overrides,
            today=datetime.now(ZoneInfo("Asia/Seoul")).date(),
        )

    async def signal_input(self, review_id: str | uuid.UUID) -> SignalInput:
        """신호 입력을 채운다.

        항목 ID: JSD-MS-001#ReviewService.signal_input
        근거: JSD-API-002#check_signals, JSD-DOM-002 2.8 SignalInput
        """
        r_id = _to_uuid(review_id)
        async with async_session_factory() as session:
            review = await crud.get_review(session, r_id)
            if review is None:
                raise AppError("not_found")
            facts = ReviewFacts(review.facts)

        prop = await self.registry_service.property(r_id)
        prop_fact = PropertyFact(
            region=prop.region,
            building_type=prop.building_type,
            is_collective=prop.is_collective,
            land_right_unregistered=prop.land_right_unregistered,
            separate_land_registry=prop.separate_land_registry,
        )

        entries = await self.registry_service.entries(r_id)
        holder_names = await self.registry_service.holder_names(r_id)
        labels = privacy.person_labels(holder_names)

        entry_facts = [
            EntryFact(
                entry_id=e.entry_id,
                section=e.section,
                rank_no=e.rank_no,
                parent_entry_id=e.parent_entry_id,
                purpose_code=e.purpose_code,
                cause=e.cause,
                received_at=e.received_at,
                amount_manwon=e.amount_manwon,
                price_manwon=e.price_manwon,
                holder=e.holder if e.holder_is_corporation else labels.get(e.holder or "", "개인"),
                holder_is_corporation=e.holder_is_corporation,
                cancelled=e.cancelled,
            )
            for e in entries
        ]

        answers = facts.answers
        proxy_val = answers.get("proxy", "unknown")
        proxy_status = ProxyStatus(proxy_val) if proxy_val in ProxyStatus._value2member_map_ else ProxyStatus.unknown

        illegal_val = answers.get("illegal_building", "unknown")
        illegal_status = IllegalBuilding(illegal_val) if illegal_val in IllegalBuilding._value2member_map_ else IllegalBuilding.unknown

        owner_val = answers.get("owner_type", "unknown")
        owner_status = OwnerType(owner_val) if owner_val in OwnerType._value2member_map_ else OwnerType.unknown

        owner_matched = await self.owner_matches(r_id)

        ledger_main_use = facts.building.get("main_use") if facts.building else None
        defaulter_matched = facts.defaulter.get("matched") if facts.defaulter else None

        # rights_summary 객체 생성 또는 딕셔너리 변환
        assert facts.rights is not None
        rights_summary = RightsSummary(**facts.rights) if isinstance(facts.rights, dict) else facts.rights

        return SignalInput(
            entries=entry_facts,
            property=prop_fact,
            rights=rights_summary,
            owner_matches_counterparty=owner_matched,
            proxy_status=proxy_status,
            illegal_building=illegal_status,
            owner_type=owner_status,
            ledger_main_use=ledger_main_use,
            defaulter_matched=defaulter_matched,
            tenants_answered=("tenants" in answers),
            failures=list(facts.failures.keys()),
            untried=facts.untried,
            today=datetime.now(ZoneInfo("Asia/Seoul")).date(),
        )

    async def report_input(self, review_id: str | uuid.UUID) -> ReportInput:
        """의견서 입력을 채운다.

        항목 ID: JSD-MS-001#ReviewService.report_input
        근거: JSD-API-002#write_report, JSD-PRD-001#R10
        """
        r_id = _to_uuid(review_id)
        async with async_session_factory() as session:
            review = await crud.get_review(session, r_id)
            if review is None:
                raise AppError("not_found")
            facts = ReviewFacts(review.facts)

        prop = await self.registry_service.property(r_id)
        prop_copy = Property(
            region=prop.region,
            building_type=prop.building_type,
            is_collective=prop.is_collective,
            land_right_unregistered=prop.land_right_unregistered,
            separate_land_registry=prop.separate_land_registry,
            lot_address=None,
            exclusive_area_m2=None,
            building_name=None,
        )

        entries = await self.registry_service.entries(r_id)
        holder_names = await self.registry_service.holder_names(r_id)
        labels = privacy.person_labels(holder_names)

        entries_copy = [
            type(e)(
                entry_id=e.entry_id,
                rank_no=e.rank_no,
                purpose_code=e.purpose_code,
                received_at=e.received_at,
                amount_manwon=e.amount_manwon,
                price_manwon=e.price_manwon,
                holder=e.holder if e.holder_is_corporation else labels.get(e.holder or "", "개인"),
                holder_is_corporation=e.holder_is_corporation,
                cancelled=e.cancelled,
                document_id=e.document_id,
                block_ids=e.block_ids,
                location_label=e.location_label,
                section=e.section,
                parent_entry_id=e.parent_entry_id,
                cause=e.cause,
                cancelled_by_entry_id=e.cancelled_by_entry_id,
            )
            for e in entries
        ]

        answers_map = {QuestionKind(k): v for k, v in facts.answers.items() if k in QuestionKind._value2member_map_}
        use_model = review.llm_cost_krw < LIMITS.cost_krw

        assert facts.rights is not None
        assert facts.check is not None
        rights_obj = _deserialize_rights_summary(facts.rights)
        check_obj = _deserialize_signal_check(facts.check)

        return ReportInput(
            rights=rights_obj,
            check=check_obj,
            property=prop_copy,
            deposit_manwon=review.deposit_manwon,
            contract_type=ContractType(review.contract_type),
            answers=answers_map,
            entries=entries_copy,
            use_model=use_model,
        )

    async def summarize_and_store(self, review_id: str | uuid.UUID) -> RightsSummary:
        """합산을 내고 facts에 둔다.

        항목 ID: JSD-MS-001#ReviewService.summarize_and_store
        근거: JSD-SEQ-001#SEQ-5, JSD-API-002#summarize_rights, JSD-UC-001#UC-S2
        """
        r_id = _to_uuid(review_id)
        inp = await self.rights_input(r_id)
        rights = self.rules_service.summarize(inp)
        rights_dict = asdict(rights)

        async with async_session_factory() as session:
            async with session.begin():
                rev = await crud.get_review_for_update(session, r_id)
                if rev:
                    facts = ReviewFacts(rev.facts)
                    facts.rights = rights_dict
                    await crud.update_review_facts(session, r_id, facts.to_dict())

        return rights

    async def check_and_store(self, review_id: str | uuid.UUID) -> SignalCheck:
        """합산을 다시 낸 뒤 신호·등급을 facts에 둔다.

        항목 ID: JSD-MS-001#ReviewService.check_and_store
        근거: JSD-SEQ-001#SEQ-5, JSD-API-002#check_signals, JSD-UC-001#UC-S3
        """
        r_id = _to_uuid(review_id)
        await self.summarize_and_store(r_id)
        inp = await self.signal_input(r_id)
        check = self.rules_service.check(inp)
        check_dict = asdict(check)

        async with async_session_factory() as session:
            async with session.begin():
                rev = await crud.get_review_for_update(session, r_id)
                if rev:
                    facts = ReviewFacts(rev.facts)
                    facts.check = check_dict
                    await crud.update_review_facts(session, r_id, facts.to_dict())

        return check

    async def write_report(
        self,
        review_id: str | uuid.UUID,
        agent_notes: str | None = None,
        revision_reason: str | None = None,
    ) -> ReportResult:
        """합산·신호·의견서를 다시 내고 카드를 남긴다.

        항목 ID: JSD-MS-001#ReviewService.write_report
        근거: JSD-SEQ-001#SEQ-8, JSD-API-002#write_report, JSD-UC-001#UC-S8, JSD-UC-001#UC-A1 6~7
        """
        r_id = _to_uuid(review_id)
        async with async_session_factory() as session:
            rev = await crud.get_review(session, r_id)
            if not rev:
                raise AppError("not_found")
            cp_name = rev.counterparty_name

        holder_names = await self.registry_service.holder_names(r_id)
        names = list(holder_names)
        if cp_name:
            names.append(cp_name)

        masked_notes = privacy.mask_text(agent_notes, names) if agent_notes else None
        masked_reason = privacy.mask_text(revision_reason, names) if revision_reason else None

        await self.check_and_store(r_id)
        inp = await self.report_input(r_id)
        result = await self.report_service.write(r_id, inp, masked_notes, masked_reason)

        llm_krw = usage_krw(result.tokens_in, result.tokens_out)
        card = ReportCard(
            grade=result.grade,
            signal_count=result.signal_count,
            unknown_count=result.unknown_count,
            rule_version=result.rule_version,
            revision_no=result.revision_no,
            revision_reason=result.revision_reason,
        )

        async with async_session_factory() as session:
            async with session.begin():
                rev_row = await crud.get_review_for_update(session, r_id)
                if rev_row:
                    rev_row.corrections += result.corrections
                    rev_row.tokens_in += result.tokens_in
                    rev_row.tokens_out += result.tokens_out
                    rev_row.llm_cost_krw += llm_krw
                    rev_row.cost_krw += llm_krw

                await self.record(
                    review_id=r_id,
                    role=Role.agent,
                    kind=MessageKind.report,
                    text="",
                    data=asdict(card),
                    session=session,
                )

        return result

    async def finish(
        self,
        review_id: str | uuid.UUID,
        status: ReviewStatus,
    ) -> None:
        """상태를 닫고 사용량을 갱신한다.

        항목 ID: JSD-MS-001#ReviewService.finish
        근거: JSD-SEQ-001#SEQ-2, JSD-SEQ-001#SEQ-9, JSD-INFRA-001#C3
        """
        r_id = _to_uuid(review_id)
        async with async_session_factory() as session:
            async with session.begin():
                review = await crud.get_review_for_update(session, r_id)
                if review is None:
                    return

                now = datetime.now(timezone.utc)
                await crud.update_review_status(session, r_id, status.value, finished_at=now)

                has_report = await self.report_service.exists(r_id, session=session)
                llm_fallback = False
                if has_report:
                    rep = await self.report_service.get(r_id, session=session)
                    llm_fallback = rep.llm_fallback

                await crud.upsert_usage_log(
                    session=session,
                    review_id=r_id,
                    is_sample=(review.sample_id is not None),
                    status=status.value,
                    tool_calls=review.tool_calls,
                    tokens_in=review.tokens_in,
                    tokens_out=review.tokens_out,
                    parsed_pages=review.parsed_pages,
                    cost_krw=review.cost_krw,
                    corrections=review.corrections,
                    llm_fallback=llm_fallback,
                )

    async def require_live(
        self,
        review_id: str | uuid.UUID,
        session: AsyncSession | None = None,
    ) -> None:
        """검토 경로의 404·410 판정.

        항목 ID: JSD-MS-001#ReviewService.require_live
        근거: JSD-SEQ-001#SEQ-C2, JSD-DOM-002 5장 결정 7
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> None:
            status = await crud.get_review_status(sess, r_id)
            if status is None:
                raise AppError("not_found")
            if status == "expired":
                raise AppError("gone")

        if session is not None:
            await _execute(session)
        else:
            async with async_session_factory() as sess:
                await _execute(sess)

    async def purge_expired(self, now: datetime) -> int:
        """보관 기간이 지난 검토를 비운다.

        항목 ID: JSD-MS-001#ReviewService.purge_expired
        근거: JSD-SEQ-001#SEQ-16, JSD-UC-001#UC-A1 9, JSD-DOM-002 5장 결정 4
        """
        async with async_session_factory() as session:
            ids = await crud.list_expired_review_ids(session, now)

        purged_count = 0
        for r_id in ids:
            try:
                async with async_session_factory() as session:
                    async with session.begin():
                        hashes = await self.registry_service.delete_for_review(r_id, session=session)
                        for h in hashes:
                            await gate.forget(h, session=session)
                        await self.citation_service.delete_for_review(r_id, session=session)
                        await self.report_service.delete_for_review(r_id, session=session)
                        await crud.expire_review(session, r_id)
                purged_count += 1
            except Exception:
                continue

        return purged_count

    async def warm_samples(self) -> int:
        """예시 3건의 파싱 캐시를 채운다.

        항목 ID: JSD-MS-001#ReviewService.warm_samples
        근거: JSD-SEQ-001#SEQ-18, JSD-UC-001#UC-A2 4a
        """
        samples = SampleService.list()
        warmed = 0

        for s in samples:
            upload = SampleService.file(s.sample_id)
            check = gate.check_file(upload)
            cached = await gate.cached_html(check.file_sha256)
            if cached is None:
                fixture_html = SampleService.fixture_html(s.sample_id)
                if fixture_html is not None:
                    parsed = ParsedDocument(html=fixture_html, page_count=1, billed_pages=1)
                else:
                    parsed = await self.registry_service.parse(upload.data, check.media_type)
                async with async_session_factory() as session:
                    async with session.begin():
                        await gate.remember_html(
                            check.file_sha256,
                            parsed.html,
                            parsed.page_count,
                            is_sample=True,
                            session=session,
                        )
                warmed += 1
            else:
                warmed += 1

        return warmed

    async def usage_report(self, day: date) -> UsageSummary:
        """하루치 사용량 요약.

        항목 ID: JSD-MS-001#ReviewService.usage_report
        근거: JSD-INFRA-001#C3, JSD-INFRA-001 8장 비용 점검
        """
        tz = ZoneInfo("Asia/Seoul")
        start_dt = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tz)
        end_dt = start_dt + timedelta(days=1)

        async with async_session_factory() as session:
            total, failed, avg_cost = await crud.get_usage_summary_for_period(
                session, start_dt, end_dt
            )

        return UsageSummary(
            day=day,
            reviews=total,
            failed=failed,
            avg_cost_krw=int(round(avg_cost)),
        )
