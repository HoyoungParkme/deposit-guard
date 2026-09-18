"""등기부 표 읽기 순수 함수.

근거: JSD-DOM-002 4.4, JSD-MS-004, JSD-UC-001, JSD-API-002
규칙: DB·네트워크·모델을 부르지 않는 순수 함수. 같은 HTML이면 같은 결과.
"""

from datetime import date
import html as html_lib
from html.parser import HTMLParser
import re

from app.core.errors import AppError
from app.domains.registry.schemas import (
    Block,
    ParsedEntry,
    ParsedRegistry,
    Property,
)
from app.shared import privacy
from app.shared.types import (
    BuildingType,
    DocKind,
    PurposeCode,
    Section,
)


def norm(s: str | None) -> str:
    """모든 공백을 뺀 문자열을 반환한다."""
    if not s:
        return ""
    return re.sub(r"\s+", "", s)


def won_to_manwon(text: str) -> int | None:
    """금액 문자열을 만원 정수로 변환한다.

    항목 ID: JSD-MS-004#service_parse.won_to_manwon
    """
    if not text:
        return None
    # 금, ,, 원, 공백 제거
    cleaned = re.sub(r"[금,원\s]", "", text)
    if cleaned.isdigit():
        return int(cleaned) // 10000
    return None


def purpose_code(text: str) -> PurposeCode:
    """등기목적 문구를 코드로 변환한다.

    항목 ID: JSD-MS-004#service_parse.purpose_code
    근거: JSD-DOM-002 2.9 PurposeCode
    """
    s = norm(text)
    # 순서가 규칙이다 — 긴 말이 먼저
    rules: list[tuple[str, PurposeCode]] = [
        ("말소", PurposeCode.cancellation),
        ("가압류", PurposeCode.provisional_seizure),
        ("압류", PurposeCode.seizure),
        ("가처분", PurposeCode.injunction),
        ("가등기", PurposeCode.provisional_registration),
        ("경매개시결정", PurposeCode.auction),
        ("신탁", PurposeCode.trust),
        ("예고등기", PurposeCode.notice_registration),
        ("근저당권변경", PurposeCode.mortgage_change),
        ("근저당권설정", PurposeCode.mortgage),
        ("근저당권이전", PurposeCode.mortgage),
        ("전세권", PurposeCode.jeonse_right),
        ("임차권", PurposeCode.lease_right),
        ("소유권보존", PurposeCode.ownership_preserve),
        ("소유권이전", PurposeCode.ownership_transfer),
    ]

    for pat, code in rules:
        if pat in s:
            return code
    return PurposeCode.other


def read_holder(
    section: Section, purpose: PurposeCode, text: str
) -> tuple[str | None, bool | None]:
    """권리자 칸에서 이름과 법인 여부를 읽는다.

    항목 ID: JSD-MS-004#service_parse.read_holder
    근거: JSD-API-002 1.3, JSD-DOM-002 4.4
    """
    if not text:
        return None, None

    # 1. 역할 낱말
    target_words: list[str]
    if purpose in (PurposeCode.ownership_preserve, PurposeCode.ownership_transfer):
        target_words = ["소유자", "공유자"]
    elif purpose in (PurposeCode.mortgage, PurposeCode.mortgage_change):
        target_words = ["근저당권자"]
    elif purpose == PurposeCode.jeonse_right:
        target_words = ["전세권자"]
    elif purpose == PurposeCode.lease_right:
        target_words = ["임차권자"]
    elif purpose in (
        PurposeCode.seizure,
        PurposeCode.provisional_seizure,
        PurposeCode.injunction,
        PurposeCode.auction,
    ):
        target_words = ["채권자", "권리자"]
    elif purpose == PurposeCode.trust:
        target_words = ["수탁자"]
    elif purpose == PurposeCode.provisional_registration:
        target_words = ["가등기권자"]
    else:
        target_words = [
            "소유자", "공유자", "근저당권자", "전세권자", "임차권자",
            "채권자", "권리자", "수탁자", "가등기권자",
        ]

    # 역할 낱말 마지막 등장 위치 찾기
    found_pos = -1
    found_word = ""
    for w in target_words:
        pos = text.rfind(w)
        if pos > found_pos:
            found_pos = pos
            found_word = w

    if found_pos == -1:
        return None, None

    # 역할 낱말 뒤의 텍스트
    after_role = text[found_pos + len(found_word):].strip()
    if not after_role:
        return None, None

    words = after_role.split()
    if not words:
        return None, None

    # 4. 공유자 처리
    if found_word == "공유자":
        names: list[str] = []
        skip_next = False
        for w in words:
            if skip_next:
                skip_next = False
                continue
            if w.startswith("지분"):
                continue
            # 등록번호 형태가 아니면 이름으로 수집
            if not re.match(r"^\d{6}-", w):
                names.append(w)
        if names:
            name = ", ".join(names)
            # 첫 번째 이름 기준 법인 여부 확인
            is_corp = False
            for w in words:
                if re.match(r"^\d{6}-\d\*{4}$", w):
                    is_corp = True
                    break
            return name, is_corp
        return None, None

    name = words[0]
    next_words = words[1:]

    # 5. 법인 여부 판단
    is_corp: bool | None = None
    corp_indicators = [
        "주식회사", "(주)", "은행", "금고", "공사", "조합", "신탁",
        "캐피탈", "저축은행", "보험",
    ]

    for w in next_words:
        # 법인 등록번호: 110111-5****
        if re.match(r"^\d{6}-\d\*{4}$", w):
            is_corp = True
            break
        # 개인 주민등록번호: 910814-******* 또는 910814-1******
        if re.match(r"^\d{6}-\*{7}$", w) or re.match(r"^\d{6}-\d\*{6}$", w):
            is_corp = False
            break

    if is_corp is None:
        is_corp = any(ind in name for ind in corp_indicators)

    return name, is_corp


