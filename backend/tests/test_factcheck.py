"""factcheck 유틸 단위 테스트.

근거: JSD-MS-014
"""

from app.shared.factcheck import amounts, contradicts


def test_amounts_extraction():
    """테스트 관점: 금액 단위 정규식 추출."""
    assert amounts("2.1억") == {21000}
    assert amounts("5억 5천") == {55000}
    assert amounts("2억 1000만") == {21000}
    assert amounts("8천만") == {8000}
    assert amounts("8000만원") == {8000}
    assert amounts("금210000000원") == {21000}
    assert amounts("보증금 1억 8천이에요") == {18000}
    assert amounts("3호실") == set()
    assert amounts("2026년") == set()


def test_contradicts_amounts():
    """테스트 관점: 금액 허용 오차 판정."""
    # 허용 {21000}에 2.1억 (21000) -> 모순 없음 (False)
    assert not contradicts("보증금은 2.1억입니다.", {21000}, set(), None)
    # 3억 (30000) -> 모순 (True)
    assert contradicts("보증금은 3억입니다.", {21000}, set(), None)


def test_contradicts_ratios():
    """테스트 관점: 비율 오차 판정."""
    # 허용 비율 {0.78}에 78% -> False, 92% -> True
    assert not contradicts("부채비율은 78%입니다.", set(), {0.78}, None)
    assert contradicts("부채비율은 92%입니다.", set(), {0.78}, None)


def test_contradicts_grade():
    """테스트 관점: 등급어 일치 판정."""
    # 등급 caution에 '위험합니다' -> True
    assert contradicts("이 물건은 위험합니다.", set(), set(), "caution")
    # 등급 미정(None)에 '안전합니다' -> True
    assert contradicts("이 집은 안전합니다.", set(), set(), None)
    # 등급 safe에 '안전합니다' -> False
    assert not contradicts("이 집은 안전합니다.", set(), set(), "safe")
    # 신호 이름 속 '위험 신호'는 등급어가 아니므로 모순 아님
    assert not contradicts("2건의 위험 신호가 감지되었습니다.", set(), set(), "caution")


def test_contradicts_no_numbers():
    """테스트 관점: 숫자 없는 일반 문장은 False."""
    assert not contradicts("등기부등본 확인을 시작합니다.", set(), set(), None)
