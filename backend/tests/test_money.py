"""money 유틸 단위 테스트.

근거: JSD-MS-014
"""

from app.shared.money import format_manwon


def test_format_manwon():
    """테스트 관점: format_manwon 변환 테스트."""
    assert format_manwon(21000) == "2.1억"
    assert format_manwon(20000) == "2억"
    assert format_manwon(8000) == "8,000만원"
    assert format_manwon(15555) == "1.6억"
    assert format_manwon(None) == "-"
    assert format_manwon(0) == "0만원"