class _BlockHTMLParser(HTMLParser):
    """업스테이지 HTML 요소를 Block 목록으로 분리하는 파서."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[Block] = []
        self._current_tag: str | None = None
        self._current_id: str | None = None
        self._current_text: list[str] = []

        # 테이블 파싱용
        self._in_table = False
        self._in_thead = False
        self._in_tbody = False
        self._table_header: list[str] = []
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        element_id = attr_dict.get("id")

        if element_id is not None:
            # 새로운 블록 시작
            self._flush_block()
            self._current_tag = tag
            self._current_id = element_id
            self._current_text = []

            if tag == "table":
                self._in_table = True
                self._table_header = []
                self._table_rows = []

        if self._in_table:
            if tag == "thead":
                self._in_thead = True
            elif tag == "tbody":
                self._in_tbody = True
            elif tag == "tr":
                self._current_row = []
            elif tag in ("th", "td"):
                self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if self._in_table:
            if tag in ("th", "td"):
                cell_text = " ".join("".join(self._current_cell).split())
                self._current_row.append(html_lib.unescape(cell_text))
            elif tag == "tr":
                if self._in_thead:
                    if not self._table_header and self._current_row:
                        self._table_header = self._current_row
                elif self._in_tbody:
                    if self._current_row:
                        self._table_rows.append(self._current_row)
                else:
                    # thead 없는 표의 경우 첫 번째 행을 헤더로
                    if not self._table_header and not self._table_rows:
                        self._table_header = self._current_row
                    elif self._current_row:
                        self._table_rows.append(self._current_row)
            elif tag == "thead":
                self._in_thead = False
            elif tag == "tbody":
                self._in_tbody = False
            elif tag == "table":
                self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._current_id is not None:
            self._current_text.append(data)
            if self._in_table:
                self._current_cell.append(data)

    def _flush_block(self) -> None:
        if self._current_id is not None and self._current_tag is not None:
            full_text = " ".join("".join(self._current_text).split())
            clean_text = html_lib.unescape(full_text)
            block = Block(
                tag=self._current_tag,
                block_id=self._current_id,
                text=clean_text,
                header=self._table_header if self._current_tag == "table" else [],
                rows=self._table_rows if self._current_tag == "table" else [],
            )
            self.blocks.append(block)
            self._current_tag = None
            self._current_id = None
            self._current_text = []

    def close(self) -> None:
        super().close()
        self._flush_block()


def split_blocks(html: str) -> list[Block]:
    """HTML을 요소 목록(Block)으로 분리한다.

    항목 ID: JSD-MS-004#service_parse.split_blocks
    근거: JSD-DOM-002 4.4
    """
    parser = _BlockHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.blocks


def clean_html(blocks: list[Block]) -> str:
    """문서 패널에 내려갈 정제된 HTML을 생성한다.

    항목 ID: JSD-MS-004#service_parse.clean_html
    근거: JSD-UI-001#UI-2 요소 7, JSD-DOM-002 4.4
    """
    parts: list[str] = []
    for b in blocks:
        if b.tag == "table":
            table_lines: list[str] = [f'<table data-block-id="{b.block_id}">']
            if b.header:
                table_lines.append("<thead><tr>")
                for h in b.header:
                    table_lines.append(f"<th>{html_lib.escape(h)}</th>")
                table_lines.append("</tr></thead>")
            table_lines.append("<tbody>")
            for idx, r in enumerate(b.rows, start=1):
                row_block_id = f"{b.block_id}-{idx}"
                table_lines.append(f'<tr data-block-id="{row_block_id}">')
                for c in r:
                    table_lines.append(f"<td>{html_lib.escape(c)}</td>")
                table_lines.append("</tr>")
            table_lines.append("</tbody></table>")
            parts.append("".join(table_lines))
        else:
            tag_name = b.tag if b.tag in ("h1", "h2", "h3") else "p"
            parts.append(
                f'<{tag_name} data-block-id="{b.block_id}">{html_lib.escape(b.text)}</{tag_name}>'
            )
    return "\n".join(parts)


def read_rows(
    table: Block, section: Section, warnings: list[str]
) -> list[ParsedEntry]:
    """갑구·을구 표 하나의 행을 항목으로 변환한다.

    항목 ID: JSD-MS-004#service_parse.read_rows
    근거: JSD-UC-001#UC-S1 3·3a, JSD-DOM-002 2.2
    """
    norm_headers = [norm(h) for h in table.header]

    # 1. 열 위치 찾기
    col_rank = -1
    col_purpose = -1
    col_receipt = -1
    col_cause = -1
    col_holder = -1

    for idx, h in enumerate(norm_headers):
        if "순위번호" in h:
            col_rank = idx
        elif "등기목적" in h:
            col_purpose = idx
        elif "접수" in h:
            col_receipt = idx
        elif "등기원인" in h:
            col_cause = idx
        elif "권리자" in h:
            col_holder = idx

    if col_rank == -1 or col_purpose == -1:
        warnings.append(f"{table.block_id} 머리글을 읽지 못함")
        return []

    entries: list[ParsedEntry] = []
    used_entry_ids: dict[str, int] = {}

    for i, row in enumerate(table.rows, start=1):
        if len(row) != len(table.header):
            warnings.append(f"{table.block_id}-{i} 칸 수가 다름")

        def _get_cell(col_idx: int) -> str:
            return row[col_idx] if 0 <= col_idx < len(row) else ""

        rank_no = norm(_get_cell(col_rank))
        if not rank_no:
            warnings.append(f"{table.block_id}-{i} 순위번호 없음")
            continue

        base_entry_id = f"{section.value}-{rank_no}"
        count = used_entry_ids.get(base_entry_id, 0)
        if count > 0:
            entry_id = f"{base_entry_id}-{count + 1}"
            warnings.append(f"{entry_id} 중복 순위번호")
        else:
            entry_id = base_entry_id
        used_entry_ids[base_entry_id] = count + 1

        # parent_entry_id: N-M 형태 부기등기
        parent_entry_id: str | None = None
        if "-" in rank_no:
            parent_n = rank_no.split("-")[0]
            parent_entry_id = f"{section.value}-{parent_n}"

        purpose_text = " ".join(_get_cell(col_purpose).split())
        code = purpose_code(purpose_text)

        # 접수 칸 분석
        receipt_text = _get_cell(col_receipt)
        received_at: date | None = None
        receipt_no: str | None = None

        m_date = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", receipt_text)
        if m_date:
            received_at = date(
                int(m_date.group(1)),
                int(m_date.group(2)),
                int(m_date.group(3)),
            )
        m_no = re.search(r"제\s*(\d+)\s*호", receipt_text)
        if m_no:
            receipt_no = f"제{m_no.group(1)}호"

        if received_at is None and code != PurposeCode.cancellation:
            warnings.append(f"{entry_id} 접수일을 읽지 못함")

        cause_text = _get_cell(col_cause).strip() or None

        # 권리자 칸 분석
        holder_cell = _get_cell(col_holder)
        amount_manwon: int | None = None
        price_manwon: int | None = None

        m_amount = re.search(r"(?:채권최고액|전세금|임차보증금)\s*금?\s*([\d,]+)\s*원", holder_cell)
        if m_amount:
            amount_manwon = won_to_manwon(m_amount.group(1))
        elif code in (PurposeCode.mortgage, PurposeCode.jeonse_right, PurposeCode.lease_right):
            warnings.append(f"{entry_id} 금액을 읽지 못함")

        m_price = re.search(r"거래가액\s*금?\s*([\d,]+)\s*원", holder_cell)
        if m_price:
            price_manwon = won_to_manwon(m_price.group(1))

        holder, holder_is_corp = read_holder(section, code, holder_cell)
        if code != PurposeCode.cancellation and holder is None:
            warnings.append(f"{entry_id} 권리자를 읽지 못함")

        block_ids = [f"{table.block_id}-{i}"]
        loc_sec = "갑구" if section == Section.gap else "을구"
        location_label = f"{loc_sec} {rank_no}번"

        entry = ParsedEntry(
            entry_id=entry_id,
            rank_no=rank_no,
            purpose_code=code,
            received_at=received_at,
            amount_manwon=amount_manwon,
            price_manwon=price_manwon,
            holder=holder,
            holder_is_corporation=holder_is_corp,
            cancelled=False,
            receipt_no=receipt_no,
            purpose_text=purpose_text,
            block_ids=block_ids,
            location_label=location_label,
            section=section,
            parent_entry_id=parent_entry_id,
            cause=cause_text,
            cancelled_by_entry_id=None,
        )
        entries.append(entry)

    return entries


def apply_cancellations(entries: list[ParsedEntry], warnings: list[str] | None = None) -> None:
    """말소 행으로 대상 항목에 말소 표시를 한다.

    항목 ID: JSD-MS-004#service_parse.apply_cancellations
    근거: JSD-UC-001#UC-S1 4, JSD-DOM-001#RegistryEntry
    """
    for c in entries:
        if c.purpose_code == PurposeCode.cancellation:
            # c.purpose_text에서 대상 번호 추출
            m = re.search(r"^(\d+(?:-\d+)?)번", norm(c.purpose_text))
            if not m:
                continue
            target_n = m.group(1)
            sec_prefix = c.entry_id.split("-")[0]

            target = next(
                (
                    e for e in entries
                    if e.section.value == sec_prefix and e.rank_no == target_n
                ),
                None,
            )
            if target is not None:
                target.cancelled = True
                target.cancelled_by_entry_id = c.entry_id

                # 부기등기 말소 연쇄: 주등기가 말소되면 부기등기도 말소
                for sub in entries:
                    if sub.parent_entry_id == target.entry_id:
                        sub.cancelled = True
                        sub.cancelled_by_entry_id = c.entry_id
            else:
                if warnings is not None:
                    warnings.append(f"{c.entry_id} 말소 대상 {target_n}번을 찾지 못함")


def read_property(blocks: list[Block], kind: DocKind) -> Property | None:
    """첫머리 주소와 표제부에서 주택 정보를 읽는다.

    항목 ID: JSD-MS-004#service_parse.read_property
    근거: JSD-UC-001#UC-S1 5·5a, JSD-DOM-001#Property
    """
    if kind == DocKind.land:
        return None

    # 2. 주소 줄
    lot_address: str | None = None
    building_name: str | None = None

    addr_block = next(
        (b for b in blocks if b.text.startswith("[집합건물]") or b.text.startswith("[건물]")),
        None,
    )
    if addr_block is not None:
        parts = addr_block.text.split()
        # [집합건물] 등 제외
        body_words = parts[1:] if len(parts) > 1 else []

        lot_words: list[str] = []
        name_words: list[str] = []
        found_lot = False

        for w in body_words:
            if not found_lot:
                lot_words.append(w)
                # 지번 모양 낱말: ^\d+(-\d+)?$
                if re.match(r"^\d+(-\d+)?$", w):
                    found_lot = True
            else:
                # 제로 시작하는 낱말(동, 층, 호) 앞까지
                if re.match(r"^제\d+", w):
                    break
                name_words.append(w)

        if lot_words:
            lot_address = " ".join(lot_words)
        if name_words:
            building_name = " ".join(name_words)

    region = privacy.short_region(lot_address) if lot_address else ""

    # 표제부 표들 탐색
    building_type = BuildingType.other
    exclusive_area_m2: float | None = None
    has_land_right_table = False
    separate_land_registry = False

    for b in blocks:
        norm_txt = norm(b.text)
        if "별도등기" in norm_txt:
            separate_land_registry = True

        if b.tag == "table":
            norm_header = [norm(h) for h in b.header]
            # 건물내역이 있는 첫 표에서 building_type 판정
            if building_type == BuildingType.other and "건물내역" in norm_header:
                idx = norm_header.index("건물내역")
                for r in b.rows:
                    if idx < len(r):
                        row_norm = norm(r[idx])
                        if "아파트" in row_norm:
                            building_type = BuildingType.apartment
                            break
                        elif "다세대주택" in row_norm or "연립주택" in row_norm:
                            building_type = BuildingType.multi_family_unit
                            break
                        elif "다가구주택" in row_norm:
                            building_type = BuildingType.multi_household
                            break
                        elif "오피스텔" in row_norm:
                            building_type = BuildingType.officetel
                            break

        # 전유부분 건물내역 표에서 전용면적 추출
        if "전유부분" in norm_txt:
            # 전유부분 표에서 건물내역 칸
            for r_block in blocks:
                if r_block.tag == "table" and any("건물내역" in norm(h) for h in r_block.header):
                    col_idx = [norm(h) for h in r_block.header].index("건물내역")
                    for row in r_block.rows:
                        if col_idx < len(row):
                            # 마지막 ([\d.]+)㎡
                            matches = re.findall(r"([\d.]+)㎡", row[col_idx])
                            if matches:
                                exclusive_area_m2 = float(matches[-1])

        if "대지권의표시" in norm_txt:
            has_land_right_table = True

    is_collective = (kind == DocKind.collective)
    land_right_unregistered = (is_collective and not has_land_right_table)

    return Property(
        region=region,
        building_type=building_type,
        is_collective=is_collective,
        land_right_unregistered=land_right_unregistered,
        separate_land_registry=separate_land_registry,
        lot_address=lot_address,
        exclusive_area_m2=exclusive_area_m2,
        building_name=building_name,
    )


def read_extract(html: str) -> ParsedRegistry:
    """HTML 한 장을 등기부로 읽는다.

    항목 ID: JSD-MS-004#service_parse.read_extract
    근거: JSD-UC-001#UC-S1 2~6, JSD-MS-003#RegistryService.create_extract
    """
    blocks = split_blocks(html)
    warnings: list[str] = []

    # 2. 문서 종류 판정
    kind: DocKind = DocKind.building
    found_kind = False

    for b in blocks:
        if b.tag != "table":
            t = norm(b.text)
            if "-집합건물" in t or "[집합건물]" in t:
                kind = DocKind.collective
                found_kind = True
                break
            elif "-토지" in t or "[토지]" in t:
                kind = DocKind.land
                found_kind = True
                break
            elif "-건물" in t or "[건물]" in t:
                kind = DocKind.building
                found_kind = True
                break

    if not found_kind:
        warnings.append("문서 종류를 읽지 못함")

    # 3. 블록 순회 및 섹션별 표 읽기
    section: Section | None = None
    in_title_section = False
    entries: list[ParsedEntry] = []
    has_gap_or_eul = False

    for b in blocks:
        if b.tag != "table":
            t = norm(b.text)
            if "【표제부】" in t:
                in_title_section = True
                section = None
            elif "【갑구】" in t:
                in_title_section = False
                section = Section.gap
            elif "【을구】" in t:
                in_title_section = False
                section = Section.eul
        else:
            if section in (Section.gap, Section.eul):
                has_gap_or_eul = True
                parsed_rows = read_rows(b, section, warnings)
                entries.extend(parsed_rows)

    # 4. 갑구/을구 표가 하나도 없으면 not_registry 예외
    if not has_gap_or_eul:
        raise AppError("not_registry")

    # 5. 말소 적용
    apply_cancellations(entries, warnings)

    # 6. 주택 정보 읽기
    prop = read_property(blocks, kind)
    if kind != DocKind.land and prop is not None and prop.building_type == BuildingType.other:
        warnings.append("건물 종류를 정하지 못함")

    return ParsedRegistry(
        kind=kind,
        property=prop,
        entries=entries,
        panel_html=clean_html(blocks),
        warnings=warnings,
    )
