"""Gate 도메인 CRUD (DB 접근).

근거: JSD-DOM-002 4.11, JSD-MS-011, JSD-DOM-003
"""

from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LIMITS
from app.domains.gate.models import FileCache, IpQuota


async def is_sample_file_cached(session: AsyncSession, file_sha256: str) -> bool:
    """캐시된 예시 파일인지 확인한다."""
    stmt = select(FileCache.id).where(
        FileCache.file_sha256 == file_sha256,
        FileCache.is_sample.is_(True),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def try_take_quota(session: AsyncSession, ip_hash: str, today: date) -> bool:
    """원자적으로 IP 하루 한도를 1 증가시키고 한도 내인지 확인한다 (JSD-MS-011#gate.take_quota).

    한 SQL 문장으로 ON CONFLICT ... WHERE used < LIMITS.ip_daily 수행.
    반환: 증가 성공 시 True, 한도 초과(행 미반환) 시 False.
    """
    stmt = text(
        """
        INSERT INTO ip_quotas (ip_hash, day, used)
        VALUES (:ip_hash, :day, 1)
        ON CONFLICT (ip_hash, day)
        DO UPDATE SET used = ip_quotas.used + 1
        WHERE ip_quotas.used < :max_daily
        RETURNING used
        """
    )
    result = await session.execute(
        stmt,
        {"ip_hash": ip_hash, "day": today, "max_daily": LIMITS.ip_daily},
    )
    row = result.fetchone()
    return row is not None


async def get_cached_file(
    session: AsyncSession, file_sha256: str, now: datetime
) -> FileCache | None:
    """만료되지 않은 파싱 캐시를 조회한다 (JSD-MS-011#gate.cached_html)."""
    stmt = select(FileCache).where(
        FileCache.file_sha256 == file_sha256,
        (FileCache.expires_at.is_(None)) | (FileCache.expires_at > now),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_file_cache(
    session: AsyncSession,
    file_sha256: str,
    html: str,
    page_count: int,
    is_sample: bool,
    now: datetime,
) -> None:
    """파싱 캐시를 삽입 또는 갱신한다 (JSD-MS-011#gate.remember_html)."""
    expires_at = (
        None if is_sample else now + timedelta(hours=LIMITS.retention_hours)
    )
    stmt = insert(FileCache).values(
        file_sha256=file_sha256,
        html=html,
        page_count=page_count,
        is_sample=is_sample,
        created_at=now,
        expires_at=expires_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["file_sha256"],
        set_={
            "html": stmt.excluded.html,
            "page_count": stmt.excluded.page_count,
            "is_sample": FileCache.is_sample | stmt.excluded.is_sample,
            "expires_at": text(
                """
                CASE
                    WHEN file_caches.is_sample OR EXCLUDED.is_sample THEN NULL
                    ELSE EXCLUDED.expires_at
                END
                """
            ),
            "created_at": now,
        },
    )
    await session.execute(stmt)
