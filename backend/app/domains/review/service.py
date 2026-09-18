"""Review 도메인 서비스 (ReviewService).

근거: JSD-DOM-002 4.1, JSD-MS-001, JSD-SEQ-001, JSD-API-001, JSD-DOM-003
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LIMITS, PRICES
from app.core.db import async_session_factory
from app.core.errors import AppError
from app.domains.gate import service as gate
from app.domains.registry.service import RegistryService
from app.domains.review import crud
from app.domains.review.schemas import (
    QuestionDTO,
    ReviewCounters,
    ReviewCreated,
    ReviewDocumentItem,
    ReviewSubject,
    ReviewView,
)
from app.domains.sample.service import SampleService
from app.shared import privacy
from app.shared.types import (
    ContractType,
    DocKind,
    FileCheck,
    InputType,
    MessageKind,
    ParsedDocument,
    QuestionKind,
    ReviewStatus,
    Role,
    Upload,
)


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    return val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))


class ReviewService:
    """검토의 상태·한도·대화 기록·세션 정보 채우기 서비스."""

    def __init__(
        self,
        registry_service: RegistryService | None = None,
    ) -> None:
        self.registry_service: RegistryService = registry_service or RegistryService()

    async def parse_upload(
        self,
        upload: Upload,
        check: FileCheck,
        is_sample: bool,
    ) -> tuple[ParsedDocument, bool]:
        """파싱 캐시를 보고 없으면 업스테이지로 파싱.

        항목 ID: JSD-MS-001#ReviewService.parse_upload
        근거: JSD-SEQ-001#SEQ-1, JSD-DOM-002 5장 결정 3
        """
        cached = await gate.cached_html(check.file_sha256)
        if cached is not None:
            return cached, True

        parsed = await self.registry_service.parse(upload.data, check.media_type)
        return parsed, False

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
        parsed, from_cache = await self.parse_upload(active_upload, check, is_sample)

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

        # 8. 반환 (에이전트 루프는 B2에서 라우터가 띄운다)
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

            # 스텁: ReportService.exists -> False (B2가 푼다)
            has_report = False

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
            # 1. 행 잠금
            review = await crud.get_review_for_update(sess, r_id)
            if review is None:
                raise AppError("not_found")

            # 2. 텍스트 마스킹 (agent, user 발화)
            masked_text = text
            if role in (Role.agent, Role.user):
                holder_names = await self.registry_service.holder_names(r_id, session=sess)
                names_to_mask = list(holder_names)
                if review.counterparty_name:
                    names_to_mask.append(review.counterparty_name)
                masked_text = privacy.mask_text(text, names_to_mask)

            # 3. seq 부여
            max_seq = await crud.get_max_seq(sess, r_id)
            seq = max_seq + 1

            # 4. 레코드 삽입
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
