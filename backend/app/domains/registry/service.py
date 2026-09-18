"""Registry 도메인 서비스 (RegistryService).

근거: JSD-DOM-002 4.3, JSD-MS-003, JSD-SEQ-001, JSD-API-001, JSD-API-002
"""

from __future__ import annotations

from html.parser import HTMLParser
import logging
import re
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.core.errors import AppError
from app.domains.registry import crud, service_parse
from app.domains.registry.adapters.upstage import UpstageParser
from app.domains.registry.models import RegistryEntryRow
from app.domains.registry.ports import DocumentParser
from app.domains.registry.schemas import (
    BlockExcerpt,
    DocumentBrief,
    Owner,
    Property,
    Registry,
    RegistryEntry,
)
from app.shared.types import (
    BuildingType,
    DocKind,
    ParsedDocument,
    PurposeCode,
    Section,
)

logger = logging.getLogger(__name__)


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    return val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))


class _BlockExcerptExtractor(HTMLParser):
    """HTML에서 특정 data-block-id의 텍스트를 추출하는 파서."""

    def __init__(self, target_block_id: str) -> None:
        super().__init__()
        self.target_block_id = target_block_id
        self._matched = False
        self._depth = 0
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        if attr_dict.get("data-block-id") == self.target_block_id:
            self._matched = True
            self._depth = 1
        elif self._matched:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._matched:
            self._depth -= 1
            if self._depth <= 0:
                self._matched = False

    def handle_data(self, data: str) -> None:
        if self._matched:
            self.texts.append(data)


