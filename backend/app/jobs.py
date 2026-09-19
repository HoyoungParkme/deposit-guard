"""배치 명령 진입점.

항목 ID: JSD-MS-015
근거: JSD-DOM-002 4.15, JSD-INFRA-001 8장
사용법: python -m app.jobs <명령>
명령: purge, refresh_defaulters, load_region_codes, warm_samples, usage_report
"""

from __future__ import annotations

import asyncio
import csv
from datetime import date, datetime, timedelta, timezone
import json
import logging
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import LIMITS
from app.core.errors import AppError
from app.core.logging import setup_logging
from app.domains.gate.service import purge as gate_purge
from app.domains.lookup.adapters.hug import HugDefaulterSource
from app.domains.lookup.service import LookupService
from app.domains.review.service import ReviewService
from app.domains.sample.service import SampleService
from app.domains.share.service import ShareService
from app.domains.lookup.schemas import RegionCodeRow

logger = logging.getLogger(__name__)


async def purge(now: datetime | None = None) -> int:
    """만료된 것 지우기 (JSD-MS-015#jobs.purge)."""
    current_time = now or datetime.now(timezone.utc)
    rev_svc = ReviewService()
    share_svc = ShareService()
    lookup_svc = LookupService()

    errors: list[Exception] = []
    total = 0

    for name, coro_fn in [
        ("review", lambda: rev_svc.purge_expired(current_time)),
        ("share", lambda: share_svc.purge_expired(current_time)),
        ("lookup", lambda: lookup_svc.purge_cache(current_time)),
        ("gate", lambda: gate_purge(current_time)),
    ]:
        try:
            total += await coro_fn()
        except Exception as e:
            logger.exception("purge %s failed: %s", name, e)
            errors.append(e)

    if errors:
        raise errors[0]

    return total


async def refresh_defaulters() -> int:
    """HUG 악성 임대인 명단 스냅샷 교체 (JSD-MS-015#jobs.refresh_defaulters)."""
    lookup_svc = LookupService(defaulter_source=HugDefaulterSource())
    count = await lookup_svc.refresh_defaulters()
    if count == 0:
        raise AppError("defaulter_refresh_empty", "0 records fetched, skipping replacement")
    return count


async def load_region_codes(path: str) -> int:
    """법정동코드 10자리 데이터 적재 (JSD-MS-015#jobs.load_region_codes)."""
    lookup_svc = LookupService()
    rows: list[RegionCodeRow] = []

    with open(path, "r", encoding="cp949") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if not reader.fieldnames or not {"법정동코드", "법정동명", "폐지여부"}.issubset(set(reader.fieldnames)):
            raise AppError("invalid_file", "올바른 법정동코드 파일 형식이 아닙니다.")

        for r in reader:
            code = (r.get("법정동코드") or "").strip()
            name = (r.get("법정동명") or "").strip()
            status_str = (r.get("폐지여부") or "").strip()
            if len(code) == 10 and code.isdigit():
                rows.append(
                    RegionCodeRow(
                        code=code,
                        name=name,
                        is_active=(status_str == "존재"),
                    )
                )

    return await lookup_svc.load_region_codes(rows)


async def warm_samples() -> int:
    """예시 파싱 캐시 채우기 (JSD-MS-015#jobs.warm_samples)."""
    rev_svc = ReviewService()
    samples = SampleService.list()
    count = await rev_svc.warm_samples()
    if count < len(samples):
        raise RuntimeError(f"Warmed only {count} of {len(samples)} samples")
    return count


async def usage_report(day: date | None = None) -> int:
    """어제 비용 점검 (JSD-MS-015#jobs.usage_report)."""
    seoul_tz = ZoneInfo("Asia/Seoul")
    now_seoul = datetime.now(seoul_tz)
    target_day = day or (now_seoul - timedelta(days=1)).date()

    rev_svc = ReviewService()
    summary = await rev_svc.usage_report(target_day)

    log_payload: dict[str, Any] = {
        "job": "usage_report",
        "day": str(target_day),
        "reviews": summary.reviews,
        "failed": summary.failed,
        "avg_cost_krw": summary.avg_cost_krw,
    }
    logger.info(json.dumps(log_payload))

    if summary.avg_cost_krw > LIMITS.cost_krw:
        logger.warning(
            json.dumps({
                "job": "usage_report",
                "warning": "cost_over_limit",
                "avg_cost_krw": summary.avg_cost_krw,
                "limit": LIMITS.cost_krw,
            })
        )

    return summary.reviews


def main(argv: list[str] | None = None) -> int:
    """배치 명령 진입점 (JSD-MS-015#jobs.main)."""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("사용법: python -m app.jobs <purge|refresh_defaulters|load_region_codes <path>|warm_samples|usage_report>", file=sys.stderr)
        return 2

    command = args[0]
    valid_commands = {"purge", "refresh_defaulters", "load_region_codes", "warm_samples", "usage_report"}
    if command not in valid_commands:
        print(f"알 수 없는 명령: {command}", file=sys.stderr)
        return 2

    setup_logging()
    started = time.time()

    def _run_async(coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)

    try:
        if command == "purge":
            count = _run_async(purge())
        elif command == "refresh_defaulters":
            count = _run_async(refresh_defaulters())
        elif command == "load_region_codes":
            if len(args) < 2:
                print("사용법: python -m app.jobs load_region_codes <file_path>", file=sys.stderr)
                return 2
            count = _run_async(load_region_codes(args[1]))
        elif command == "warm_samples":
            count = _run_async(warm_samples())
        elif command == "usage_report":
            count = _run_async(usage_report())
        else:
            return 2

        elapsed_ms = int((time.time() - started) * 1000)
        logger.info(json.dumps({"job": command, "ok": True, "count": count, "elapsed_ms": elapsed_ms}))
        return 0

    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        logger.error(json.dumps({"job": command, "ok": False, "error": type(exc).__name__, "elapsed_ms": elapsed_ms}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
