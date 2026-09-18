"""logging 설정 및 개인정보 필터 테스트.

근거: JSD-DOM-002 4.14
"""

import logging
from app.core.logging import JSONFormatter, PrivacyFilter


def test_privacy_filter_masks_rrn():
    """테스트 관점: 로그 필터가 주민번호 형태를 지운다."""
    filter_ = PrivacyFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="사용자 식별번호: 950101-1234567 및 000101-******* 처리",
        args=(),
        exc_info=None,
    )
    filter_.filter(record)
    assert "950101" not in record.msg
    assert "000101" not in record.msg
    assert "[MASKED_RRN]" in record.msg


def test_json_formatter_structure():
    """테스트 관점: 로그 출력이 유효한 JSON 포맷이다."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="테스트 메시지",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    assert '"level": "INFO"' in output
    assert '"message": "테스트 메시지"' in output
