"""Jobs 배치 스크립트 테스트.

근거: JSD-MS-015, JSD-DOM-002 4.15
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.jobs import load_region_codes, main, purge, refresh_defaulters, usage_report, warm_samples


def test_jobs_main_invalid_args():
    """모르는 명령 실행 시 반환값 2."""
    assert main([]) == 2
    assert main(["unknown_cmd"]) == 2


@pytest.mark.asyncio
async def test_jobs_main_purge_success():
    """purge 정상 실행 시 0 반환."""
    with patch("app.jobs.purge", new=AsyncMock(return_value=5)):
        code = main(["purge"])
        assert code == 0


@pytest.mark.asyncio
async def test_jobs_main_failure_returns_1():
    """예외 발생 시 1 반환."""
    with patch("app.jobs.purge", side_effect=RuntimeError("DB 에러")):
        code = main(["purge"])
        assert code == 1


@pytest.mark.asyncio
async def test_jobs_load_region_codes_invalid_header(tmp_path):
    """잘못된 헤더의 법정동코드 파일 적재 시 예외."""
    tsv_file = tmp_path / "test_regions.txt"
    tsv_file.write_text("잘못된헤더1\t잘못된헤더2\n1111000000\t서울", encoding="cp949")

    with pytest.raises(Exception):
        await load_region_codes(str(tsv_file))
