"""문장 속 금액·비율·등급어 사실 검증 유틸.

근거: JSD-DOM-002 4.14, JSD-MS-014
규칙: 순수 함수. 아무것도 import하지 않는다 (re, math 제외).
"""

import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.types import GradeLevel


def amounts(text: str) -> set[int]:
    """문장 속 금액(억·만원)을 만원 정수 집합으로 추출.

    항목 ID: JSD-MS-014#factcheck.amounts
    근거: JSD-MS-002#service_agent.check_stated, JSD-UC-001#UC-A1 7
    """
    clean_text = text.replace(",", "")
    found: list[tuple[int, int, int]] = []  # (start, end, manwon_val)

    # 1. (\d+(\.\d+)?)\s*억(\s*(\d+)\s*천)?(\s*(\d+)\s*만)?
    pattern1 = re.compile(
        r"(\d+(?:\.\d+)?)\s*억(?:\s*(\d+)\s*천)?(?:\s*(\d+)\s*만)?"
    )
    for m in pattern1.finditer(clean_text):
        eok = float(m.group(1))
        cheon = int(m.group(2)) if m.group(2) else 0
        man = int(m.group(3)) if m.group(3) else 0
        val = int(round(eok * 10000)) + cheon * 1000 + man
        found.append((m.start(), m.end(), val))

    # 2. (\d+)\s*천\s*만
    pattern2 = re.compile(r"(\d+)\s*천\s*만")
    for m in pattern2.finditer(clean_text):
        # 겹침 확인
        if any(s <= m.start() < e or s < m.end() <= e for s, e, _ in found):
            continue
        val = int(m.group(1)) * 1000
        found.append((m.start(), m.end(), val))

    # 3. (\d+)\s*만\s*원?
    pattern3 = re.compile(r"(\d+)\s*만\s*원?")
    for m in pattern3.finditer(clean_text):
        if any(s <= m.start() < e or s < m.end() <= e for s, e, _ in found):
            continue
        val = int(m.group(1))
        found.append((m.start(), m.end(), val))

    # 4. 금?\s*(\d{5,})\s*원
    pattern4 = re.compile(r"금?\s*(\d{5,})\s*원")
    for m in pattern4.finditer(clean_text):
        if any(s <= m.start() < e or s < m.end() <= e for s, e, _ in found):
            continue
        won = int(m.group(1))
        val = won // 10000
        found.append((m.start(), m.end(), val))

    return {val for _, _, val in found}


# 등급어 패턴 목록: (pattern, GradeLevel string)
# "위험 신호" 등은 등급어가 아니므로 부정형 룩어헤드/룩비하인드로 제외
GRADE_PATTERNS = [
    (re.compile(r"(?<!신호\s)위험합니다"), "danger"),
    (re.compile(r"위험\s*등급"), "danger"),
    (re.compile(r"위험으로\s*판정"), "danger"),
    (re.compile(r"주의가\s*필요합니다"), "caution"),
    (re.compile(r"주의\s*등급"), "caution"),
    (re.compile(r"안전합니다"), "safe"),
    (re.compile(r"안전\s*등급"), "safe"),
]


def contradicts(
    text: str,
    allowed_manwon: set[int],
    allowed_ratios: set[float],
    grade: str | None,
) -> bool:
    """문장 속 금액·비율·등급어가 허용 값과 다른지 검증.

    항목 ID: JSD-MS-014#factcheck.contradicts
    근거: JSD-PRD-001#R10, JSD-MS-002#service_agent.say, JSD-MS-008#ReportService.write
    """
    # 1. 금액 검증: |a - b| <= max(b * 0.05, 100)
    found_amounts = amounts(text)
    for a in found_amounts:
        matched = False
        for b in allowed_manwon:
            allowed_diff = max(b * 0.05, 100)
            if abs(a - b) <= allowed_diff:
                matched = True
                break
        if not matched:
            return True

    # 2. 비율 검증: (\d+(\.\d+)?)\s*% 마다 r/100과 allowed_ratios 차이 0.01 이하
    ratio_matches = re.finditer(r"(\d+(?:\.\d+)?)\s*%", text)
    for rm in ratio_matches:
        r = float(rm.group(1)) / 100.0
        matched = False
        for ar in allowed_ratios:
            if abs(r - ar) <= 0.01001:  # 부동소수점 오차 감안
                matched = True
                break
        if not matched:
            return True

    # 3. 등급어 검증
    for pat, target_grade in GRADE_PATTERNS:
        if pat.search(text):
            if grade is None or str(grade) != target_grade:
                return True

    return False
