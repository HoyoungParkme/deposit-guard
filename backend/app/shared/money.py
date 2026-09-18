"""금액 표기 포맷 유틸.

근거: JSD-DOM-002 4.14, JSD-MS-014
규칙: 순수 함수. 아무것도 import하지 않는다.
"""


def format_manwon(amount: int | None) -> str:
    """만원 정수를 사람이 읽기 쉬운 문자열(억·만원)로 포맷.

    항목 ID: JSD-MS-014#money.format_manwon
    근거: JSD-UI-001 금액 표기, JSD-MS-002#service_agent.tool_summary
    """
    if amount is None:
        return "-"

    if amount >= 10000:
        val = round(amount / 10000, 1)
        if val.is_integer():
            return f"{int(val)}억"
        return f"{val}억"
    else:
        return f"{amount:,}만원"
