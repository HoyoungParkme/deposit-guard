"""Registry 도메인 CRUD (DB 접근).

근거: JSD-DOM-002 4.3, JSD-MS-003, JSD-DOM-003
"""

from collections.abc import Sequence
import uuid
from sqlalchemy import case, distinct, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.registry.models import RegistryEntryRow, RegistryExtract


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    return val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))


# 등기부 정렬 순서: 갑구 먼저 (CASE section WHEN 'gap' THEN 0 ELSE 1 END), id 오름차순
_SECTION_ORDER = case((RegistryEntryRow.section == "gap", 0), else_=1)


async def get_extracts(session: AsyncSession, review_id: str | uuid.UUID) -> Sequence[RegistryExtract]:
    """검토의 문서 목록을 생성 순서대로 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        select(RegistryExtract)
        .where(RegistryExtract.review_id == r_id)
        .order_by(RegistryExtract.created_at.asc())
    )
    res = await session.execute(stmt)
    return res.scalars().all()


async def insert_extract(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    kind: str,
    label: str,
    page_count: int,
    file_sha256: str,
    html: str,
    warnings: list[str],
    lot_address: str | None = None,
    region: str | None = None,
    building_type: str | None = None,
    land_right_unregistered: bool | None = None,
    separate_land_registry: bool | None = None,
    exclusive_area_m2: float | None = None,
    building_name: str | None = None,
) -> RegistryExtract:
    """새 등기부 추출물 행을 생성한다."""
    r_id = _to_uuid(review_id)
    extract = RegistryExtract(
        review_id=r_id,
        kind=kind,
        label=label,
        page_count=page_count,
        file_sha256=file_sha256,
        html=html,
        warnings=warnings,
        read_by_agent=False,
        lot_address=lot_address,
        region=region,
        building_type=building_type,
        land_right_unregistered=land_right_unregistered,
        separate_land_registry=separate_land_registry,
        exclusive_area_m2=exclusive_area_m2,
        building_name=building_name,
    )
    session.add(extract)
    await session.flush()
    return extract


async def insert_entries(
    session: AsyncSession,
    entry_rows: list[RegistryEntryRow],
) -> None:
    """등기 항목 여러 개를 순서대로 추가한다."""
    session.add_all(entry_rows)
    await session.flush()


async def get_extract_by_id(
    session: AsyncSession, review_id: str | uuid.UUID, extract_id: str | uuid.UUID
) -> RegistryExtract | None:
    """ID로 등기부 문서를 조회한다."""
    r_id = _to_uuid(review_id)
    e_id = _to_uuid(extract_id)
    stmt = select(RegistryExtract).where(
        RegistryExtract.id == e_id,
        RegistryExtract.review_id == r_id,
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_unread_or_latest_extract(
    session: AsyncSession, review_id: str | uuid.UUID
) -> RegistryExtract | None:
    """에이전트가 아직 읽지 않은 첫 문서 또는 마지막 문서를 조회한다."""
    r_id = _to_uuid(review_id)
    # 1. read_by_agent false 중 생성순 첫 행
    stmt_unread = (
        select(RegistryExtract)
        .where(
            RegistryExtract.review_id == r_id,
            RegistryExtract.read_by_agent.is_(False),
        )
        .order_by(RegistryExtract.created_at.asc())
        .limit(1)
    )
    res_unread = await session.execute(stmt_unread)
    row = res_unread.scalar_one_or_none()
    if row is not None:
        return row

    # 2. 이미 다 읽었으면 생성순 마지막 행
    stmt_latest = (
        select(RegistryExtract)
        .where(RegistryExtract.review_id == r_id)
        .order_by(RegistryExtract.created_at.desc())
        .limit(1)
    )
    res_latest = await session.execute(stmt_latest)
    return res_latest.scalar_one_or_none()


async def mark_read_by_agent(session: AsyncSession, extract_id: uuid.UUID) -> None:
    """에이전트가 읽었음을 표시한다."""
    stmt = (
        update(RegistryExtract)
        .where(RegistryExtract.id == extract_id)
        .values(read_by_agent=True)
    )
    await session.execute(stmt)


async def get_entries_by_extract_id(
    session: AsyncSession, extract_id: uuid.UUID
) -> Sequence[RegistryEntryRow]:
    """추출물 ID에 속한 항목들을 등기부 순서대로 조회한다."""
    stmt = (
        select(RegistryEntryRow)
        .where(RegistryEntryRow.extract_id == extract_id)
        .order_by(_SECTION_ORDER, RegistryEntryRow.id.asc())
    )
    res = await session.execute(stmt)
    return res.scalars().all()


async def get_building_extract(
    session: AsyncSession, review_id: str | uuid.UUID
) -> RegistryExtract | None:
    """건물 등기부(kind != land 첫 행)를 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        select(RegistryExtract)
        .where(
            RegistryExtract.review_id == r_id,
            RegistryExtract.kind != "land",
        )
        .order_by(RegistryExtract.created_at.asc())
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_latest_owner_entry(
    session: AsyncSession, review_id: str | uuid.UUID, extract_id: uuid.UUID
) -> RegistryEntryRow | None:
    """건물 등기부의 현재 소유자 항목을 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        select(RegistryEntryRow)
        .where(
            RegistryEntryRow.review_id == r_id,
            RegistryEntryRow.extract_id == extract_id,
            RegistryEntryRow.section == "gap",
            RegistryEntryRow.cancelled.is_(False),
            RegistryEntryRow.purpose_code.in_(["ownership_preserve", "ownership_transfer"]),
        )
        .order_by(RegistryEntryRow.id.desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_holder_names(
    session: AsyncSession, review_id: str | uuid.UUID
) -> list[str]:
    """개인 권리자 이름을 등기부 순서대로 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        select(RegistryEntryRow.holder)
        .join(RegistryExtract, RegistryEntryRow.extract_id == RegistryExtract.id)
        .where(
            RegistryEntryRow.review_id == r_id,
            RegistryEntryRow.holder.is_not(None),
            (RegistryEntryRow.holder_is_corporation.is_(False))
            | (RegistryEntryRow.holder_is_corporation.is_(None)),
        )
        .order_by(RegistryExtract.created_at.asc(), _SECTION_ORDER, RegistryEntryRow.id.asc())
    )
    res = await session.execute(stmt)
    return [h for h in res.scalars().all() if h]


