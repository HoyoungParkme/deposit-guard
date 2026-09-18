"""구조화 JSON 로깅 및 개인정보 마스킹 필터.

근거: JSD-DOM-002 1장, 4.14, JSD-INFRA-001 5장
규칙: 주민번호 형태 숫자를 지우는 필터 적용, httpx·httpcore 로거는 WARNING 설정.
"""

import json
import logging
import re
import sys

RRN_PATTERN = re.compile(r"\d{6}\s*-\s*[\d*]{7}")


class PrivacyFilter(logging.Filter):
    """주민등록번호 형태 숫자를 지우는 로깅 필터."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = RRN_PATTERN.sub("[MASKED_RRN]", record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (RRN_PATTERN.sub("[MASKED_RRN]", v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    RRN_PATTERN.sub("[MASKED_RRN]", arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


class JSONFormatter(logging.Formatter):
    """구조화 JSON 포맷터."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            # 보안 규칙: 예외 문자열이나 파라미터를 노출하지 않고 예외 클래스명만 기록
            exc_type = record.exc_info[0]
            log_obj["exception"] = exc_type.__name__ if exc_type else "Exception"
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """애플리케이션 전역 로깅 설정."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(PrivacyFilter())
    root_logger.addHandler(handler)

    # httpx 및 httpcore 로거는 URL/키 보호를 위해 WARNING으로 설정 (JSD-DOM-002 4.14)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
