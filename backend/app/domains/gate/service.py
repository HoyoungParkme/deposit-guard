"""Gate 도메인 서비스.

근거: JSD-DOM-002 4.11, JSD-MS-011, JSD-SEQ-001, JSD-UC-001
"""

from datetime import date, datetime, timezone
import hashlib
import hmac
from io import BytesIO
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LIMITS, settings
from app.core.db import async_session_factory
from app.core.errors import AppError
from app.domains.gate import crud
from app.shared.types import FileCheck, ParsedDocument, Upload


def _hmac_hex(val: str) -> str:
    """앱 비밀키 기반 HMAC-SHA256 16진수 해시 생성."""
    return hmac.new(
        settings.app_secret.encode("utf-8"),
        val.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def check_file(upload: Upload) -> FileCheck:
    """형식·크기·쪽수·암호 검사와 해시.

    항목 ID: JSD-MS-011#gate.check_file
    근거: JSD-SEQ-001#SEQ-1, JSD-UC-001#UC-A1 2a, JSD-PRD-001#R1
    """
    data = upload.data
    # 1. 크기 검사
    if len(data) > LIMITS.file_mb * 1024 * 1024:
        raise AppError("invalid_file", field="file")

    # 2. 바이트 머리로 형식 검사
    media_type: str
    if data.startswith(b"%PDF-"):
        media_type = "application/pdf"
    elif data.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    else:
        raise AppError("invalid_file", field="file")

    # 3. 쪽수 및 암호 검사
    pages: int
    if media_type == "application/pdf":
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise AppError("invalid_file", field="file")
            pages = len(reader.pages)
        except AppError:
            raise
        except Exception:
            raise AppError("invalid_file", field="file")

        if pages > LIMITS.pages:
            raise AppError("invalid_file", field="file")
    else:
        pages = 1

    file_sha256 = hashlib.sha256(data).hexdigest()
    return FileCheck(
        file_sha256=file_sha256,
        media_type=media_type,
        page_count=pages,
    )


async def take_quota(
    client_ip: str,
    file_sha256: str,
    is_sample: bool,
    today: date,
    session: AsyncSession | None = None,
) -> None:
    """IP 하루 한도 세기.

    항목 ID: JSD-MS-011#gate.take_quota
    근거: JSD-SEQ-001#SEQ-1, JSD-UC-001#UC-A1 2b, JSD-INFRA-001 5장, JSD-DOM-002 6장
    """
    # 1. 예시 선택인 경우 무과금
    if is_sample:
        return

    # 자체 짧은 트랜잭션으로 처리
    async def _execute(sess: AsyncSession) -> None:
        # 2. 예시 파일 캐시가 이미 있으면 무과금 (사용자가 예시 파일을 직접 업로드한 경우)
        if await crud.is_sample_file_cached(sess, file_sha256):
            return

        # 3. IP 해시 생성
        h = _hmac_hex(client_ip)

        # 4-5. 원자적 쿼리 수행
        ok = await crud.try_take_quota(sess, h, today)
        if not ok:
            raise AppError("rate_limited")

    if session is not None:
        await _execute(session)
        await session.commit()
    else:
        async with async_session_factory() as sess:
            async with sess.begin():
                await _execute(sess)


async def cached_html(
    file_sha256: str,
    session: AsyncSession | None = None,
) -> ParsedDocument | None:
    """파싱 캐시 찾기.

    항목 ID: JSD-MS-011#gate.cached_html
    근거: JSD-SEQ-001#SEQ-1, JSD-UC-001#UC-A1 2c, JSD-UC-001#UC-S10 3·3a
    """
    now = datetime.now(timezone.utc)

    async def _execute(sess: AsyncSession) -> ParsedDocument | None:
        cached = await crud.get_cached_file(sess, file_sha256, now)
        if cached is not None:
            return ParsedDocument(
                html=cached.html,
                page_count=cached.page_count,
                billed_pages=0,
            )
        return None

    if session is not None:
        return await _execute(session)
    else:
        async with async_session_factory() as sess:
            return await _execute(sess)


async def remember_html(
    file_sha256: str,
    html: str,
    page_count: int,
    is_sample: bool,
    session: AsyncSession | None = None,
) -> None:
    """파싱 캐시 넣기.

    항목 ID: JSD-MS-011#gate.remember_html
    근거: JSD-SEQ-001#SEQ-1, JSD-SEQ-001#SEQ-18, JSD-MS-001#ReviewService.create
    """
    now = datetime.now(timezone.utc)

    if session is not None:
        await crud.upsert_file_cache(
            session=session,
            file_sha256=file_sha256,
            html=html,
            page_count=page_count,
            is_sample=is_sample,
            now=now,
        )
    else:
        async with async_session_factory() as sess:
            async with sess.begin():
                await crud.upsert_file_cache(
                    session=sess,
                    file_sha256=file_sha256,
                    html=html,
                    page_count=page_count,
                    is_sample=is_sample,
                    now=now,
                )


async def forget(
    file_sha256: str,
    session: AsyncSession | None = None,
) -> None:
    """검토 삭제 때 캐시 지우기 (JSD-MS-011#gate.forget)."""
    if session is not None:
        await crud.delete_file_cache(session, file_sha256)
    else:
        async with async_session_factory() as sess:
            async with sess.begin():
                await crud.delete_file_cache(sess, file_sha256)


async def purge(
    now: datetime,
    session: AsyncSession | None = None,
) -> int:
    """만료 캐시·지난 한도 행 지우기 (JSD-MS-011#gate.purge)."""
    if session is not None:
        return await crud.purge_expired_gate_records(session, now)
    else:
        async with async_session_factory() as sess:
            async with sess.begin():
                return await crud.purge_expired_gate_records(sess, now)