async def get_entries(
    session: AsyncSession,
    review_id: str | uuid.UUID,
    entry_ids: list[str] | None = None,
) -> Sequence[RegistryEntryRow]:
    """검토의 등기 항목들을 등기부 순서대로 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        select(RegistryEntryRow)
        .join(RegistryExtract, RegistryEntryRow.extract_id == RegistryExtract.id)
        .where(RegistryEntryRow.review_id == r_id)
    )
    if entry_ids is not None:
        stmt = stmt.where(RegistryEntryRow.entry_id.in_(entry_ids))

    stmt = stmt.order_by(
        RegistryExtract.created_at.asc(),
        _SECTION_ORDER,
        RegistryEntryRow.id.asc(),
    )
    res = await session.execute(stmt)
    return res.scalars().all()


async def get_entry_and_html_by_block_id(
    session: AsyncSession, review_id: str | uuid.UUID, block_id: str
) -> tuple[RegistryEntryRow, str] | None:
    """블록 ID를 포함하는 등기 항목과 해당 문서 HTML을 조회한다."""
    r_id = _to_uuid(review_id)
    stmt = (
        select(RegistryEntryRow, RegistryExtract.html)
        .join(RegistryExtract, RegistryEntryRow.extract_id == RegistryExtract.id)
        .where(
            RegistryEntryRow.review_id == r_id,
            RegistryEntryRow.block_ids.contains([block_id]),
        )
        .limit(1)
    )
    res = await session.execute(stmt)
    row = res.first()
    if row is None:
        return None
    return row[0], row[1]


async def delete_for_review(
    session: AsyncSession, review_id: str | uuid.UUID
) -> list[str]:
    """검토의 문서와 항목을 삭제하고 file_sha256 목록을 반환한다."""
    r_id = _to_uuid(review_id)
    stmt_hashes = (
        select(distinct(RegistryExtract.file_sha256))
        .where(RegistryExtract.review_id == r_id)
    )
    res_hashes = await session.execute(stmt_hashes)
    hashes = list(res_hashes.scalars().all())

    # entries delete
    from sqlalchemy import delete
    await session.execute(
        delete(RegistryEntryRow).where(RegistryEntryRow.review_id == r_id)
    )
    # extracts delete
    await session.execute(
        delete(RegistryExtract).where(RegistryExtract.review_id == r_id)
    )
    return hashes
