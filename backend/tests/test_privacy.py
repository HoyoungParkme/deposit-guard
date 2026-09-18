"""privacy 유틸 단위 테스트.

근거: JSD-MS-014
"""

from app.shared.privacy import mask_text, person_labels, short_region


def test_person_labels_basic():
    """테스트 관점: ["이서연", "김민수", "이서연"] → A·B, 공백 무시 일치."""
    names = ["이서연", "김민수", "이서연"]
    labels = person_labels(names)
    assert labels["이서연"] == "개인 A"
    assert labels["김민수"] == "개인 B"


def test_person_labels_with_spaces():
    """테스트 관점: "이 서연"과 "이서연"은 같은 라벨."""
    names = ["이서연", "이 서연"]
    labels = person_labels(names)
    assert labels["이서연"] == "개인 A"
    assert labels["이 서연"] == "개인 A"


def test_person_labels_27th():
    """테스트 관점: 27번째 → 개인 AA."""
    names = [f"사람{i}" for i in range(27)]
    labels = person_labels(names)
    assert labels["사람25"] == "개인 Z"
    assert labels["사람26"] == "개인 AA"


def test_mask_text_with_names():
    """테스트 관점: '소유자 이서연 910814-*******' + 이름 → '소유자 개인 A'."""
    text = "소유자 이서연 910814-*******"
    masked = mask_text(text, ["이서연"])
    assert masked == "소유자 개인 A"


def test_mask_text_address():
    """테스트 관점: '화곡동 123-4 해피빌 301호' → '화곡동 해피빌'."""
    text = "화곡동 123-4 해피빌 301호"
    masked = mask_text(text, [])
    assert masked == "화곡동 해피빌"


def test_mask_text_date_preserved():
    """테스트 관점: '2026-07-18 접수'는 그대로."""
    text = "2026-07-18 접수"
    masked = mask_text(text, [])
    assert masked == "2026-07-18 접수"


def test_mask_text_empty_names():
    """테스트 관점: 이름 목록이 비면 이름은 두고 숫자만."""
    text = "홍길동 950101-1234567 12-3번지"
    masked = mask_text(text, [])
    assert "홍길동" in masked
    assert "950101" not in masked
    assert "12-3" not in masked


def test_mask_text_money_preserved():
    """테스트 관점: '5억 5천'은 그대로."""
    text = "보증금 5억 5천 101동 202호"
    masked = mask_text(text, [])
    assert "5억 5천" in masked
    assert "101동" not in masked
    assert "202호" not in masked


def test_short_region():
    """테스트 관점: 서울/경기 등 축약 및 동 단위까지."""
    assert short_region("서울특별시 노원구 상계동 715") == "서울 노원구 상계동"
    assert short_region("경기도 부천시 원미구 심곡동 55-1") == "경기 부천시 원미구 심곡동"
    assert short_region("서울특별시 강남구") == "서울 강남구"
    assert short_region(None) is None
