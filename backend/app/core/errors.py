"""에러 정의 및 에러 봉투 핸들러.

근거: JSD-API-001 2장, JSD-DOM-002 1장, 4.14
규칙: detail은 코드별 문구이며 예외 문자열(str(exc))을 싣지 않는다.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

# 코드 → 기본 사용자 메시지 매핑
ERROR_MESSAGES: dict[str, str] = {
    "missing_input": "필수 입력 항목이 누락되었습니다.",
    "invalid_file": "형식·크기·쪽수를 초과했거나 읽을 수 없는 파일입니다.",
    "not_registry": "부동산 등기부등본이 아닌 문서입니다.",
    "parse_failed": "문서 분석 처리에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    "rate_limited": "오늘 이용 한도(1일 5회)를 초과했습니다.",
    "not_found": "요청하신 리소스를 찾을 수 없습니다.",
    "gone": "보관 기간(24시간)이 지나 삭제된 검토입니다.",
    "wrong_state": "현재 진행 상태에서는 처리할 수 없는 요청입니다.",
    "question_limit": "질문 가능 횟수를 초과했습니다.",
    "ask_limit": "되묻기 가능 한도를 초과했습니다.",
    "out_of_scope": "요청 범위를 벗어난 작업입니다.",
    "internal": "서버 내부 오류가 발생했습니다.",
}

# 코드 → HTTP 상태 코드 매핑 (JSD-API-001 2장)
STATUS_CODE_MAP: dict[str, int] = {
    "missing_input": 400,
    "invalid_file": 400,
    "not_registry": 400,
    "parse_failed": 502,
    "rate_limited": 429,
    "not_found": 404,
    "gone": 410,
    "wrong_state": 409,
    "question_limit": 409,
    "ask_limit": 429,
    "out_of_scope": 200,
    "internal": 500,
}


class AppError(Exception):
    """애플리케이션 공통 예외.

    예외 문자열이 아니라 정해진 코드와 사전 정의된 설명 문구만 사용한다.
    """

    def __init__(
        self,
        code: str,
        detail: str | None = None,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.detail = detail or ERROR_MESSAGES.get(code, "오류가 발생했습니다.")
        self.field = field
        super().__init__(self.code)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """AppError 예외 핸들러: 에러 봉투 반환."""
    status_code = STATUS_CODE_MAP.get(exc.code, 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "code": exc.code,
            "detail": exc.detail,
            "field": exc.field,
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """예상 밖 예외 핸들러: 예외 문자열 노출 없이 500 에러 봉투 반환."""
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal",
            "detail": ERROR_MESSAGES["internal"],
            "field": None,
        },
    )
