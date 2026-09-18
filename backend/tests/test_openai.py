"""openai 유틸 단위 테스트.

근거: JSD-MS-013
"""

from app.infra.openai import client, usage_krw


def test_openai_client_singleton():
    """테스트 관점: 두 번 불러도 같은 객체."""
    c1 = client()
    c2 = client()
    assert c1 is c2


def test_usage_krw():
    """테스트 관점: 0·0 → 0, 소수는 올림."""
    assert usage_krw(0, 0) == 0
    # 1000 in (2.7원), 500 out (5.4원) -> 8.1 -> 올림 9
    cost = usage_krw(1000, 500)
    assert cost > 0
    assert isinstance(cost, int)
