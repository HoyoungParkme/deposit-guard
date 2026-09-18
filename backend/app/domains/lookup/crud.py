"""Lookup 도메인 데이터베이스 CRUD 연산.

근거: JSD-DOM-002 4.6, JSD-DOM-003, JSD-MS-006
"""

from datetime import date, datetime
from typing import Any
import re
from sqlalchemy import delete, func, literal, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.lookup.models import DefaulterRecord, LookupCache, RegionCode
from app.domains.lookup.schemas import DefaulterRow, RegionCodeRow



async def get_cached_payload(
    session: AsyncSession, key: str, now: datetime
) -> Any | None:
    """유효한 캐시 payload를 조회한다."""
    stmt = select(LookupCache.payload).where(
        LookupCache.key == key,
        LookupCache.expires_at > now,
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def save_cache_payload(
    session: AsyncSession,
    kind: str,
    key: str,
    payload: Any,
    expires_at: datetime,
) -> None:
    """조회 결과를 캐시에 저장한다(upsert)."""
    stmt = (
        pg_insert(LookupCache)
        .values(
            kind=kind,
            key=key,
            payload=payload,
            expires_at=expires_at,
        )
        .on_conflict_do_update(
            index_elements=[LookupCache.key],
            set_={
                "payload": payload,
                "expires_at": expires_at,
                "fetched_at": func.now(),
            },
        )
    )
    await session.execute(stmt)
    await session.commit()


async def find_region_code(session: AsyncSession, addr: str) -> str | None:
    """주소 앞부분과 일치하는 가장 긴 활성 법정동코드를 조회한다.

    근거: JSD-MS-006#LookupService.region_code
    """
    # 낱말 경계를 위해 뒤에 공백 추가
    addr_with_space = addr.strip() + " "
    stmt = (
        select(RegionCode.code)
        .where(
            RegionCode.is_active.is_(True),
            literal(addr_with_space).like(RegionCode.name + " %"),
        )
        .order_by(func.length(RegionCode.name).desc())
        .limit(1)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_max_defaulter_snapshot_date(session: AsyncSession) -> date | None:
    """가장 최근 HUG 명단 스냅샷 날짜를 조회한다."""
    stmt = select(func.max(DefaulterRecord.snapshot_date))
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def count_matching_defaulters(
    session: AsyncSession, normalized_name: str
) -> int:
    """공백을 제거한 성명과 일치하는 명단 건수를 반환한다."""
    stmt = select(func.count(DefaulterRecord.id)).where(
        func.regexp_replace(DefaulterRecord.name, r"\s", "", "g") == normalized_name
    )
    res = await session.execute(stmt)
    count = res.scalar()
    return count or 0


async def replace_defaulter_records(
    session: AsyncSession, rows: list[DefaulterRow], snapshot_date: date
) -> int:
    """전체 명단 스냅샷을 교체한다."""
    await session.execute(delete(DefaulterRecord))
    if rows:
        records = [
            {
                "name": r.name,
                "age": r.age,
                "address": r.address,
                "debt_manwon": r.debt_manwon,
                "default_period": r.default_period,
                "snapshot_date": snapshot_date,
            }
            for r in rows
        ]
        await session.execute(pg_insert(DefaulterRecord).values(records))
    await session.commit()
    return len(rows)


async def upsert_region_code_rows(
    session: AsyncSession, rows: list[RegionCodeRow]
) -> int:
    """법정동코드를 대량 적재 및 갱신한다."""
    if not rows:
        return 0
    records = [{"code": r.code, "name": r.name, "is_active": r.is_active} for r in rows]
    stmt = (
        pg_insert(RegionCode)
        .values(records)
        .on_conflict_do_update(
            index_elements=[RegionCode.code],
            set_={
                "name": pg_insert(RegionCode).excluded.name,
                "is_active": pg_insert(RegionCode).excluded.is_active,
            },
        )
    )
    res = await session.execute(stmt)
    await session.commit()
    return len(rows)


async def delete_expired_lookup_caches(session: AsyncSession, now: datetime) -> int:
    """만료된 조회 캐시를 삭제한다."""
    stmt = delete(LookupCache).where(LookupCache.expires_at < now)
    res = await session.execute(stmt)
    await session.commit()
    return res.rowcount or 0