class RegistryService:
    """등기부 도메인 서비스."""

    def __init__(self, parser: DocumentParser | None = None) -> None:
        self.parser: DocumentParser = parser or UpstageParser()

    async def parse(self, data: bytes, media_type: str) -> ParsedDocument:
        """파일 바이트를 업스테이지 HTML로.

        항목 ID: JSD-MS-003#RegistryService.parse
        근거: JSD-SEQ-001#SEQ-1, JSD-UC-001#UC-S1 1·1a, JSD-INFRA-001#C8
        """
        return await self.parser.parse(data, media_type)

    async def create_extract(
        self,
        review_id: str | uuid.UUID,
        html: str,
        page_count: int,
        file_sha256: str,
        session: AsyncSession,
    ) -> DocumentBrief:
        """파싱 HTML에서 항목을 읽어 저장.

        항목 ID: JSD-MS-003#RegistryService.create_extract
        근거: JSD-SEQ-001#SEQ-1, JSD-SEQ-001#SEQ-7, JSD-UC-001#UC-S1 2~6, JSD-DOM-001#RegistryExtract
        """
        r_id = _to_uuid(review_id)
        # 1. 파싱 (갑구·을구가 없으면 거기서 not_registry 예외 발생)
        parsed = service_parse.read_extract(html)

        # 2. 기존 문서 조회
        existing = await crud.get_extracts(session, r_id)

        # 3. 문서 수 검사
        if len(existing) >= 2:
            raise AppError("wrong_state")
        if len(existing) == 1 and parsed.kind != DocKind.land:
            raise AppError("wrong_state")

        prefix = "land-" if len(existing) > 0 else ""

        # 5. 라벨 설정
        if parsed.kind == DocKind.building:
            label = "건물 등기부"
        elif parsed.kind == DocKind.collective:
            label = "집합건물 등기부"
        else:
            label = "토지 등기부"

        # 6. registry_extracts insert
        prop = parsed.property if parsed.kind != DocKind.land else None
        extract = await crud.insert_extract(
            session=session,
            review_id=r_id,
            kind=parsed.kind.value,
            label=label,
            page_count=page_count,
            file_sha256=file_sha256,
            html=parsed.panel_html,
            warnings=parsed.warnings,
            lot_address=prop.lot_address if prop else None,
            region=prop.region if prop else None,
            building_type=prop.building_type.value if prop else None,
            land_right_unregistered=prop.land_right_unregistered if prop else None,
            separate_land_registry=prop.separate_land_registry if prop else None,
            exclusive_area_m2=prop.exclusive_area_m2 if prop else None,
            building_name=prop.building_name if prop else None,
        )

        # 7. registry_entries insert
        entry_rows: list[RegistryEntryRow] = []
        for e in parsed.entries:
            e_id = f"{prefix}{e.entry_id}"
            p_id = f"{prefix}{e.parent_entry_id}" if e.parent_entry_id else None
            c_id = f"{prefix}{e.cancelled_by_entry_id}" if e.cancelled_by_entry_id else None
            loc = f"토지 {e.location_label}" if prefix else e.location_label

            row = RegistryEntryRow(
                extract_id=extract.id,
                review_id=r_id,
                entry_id=e_id,
                section=e.section.value,
                rank_no=e.rank_no,
                parent_entry_id=p_id,
                purpose_code=e.purpose_code.value,
                purpose_text=e.purpose_text,
                received_at=e.received_at,
                receipt_no=e.receipt_no,
                cause=e.cause,
                amount_manwon=e.amount_manwon,
                price_manwon=e.price_manwon,
                holder=e.holder,
                holder_is_corporation=e.holder_is_corporation,
                cancelled=e.cancelled,
                cancelled_by_entry_id=c_id,
                block_ids=e.block_ids,
                location_label=loc,
            )
            entry_rows.append(row)

        await crud.insert_entries(session, entry_rows)

        return DocumentBrief(
            document_id=str(extract.id),
            kind=parsed.kind,
            label=label,
            page_count=page_count,
        )

    async def read(
        self,
        review_id: str | uuid.UUID,
        document_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> Registry:
        """에이전트가 읽을 등기부 한 장.

        항목 ID: JSD-MS-003#RegistryService.read
        근거: JSD-SEQ-001#SEQ-4, JSD-API-002#read_registry, JSD-UC-001#UC-S1 6
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> Registry:
            if document_id:
                d_id = _to_uuid(document_id)
                ex = await crud.get_extract_by_id(sess, r_id, d_id)
                if ex is None:
                    raise AppError("not_found")
            else:
                ex = await crud.get_unread_or_latest_extract(sess, r_id)
                if ex is None:
                    raise AppError("not_found")

            # 에이전트가 읽었음을 표시
            await crud.mark_read_by_agent(sess, ex.id)

            # 항목 조회
            rows = await crud.get_entries_by_extract_id(sess, ex.id)

            # Property 복원
            building_prop: Property | None = None
            if ex.kind != "land" and ex.building_type is not None:
                building_prop = Property(
                    region=ex.region or "",
                    building_type=BuildingType(ex.building_type),
                    is_collective=(ex.kind == "collective"),
                    land_right_unregistered=ex.land_right_unregistered or False,
                    separate_land_registry=ex.separate_land_registry or False,
                    lot_address=ex.lot_address,
                    exclusive_area_m2=ex.exclusive_area_m2,
                    building_name=ex.building_name,
                )

            gap_entries: list[RegistryEntry] = []
            eul_entries: list[RegistryEntry] = []

            for r in rows:
                dto = RegistryEntry(
                    entry_id=r.entry_id,
                    rank_no=r.rank_no,
                    purpose_code=PurposeCode(r.purpose_code),
                    received_at=r.received_at,
                    amount_manwon=r.amount_manwon,
                    price_manwon=r.price_manwon,
                    holder=r.holder,
                    holder_is_corporation=r.holder_is_corporation,
                    cancelled=r.cancelled,
                    document_id=str(r.extract_id),
                    block_ids=r.block_ids,
                    location_label=r.location_label,
                    section=Section(r.section),
                    parent_entry_id=r.parent_entry_id,
                    cause=r.cause,
                    cancelled_by_entry_id=r.cancelled_by_entry_id,
                )
                if r.section == "gap":
                    gap_entries.append(dto)
                else:
                    eul_entries.append(dto)

            return Registry(
                document_id=str(ex.id),
                doc_kind=DocKind(ex.kind),
                building=building_prop,
                gap=gap_entries,
                eul=eul_entries,
                warnings=ex.warnings,
            )

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                async with sess.begin():
                    return await _execute(sess)

    async def list(
        self,
        review_id: str | uuid.UUID,
        session: AsyncSession | None = None,
    ) -> list[DocumentBrief]:
        """문서 목록.

        항목 ID: JSD-MS-003#RegistryService.list
        근거: JSD-API-001#GET/api/reviews/{id}/documents, JSD-SEQ-001#SEQ-12
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> list[DocumentBrief]:
            extracts = await crud.get_extracts(sess, r_id)
            return [
                DocumentBrief(
                    document_id=str(ex.id),
                    kind=DocKind(ex.kind),
                    label=ex.label,
                    page_count=ex.page_count,
                )
                for ex in extracts
            ]

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)

    async def get_html(
        self,
        review_id: str | uuid.UUID,
        document_id: str,
        session: AsyncSession | None = None,
    ) -> str:
        """문서 패널 원문.

        항목 ID: JSD-MS-003#RegistryService.get_html
        근거: JSD-API-001#GET/api/reviews/{id}/documents/{documentId}, JSD-UI-001#UI-2 요소 7
        """
        r_id = _to_uuid(review_id)
        d_id = _to_uuid(document_id)

        async def _execute(sess: AsyncSession) -> str:
            ex = await crud.get_extract_by_id(sess, r_id, d_id)
            if ex is None:
                raise AppError("not_found")
            return ex.html

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)

    async def property(
        self,
        review_id: str | uuid.UUID,
        session: AsyncSession | None = None,
    ) -> Property | None:
        """건물 등기부의 주택 정보.

        항목 ID: JSD-MS-003#RegistryService.property
        근거: JSD-SEQ-001#SEQ-6, JSD-SEQ-001#SEQ-12, JSD-UC-001#UC-S2
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> Property | None:
            ex = await crud.get_building_extract(sess, r_id)
            if ex is None or ex.building_type is None:
                return None
            return Property(
                region=ex.region or "",
                building_type=BuildingType(ex.building_type),
                is_collective=(ex.kind == "collective"),
                land_right_unregistered=ex.land_right_unregistered or False,
                separate_land_registry=ex.separate_land_registry or False,
                lot_address=ex.lot_address,
                exclusive_area_m2=ex.exclusive_area_m2,
                building_name=ex.building_name,
            )

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)

    async def owner(
        self,
        review_id: str | uuid.UUID,
        session: AsyncSession | None = None,
    ) -> Owner | None:
        """현재 소유자.

        항목 ID: JSD-MS-003#RegistryService.owner
        근거: JSD-SEQ-001#SEQ-4, JSD-SEQ-001#SEQ-6, JSD-UC-001#UC-S6 2a
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> Owner | None:
            ex = await crud.get_building_extract(sess, r_id)
            if ex is None:
                return None
            row = await crud.get_latest_owner_entry(sess, r_id, ex.id)
            if row is None or not row.holder:
                return None

            holder_str = row.holder
            # 여러 이름인 경우 첫 이름만
            names = re.split(r"[,·\s]+", holder_str.strip())
            name = names[0]
            if len(names) > 1:
                logger.warning("co_owned", extra={"review_id": str(r_id)})

            return Owner(
                name=name,
                is_corporation=row.holder_is_corporation or False,
                acquired_at=row.received_at,
                cause=PurposeCode(row.purpose_code),
                entry_id=row.entry_id,
            )

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)

    async def holder_names(
        self,
        review_id: str | uuid.UUID,
        session: AsyncSession | None = None,
    ) -> list[str]:
        """개인 권리자 이름, 등기부 순서.

        항목 ID: JSD-MS-003#RegistryService.holder_names
        근거: JSD-API-002 1.3, JSD-MS-002#service_agent.mask_for_model
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> list[str]:
            raw_names = await crud.get_holder_names(sess, r_id)
            results: list[str] = []
            for h in raw_names:
                for part in re.split(r"[,·\s]+", h.strip()):
                    if part:
                        results.append(part)
            return results

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)

    async def entries(
        self,
        review_id: str | uuid.UUID,
        entry_ids: list[str] | None = None,
        session: AsyncSession | None = None,
    ) -> list[RegistryEntry]:
        """이 검토의 등기 항목.

        항목 ID: JSD-MS-003#RegistryService.entries
        근거: JSD-SEQ-001#SEQ-3, JSD-SEQ-001#SEQ-5, JSD-SEQ-001#SEQ-10
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> list[RegistryEntry]:
            rows = await crud.get_entries(sess, r_id, entry_ids)
            return [
                RegistryEntry(
                    entry_id=r.entry_id,
                    rank_no=r.rank_no,
                    purpose_code=PurposeCode(r.purpose_code),
                    received_at=r.received_at,
                    amount_manwon=r.amount_manwon,
                    price_manwon=r.price_manwon,
                    holder=r.holder,
                    holder_is_corporation=r.holder_is_corporation,
                    cancelled=r.cancelled,
                    document_id=str(r.extract_id),
                    block_ids=r.block_ids,
                    location_label=r.location_label,
                    section=Section(r.section),
                    parent_entry_id=r.parent_entry_id,
                    cause=r.cause,
                    cancelled_by_entry_id=r.cancelled_by_entry_id,
                )
                for r in rows
            ]

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)

    async def block_excerpt(
        self,
        review_id: str | uuid.UUID,
        block_id: str,
        session: AsyncSession | None = None,
    ) -> BlockExcerpt | None:
        """원문 블록 하나의 항목과 한 줄.

        항목 ID: JSD-MS-003#RegistryService.block_excerpt
        근거: JSD-SEQ-001#SEQ-13, JSD-API-001#GET/api/reviews/{id}/blocks/{blockId}
        """
        r_id = _to_uuid(review_id)

        async def _execute(sess: AsyncSession) -> BlockExcerpt | None:
            pair = await crud.get_entry_and_html_by_block_id(sess, r_id, block_id)
            if pair is None:
                return None
            row, html = pair

            extractor = _BlockExcerptExtractor(block_id)
            extractor.feed(html)
            extractor.close()

            raw_text = " ".join("".join(extractor.texts).split())
            excerpt = raw_text[:80]

            return BlockExcerpt(
                entry_id=row.entry_id,
                document_id=str(row.extract_id),
                excerpt=excerpt,
            )

        if session is not None:
            return await _execute(session)
        else:
            async with async_session_factory() as sess:
                return await _execute(sess)
