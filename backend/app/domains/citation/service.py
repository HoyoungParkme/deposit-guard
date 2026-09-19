"""CitationService 인용 생성, 조회, 역추적 서비스.

항목 ID: JSD-MS-007
근거: JSD-DOM-002 4.7, JSD-DOM-003, JSD-SEQ-001, JSD-API-002
규칙: 인용 행 하나가 진실. 지어낼 수 없음(RegistryService.entries 대조 필수). 트랜잭션은 호출자 관리.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import re
from typing import Any
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.core.errors import AppError
from app.domains.citation import crud
from app.domains.registry.service import RegistryService
from app.shared.types import (
    BlockUsageItem,
    BlockUsages,
    Citation,
    CitationRef,
    CitationUse,
    CitedText,
)


class CitationService:
    """등기부 인용 생성 및 역방향 참조 관리 서비스."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        registry_service: RegistryService | None = None,
    ):
        self._session = session
        self._registry_service = registry_service

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

    async def resolve_markers(
        self,
        review_id: str,
        text: str,
        used_in: CitationUse,
        ref: str,
        session: AsyncSession | None = None,
    ) -> CitedText:
        """문장 속 {{entry:...}} 표식을 검증하고 인용 행을 생성하여 {{c1}} 형태로 치환한다.

        항목 ID: JSD-MS-007#CitationService.resolve_markers
        근거: JSD-SEQ-001#SEQ-3, JSD-SEQ-001#SEQ-8, JSD-API-002 1.4, JSD-UC-001#UC-A1 7a
        """
        pattern = re.compile(r"\{\{entry:([^}]+)\}\}")
        matches = list(pattern.finditer(text))
        if not matches:
            return CitedText(text=text, citations=[], dropped=0)

        # 1. 모든 표식의 entry_id 수집
        raw_ids: list[str] = []
        for m in matches:
            for piece in m.group(1).split(","):
                clean = piece.strip()
                if clean and clean not in raw_ids:
                    raw_ids.append(clean)

        # 2. RegistryService 대조
        known_entries: dict[str, Any] = {}
        if self._registry_service and raw_ids:
            entries = await self._registry_service.entries(review_id, raw_ids)
            known_entries = {e.entry_id: e for e in entries}

        rev_uuid = review_id if isinstance(review_id, uuid.UUID) else uuid.UUID(str(review_id))
        async with self._session_ctx(session) as sess:
            existing_count = await crud.count_existing_citations(
                sess, rev_uuid, used_in.value, ref
            )
            current_n = existing_count

            citations: list[Citation] = []
            dropped = 0
            last_end = 0
            chunks: list[str] = []

            for m in matches:
                chunks.append(text[last_end : m.start()])
                marker_ids = [p.strip() for p in m.group(1).split(",") if p.strip()]
                hits = [known_entries[i] for i in marker_ids if i in known_entries]

                if not hits:
                    dropped += 1
                else:
                    doc_groups: dict[str, list[Any]] = {}
                    for e in hits:
                        doc_groups.setdefault(e.document_id, []).append(e)

                    group_keys: list[str] = []
                    for doc_id, g_entries in doc_groups.items():
                        current_n += 1
                        key = f"c{current_n}"
                        group_keys.append(key)

                        sentence = text[:40].strip()
                        usage_label = (
                            f"결론: {sentence}"
                            if used_in == CitationUse.conclusion
                            else sentence
                        )

                        first_entry = g_entries[0]
                        label = first_entry.location_label or "등기부"
                        entry_ids = [e.entry_id for e in g_entries]
                        block_ids: list[str] = []
                        for e in g_entries:
                            for bid in e.block_ids:
                                if bid not in block_ids:
                                    block_ids.append(bid)

                        doc_uuid = doc_id if isinstance(doc_id, uuid.UUID) else uuid.UUID(str(doc_id))
                        await crud.insert_citation_row(
                            session=sess,
                            review_id=rev_uuid,
                            used_in=used_in.value,
                            ref=ref,
                            key=key,
                            label=label,
                            usage_label=usage_label,
                            document_id=doc_uuid,
                            entry_ids=entry_ids,
                            block_ids=block_ids,
                        )

                        citations.append(
                            Citation(
                                key=key,
                                label=label,
                                document_id=doc_id,
                                block_ids=block_ids,
                                entry_ids=entry_ids,
                            )
                        )

                    chunks.append("".join(f"{{{{{k}}}}}" for k in group_keys))
                last_end = m.end()

            chunks.append(text[last_end:])
            modified_text = "".join(chunks)
            cleaned_text = re.sub(r" +", " ", modified_text).strip()
            return CitedText(text=cleaned_text, citations=citations, dropped=dropped)

    async def cite(
        self,
        review_id: str,
        used_in: CitationUse,
        ref: str,
        usage_label: str,
        entry_ids: list[str],
        session: AsyncSession | None = None,
    ) -> list[Citation]:
        """항목 ID 목록으로 인용 행을 직접 생성한다.

        항목 ID: JSD-MS-007#CitationService.cite
        근거: JSD-SEQ-001#SEQ-8, JSD-DOM-001#Citation
        """
        if not entry_ids or not self._registry_service:
            return []

        hits = await self._registry_service.entries(review_id, entry_ids)
        if not hits:
            return []

        rev_uuid = review_id if isinstance(review_id, uuid.UUID) else uuid.UUID(str(review_id))
        async with self._session_ctx(session) as sess:
            current_n = await crud.count_existing_citations(
                sess, rev_uuid, used_in.value, ref
            )

            doc_groups: dict[str, list[Any]] = {}
            for e in hits:
                doc_groups.setdefault(e.document_id, []).append(e)

            citations: list[Citation] = []
            for doc_id, g_entries in doc_groups.items():
                current_n += 1
                key = f"c{current_n}"
                first_entry = g_entries[0]
                label = first_entry.location_label or "등기부"
                g_ids = [e.entry_id for e in g_entries]
                b_ids: list[str] = []
                for e in g_entries:
                    for bid in e.block_ids:
                        if bid not in b_ids:
                            b_ids.append(bid)

                doc_uuid = doc_id if isinstance(doc_id, uuid.UUID) else uuid.UUID(str(doc_id))
                await crud.insert_citation_row(
                    session=sess,
                    review_id=rev_uuid,
                    used_in=used_in.value,
                    ref=ref,
                    key=key,
                    label=label,
                    usage_label=usage_label[:40],
                    document_id=doc_uuid,
                    entry_ids=g_ids,
                    block_ids=b_ids,
                )

                citations.append(
                    Citation(
                        key=key,
                        label=label,
                        document_id=doc_id,
                        block_ids=b_ids,
                        entry_ids=g_ids,
                    )
                )

            return citations

    async def for_messages(
        self,
        review_id: str,
        message_ids: list[str | uuid.UUID],
        session: AsyncSession | None = None,
    ) -> dict[str, list[Citation]]:
        """메시지들의 인용 목록을 조회한다.

        항목 ID: JSD-MS-007#CitationService.for_messages
        근거: JSD-SEQ-001#SEQ-11, JSD-API-001#GET/api/reviews/{id}/messages
        """
        if not message_ids:
            return {}

        clean_ids = [str(m) for m in message_ids]
        rev_uuid = uuid.UUID(str(review_id))
        async with self._session_ctx(session) as sess:
            rows = await crud.list_citations_for_messages(
                sess, rev_uuid, clean_ids
            )

            result: dict[str, list[Citation]] = {}
            for r in rows:
                result.setdefault(r.ref, []).append(
                    Citation(
                        key=r.key,
                        label=r.label,
                        document_id=str(r.document_id),
                        block_ids=r.block_ids,
                        entry_ids=r.entry_ids,
                    )
                )
            return result

    async def for_report(
        self,
        review_id: str,
        session: AsyncSession | None = None,
    ) -> list[CitationRef]:
        """의견서의 인용 목록을 조회한다.

        항목 ID: JSD-MS-007#CitationService.for_report
        근거: JSD-SEQ-001#SEQ-14, JSD-API-001#GET/api/reviews/{id}/report
        """
        rev_uuid = uuid.UUID(str(review_id))
        async with self._session_ctx(session) as sess:
            rows = await crud.list_citations_for_report(sess, rev_uuid)

            return [
                CitationRef(
                    used_in=CitationUse(r.used_in),
                    ref=r.ref,
                    citation=Citation(
                        key=r.key,
                        label=r.label,
                        document_id=str(r.document_id),
                        block_ids=r.block_ids,
                        entry_ids=r.entry_ids,
                    ),
                )
                for r in rows
            ]

    async def usages(
        self,
        review_id: str,
        block_id: str,
        session: AsyncSession | None = None,
    ) -> BlockUsages:
        """원문 블록이 쓰인 곳(역방향 참조)을 조회한다.

        항목 ID: JSD-MS-007#CitationService.usages
        근거: JSD-SEQ-001#SEQ-13, JSD-API-001#GET/api/reviews/{id}/blocks/{blockId}
        """
        if not self._registry_service:
            raise AppError("not_found", "RegistryService가 제공되지 않았습니다.")

        ex = await self._registry_service.block_excerpt(review_id, block_id)
        if ex is None:
            raise AppError("not_found", "해당 블록은 이 검토의 등기 항목이 아닙니다.")

        rev_uuid = uuid.UUID(str(review_id))
        async with self._session_ctx(session) as sess:
            rows = await crud.list_citations_for_block(sess, rev_uuid, block_id)

            seen: set[tuple[str, str]] = set()
            items: list[BlockUsageItem] = []

            for r in rows:
                pair = (r.used_in, r.ref)
                if pair in seen:
                    continue
                seen.add(pair)

                sig_code = r.ref if r.used_in == "signal" else None
                msg_id = r.ref if r.used_in == "message" else None

                items.append(
                    BlockUsageItem(
                        kind=r.used_in,
                        label=r.usage_label,
                        signal_code=sig_code,
                        message_id=msg_id,
                    )
                )

            return BlockUsages(
                block_id=block_id,
                excerpt=ex.excerpt,
                used_in=items,
            )

    async def clear_report(
        self,
        review_id: str,
        session: AsyncSession | None = None,
    ) -> None:
        """이전 의견서의 인용을 모두 삭제한다.

        항목 ID: JSD-MS-007#CitationService.clear_report
        근거: JSD-SEQ-001#SEQ-8, JSD-MS-008#ReportService.write
        """
        rev_uuid = uuid.UUID(str(review_id))
        async with self._session_ctx(session) as sess:
            await crud.delete_citations_for_report(sess, rev_uuid)

    async def delete_for_review(
        self,
        review_id: str,
        session: AsyncSession | None = None,
    ) -> None:
        """검토의 모든 인용을 삭제한다.

        항목 ID: JSD-MS-007#CitationService.delete_for_review
        근거: JSD-SEQ-001#SEQ-15, JSD-SEQ-001#SEQ-16
        """
        rev_uuid = uuid.UUID(str(review_id))
        async with self._session_ctx(session) as sess:
            await crud.delete_all_citations_for_review(sess, rev_uuid)
