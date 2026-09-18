"""OpenAI 클라이언트 및 사용량 계산.

근거: JSD-DOM-002 4.13, JSD-MS-013, JSD-INFRA-001#C3, #C7
규칙: 싱글톤 클라이언트(max_retries=0), 토큰 단가 기반 원화 환산(올림).
"""

import math
from openai import AsyncOpenAI

from app.core.config import PRICES, settings

_client_instance: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    """OpenAI 비동기 클라이언트 싱글톤 반환.

    항목 ID: JSD-MS-013#openai.client
    근거: JSD-INFRA-001#C7
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY or "dummy-key-for-test",
            max_retries=0,
        )
    return _client_instance


def usage_krw(tokens_in: int, tokens_out: int) -> int:
    """입출력 토큰 수를 원화 금액(올림)으로 환산.

    항목 ID: JSD-MS-013#openai.usage_krw
    근거: JSD-INFRA-001#C3, JSD-INFRA-001 8장 비용 추정
    """
    if tokens_in == 0 and tokens_out == 0:
        return 0

    cost_in = (tokens_in * PRICES.openai_in_krw_per_1m) / 1_000_000
    cost_out = (tokens_out * PRICES.openai_out_krw_per_1m) / 1_000_000
    return math.ceil(cost_in + cost_out)
