"""개인정보 가리기 및 라벨링 유틸.

근거: JSD-DOM-002 4.14, JSD-MS-014
규칙: 순수 함수. 아무것도 import하지 않는다 (re, math 제외).
"""

import re


def _label_name(index: int) -> str:
    """0부터 시작하는 인덱스를 A, B, ..., Z, AA, AB 형태의 라벨로 변환."""
    result = []
    n = index
    while True:
        rem = n % 26
        result.append(chr(ord("A") + rem))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(result))


def person_labels(names: list[str]) -> dict[str, str]:
    """개인 이름 목록을 등장 순서대로 개인 A, 개인 B 등의 라벨로 매핑.

    항목 ID: JSD-MS-014#privacy.person_labels
    근거: JSD-API-002 1.3, JSD-MS-003#RegistryService.holder_names
    """
    labels: dict[str, str] = {}
    normalized_to_label: dict[str, str] = {}
    count = 0

    for name in names:
        trimmed = name.strip()
        if not trimmed:
            continue
        norm = re.sub(r"\s+", "", trimmed)
        if norm in normalized_to_label:
            labels[name] = normalized_to_label[norm]
        else:
            lbl = f"개인 {_label_name(count)}"
            normalized_to_label[norm] = lbl
            labels[name] = lbl
            count += 1

    return labels


def mask_text(text: str | None, names: list[str]) -> str | None:
    """문장 속 이름·주민번호·번지·동호수 가리기.

    항목 ID: JSD-MS-014#privacy.mask_text
    근거: JSD-PRD-001#N1, JSD-MS-001#ReviewService.record, JSD-MS-008#ReportService.shareable
    """
    if text is None:
        return None

    masked = text

    # 1. 이름 가리기 (긴 이름부터 매칭)
    if names:
        labels = person_labels(names)
        # 긴 이름부터 정렬하여 부분 일치 방지
        sorted_names = sorted(labels.keys(), key=lambda x: len(x), reverse=True)
        for name in sorted_names:
            label = labels[name]
            # 글자 사이 공백 하나까지 허용 (예: '이서연' -> '이\s*서\s*연')
            chars = [re.escape(c) for c in re.sub(r"\s+", "", name)]
            pattern_str = r"\s*".join(chars)
            masked = re.sub(pattern_str, label, masked)

    # 2. 주민번호 형태: \d{6}\s*-\s*[\d*]{7}
    masked = re.sub(r"\d{6}\s*-\s*[\d*]{7}", "", masked)

    # 3. 번지:
    # 3-1. \d{1,5}(-\d{1,5})?\s*번지
    masked = re.sub(r"\d{1,5}(-\d{1,5})?\s*번지", "", masked)
    # 3-2. 앞뒤가 숫자나 하이픈이 아닌 \d{1,5}-\d{1,5} (날짜 YYYY-MM-DD 등 3토막 제외)
    masked = re.sub(r"(?<![\d\-])\d{1,5}-\d{1,5}(?![\d\-])", "", masked)

    # 4. 동·호수: 제?\s*\d{1,4}\s*동\s*제?\s*\d{1,4}\s*호 | 제?\s*\d{1,4}\s*호 | 제\s*\d{1,3}\s*층
    masked = re.sub(r"제?\s*\d{1,4}\s*동\s*제?\s*\d{1,4}\s*호", "", masked)
    masked = re.sub(r"제?\s*\d{1,4}\s*호", "", masked)
    masked = re.sub(r"제\s*\d{1,3}\s*층", "", masked)

    # 5. 연속 공백 축소 및 앞뒤 공백 제거
    masked = re.sub(r"[ \t]+", " ", masked)
    return masked.strip()


# 시도 약칭 사전
SIDO_MAP: dict[str, str] = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원",
    "강원도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
    "제주도": "제주",
}


def short_region(address: str | None) -> str | None:
    """주소를 시도·시군구·동 형태로 축약.

    항목 ID: JSD-MS-014#privacy.short_region
    근거: JSD-API-002 1.3, JSD-MS-004#service_parse.read_property, JSD-MS-005 3장
    """
    if not address or not address.strip():
        return None

    words = address.strip().split()
    if not words:
        return None

    # 시도 단축
    sido = words[0]
    short_sido = SIDO_MAP.get(sido, sido)
    result_parts = [short_sido]

    dong_suffixes = ("동", "읍", "면", "가")

    # 뒤 낱말 탐색
    for word in words[1:]:
        # 숫자로 시작하는 낱말(번지, 건물번호 등)에서 멈춤
        if re.match(r"^\d", word):
            break

        result_parts.append(word)

        # 끝이 동/읍/면/가인 첫 법정동 낱말에 도달하면 종료
        if word.endswith(dong_suffixes):
            break

    return " ".join(result_parts)
