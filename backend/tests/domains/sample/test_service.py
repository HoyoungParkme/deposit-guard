"""SampleService 단위 테스트.

항목 ID: JSD-MS-010#SampleService.list, JSD-MS-010#SampleService.file
"""

import hashlib
import pytest

from app.core.errors import AppError
from app.domains.sample.schemas import SampleCaseResponse
from app.domains.sample.service import SampleService


def test_sample_service_list():
    """예시 3건 목록 조회."""
    cases = SampleService.list()
    assert len(cases) == 3

    sample_ids = [c.sample_id for c in cases]
    assert "apartment_safe" in sample_ids
    assert "multi_family_caution" in sample_ids
    assert "multi_household_danger" in sample_ids

    # 응답 스키마 직렬화 시 expected_grade, file_name이 노출되지 않음
    responses = [
        SampleCaseResponse(
            sample_id=c.sample_id,
            title=c.title,
            summary=c.summary,
            region=c.region,
            deposit_manwon=c.deposit_manwon,
            contract_type=c.contract_type,
        ).model_dump()
        for c in cases
    ]
    for r in responses:
        assert "expected_grade" not in r
        assert "file_name" not in r
        assert "deposit_manwon" in r


def test_sample_service_file_valid():
    """유효한 sample_id로 PDF 파일 로드."""
    cases = SampleService.list()
    for case in cases:
        upload = SampleService.file(case.sample_id)
        assert upload.filename == case.file_name
        assert upload.media_type == "application/pdf"
        assert len(upload.data) > 0

        # 같은 예시 두 번 호출 시 동일 해시
        upload2 = SampleService.file(case.sample_id)
        assert hashlib.sha256(upload.data).hexdigest() == hashlib.sha256(upload2.data).hexdigest()


def test_sample_service_file_invalid():
    """존재하지 않거나 유효하지 않은 sample_id -> missing_input."""
    with pytest.raises(AppError) as exc_info:
        SampleService.file("non_existent_id")
    assert exc_info.value.code == "missing_input"

    with pytest.raises(AppError) as exc_info:
        SampleService.file("../../etc/passwd")
    assert exc_info.value.code == "missing_input"
