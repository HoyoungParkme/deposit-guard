---
doc_id: JSD-MS-004
type: MS
title: 보증금지킴 — 미니스펙 등기부 표 읽기
status: draft
upstream: [JSD-DOM-002, JSD-UC-001, JSD-API-002, JSD-MS-003]
---

# MINISPEC — 등기부 표 읽기

## 0. 이 문서가 다루는 것

`registry/service_parse.py`의 함수 9개. 클래스 명세 [[JSD-DOM-002]] 4.4의 함수 열을 함수 안쪽까지 내린 것이다. 업스테이지 Document Parse가 돌려준 HTML에서 표제부·갑구·을구를 항목으로 읽는다. 부르는 곳은 [[JSD-MS-003#RegistryService.create_extract]] 하나다.

**순수 함수다.** DB·네트워크·모델을 부르지 않고, 같은 HTML이면 같은 결과다. 그래서 예시 3건(토지 등기부 포함 4장)의 업스테이지 출력 고정본과 3장 정답표로 테스트한다([[JSD-PRD-001#R3]]). 모델을 쓰지 않는다([[JSD-DOM-002]] 5장 결정 2).

**2026-09-16에 받은 업스테이지 출력에서 확인한 것** — 규칙은 모두 여기에 기댄다.
- 요소마다 `id`가 붙는다. 제목은 `<h1>` 또는 `<p>`, 표는 `<table>`(머리글 `<thead>`, 행 `<tbody><tr><td>`)이다. 같은 모양의 제목이 문서마다 `h1`이었다 `p`였다 한다
- **요소 id는 표 하나에 하나다.** 행에는 id가 없다. 그래서 행 블록 ID를 이 파일이 만든다
- 구 제목은 `【 갑 구 】 ( 소유권에 관한 사항 )`처럼 글자 사이가 띄어져 있다
- 쪽을 넘긴 표는 제목 없이 같은 머리글로 한 번 더 온다
- OCR이 셀 안을 끊는다 — `순위번 호`, `1번근저당권설 정등기말소`, `임 차권등기명령`
- 권리자 뒤 등록번호가 가려져 온다 — 법인은 `110111-0****`, 개인은 `910814-*******`
- 취소선은 남지 않는다. 말소는 "N번…말소" 행으로만 안다
- 첫머리에 `등기사항전부증명서(말소사항 포함) - 집합건물` 제목과 `[집합건물] 주소 건물명 제N동 제N층 제N호` 줄이 온다

형식은 [[JSD-MS-001]]과 같다. 타입(`ParsedRegistry` `ParsedEntry` `Property` `Block`)은 [[JSD-DOM-002]] 2.8이다.

**표기** — `→` 반환·결과, `!` 예외, `if 조건 → 결과 · else → 결과` 분기. `norm(s)`는 모든 공백을 뺀 문자열이다.

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#service_parse.read_extract]] | HTML 한 장을 등기부로 읽는다 |
| [[#service_parse.split_blocks]] | HTML을 요소 목록으로 |
| [[#service_parse.read_property]] | 첫머리 주소와 표제부에서 주택 정보 |
| [[#service_parse.read_rows]] | 갑구·을구 표 하나의 행을 항목으로 |
| [[#service_parse.read_holder]] | 권리자 칸에서 이름과 법인 여부 |
| [[#service_parse.apply_cancellations]] | 말소 행으로 대상 항목에 말소 표시 |
| [[#service_parse.purpose_code]] | 등기목적 문구를 코드로 |
| [[#service_parse.won_to_manwon]] | 금액 문자열을 만원 정수로 |
| [[#service_parse.clean_html]] | 문서 패널에 내려갈 HTML |

---

## 2. 함수

#### service_parse.read_extract HTML 한 장을 등기부로 읽는다

**시그니처** `read_extract(html: str) -> ParsedRegistry`

근거: [[JSD-UC-001#UC-S1]] 2~6·2a·3a·5a · [[JSD-MS-003#RegistryService.create_extract]]

**처리**
1. `blocks = split_blocks(html)` · `warnings = []`
2. 문서 종류 — 표가 아닌 블록 중 `norm(text)`에 `-집합건물` → collective · `-토지` → land · `-건물` → building. 제목이 없으면 `[집합건물]` `[토지]` `[건물]` 줄로 본다. 둘 다 없으면 building + 경고 `문서 종류를 읽지 못함`
3. 블록을 순서대로 훑는다. `section = None`
   - 표가 아닌 블록 · `norm(text)`에 `【표제부】` → `section = title` · `【갑구】` → `gap` · `【을구】` → `eul`
   - 표 · if `section in (gap, eul)` → `entries += read_rows(block, section, warnings)` · if `section == title` → 표제부 표로 모아 둔다 · if `section is None` → 건너뛴다
   - 제목 없이 이어진 표는 `section`이 바뀌지 않았으므로 앞 구간에 붙는다
4. if 갑구 표와 을구 표가 하나도 없음 → `! not_registry`
5. `apply_cancellations(entries)`
6. `property = read_property(blocks, kind)`
7. if `kind != land` and `property.building_type == other` → 경고 `건물 종류를 정하지 못함`
8. `→ ParsedRegistry(kind, property, entries, panel_html = clean_html(blocks), warnings)`

**예외** `not_registry` 갑구·을구 표가 없음

**테스트 관점** 3장 정답표 4장이 필드까지 같다 · 표 없는 HTML(계약서 PDF 파싱 결과) → not_registry · 을구가 두 표로 나뉜 아파트 예시 → 을구 항목 3개 · 같은 HTML을 두 번 읽으면 같은 결과

---

#### service_parse.split_blocks HTML을 요소 목록으로

**시그니처** `split_blocks(html: str) -> list[Block]`

근거: [[JSD-DOM-002]] 4.4

**처리** — 표준 라이브러리 `html.parser.HTMLParser`
1. 최상위에서 `id` 속성이 있는 요소마다 `Block` 하나. `tag`는 요소 이름, `block_id`는 `id` 값
2. `text` — 요소 안 글자를 모아 연속 공백을 한 칸으로. `<br>`은 공백
3. `table`이면 `header` = `thead`의 첫 행 셀 글자 목록, `rows` = `tbody`의 행마다 셀 글자 목록. `thead`가 없으면 첫 행을 머리글로 본다
4. `id`가 없는 최상위 `<br>` 등은 버린다
5. HTML 엔티티는 글자로 푼다

**테스트 관점** 예시 HTML → 블록 수가 업스테이지 `elements` 수와 같다 · 표의 `rows` 길이가 `<tr>` 수와 같다 · `&amp;` → `&`

---

#### service_parse.read_property 첫머리 주소와 표제부에서 주택 정보

**시그니처** `read_property(blocks: list[Block], kind: DocKind) -> Property | None`

근거: [[JSD-UC-001#UC-S1]] 5·5a · [[JSD-DOM-001#Property]]

**처리**
1. if `kind == land` → `None`
2. 주소 줄 — `text`가 `[집합건물]` 또는 `[건물]`로 시작하는 첫 블록. 대괄호 뒤를 공백으로 나눈다
   - `lot_address` = 앞에서부터 **지번 모양 낱말**(`^\d+(-\d+)?$`)까지
   - `building_name` = 지번 뒤부터 `제`로 시작하는 낱말(`제103동` `제7층` `제702호`) 앞까지 이은 것. 없으면 None
   - 동·호수는 어디에도 남기지 않는다
3. `region = privacy.short_region(lot_address)`
4. 표제부 표 중 머리글에 `건물내역`이 있는 첫 표(1동의 건물·건물의 표시)의 `건물내역` 칸 `norm` 글자로 `building_type`
   - `아파트` → apartment · `다세대주택` 또는 `연립주택` → multi_family_unit · `다가구주택` → multi_household · `오피스텔` → officetel · 그 밖 → other
5. `is_collective = (kind == collective)`
6. `exclusive_area_m2` — 제목이 `전유부분`인 표제부 표의 `건물내역` 칸에서 마지막 `([\d.]+)㎡` · 없으면 None
7. `land_right_unregistered` — if collective and 제목에 `대지권의표시`인 표제부가 없음 → True · else → False
8. `separate_land_registry` — 표제부 표 어느 칸이든 `norm`에 `별도등기` → True · else → False
9. `→ Property(region, building_type, is_collective, land_right_unregistered, separate_land_registry, lot_address, exclusive_area_m2, building_name)`

**테스트 관점** 아파트 → `서울특별시 노원구 상계동 715` · `상계행복아파트` · apartment · 84.97 · 대지권 있음 · 다가구 → `경기도 부천시 원미구 심곡동 55-1` · 건물명 None · multi_household · 면적 None · 대지권 표가 없는 집합건물 → `land_right_unregistered` True · 주소 줄이 없으면 `lot_address` None, 경고는 read_extract가 남기지 않는다(조회가 no_region_code로 드러낸다)

---

#### service_parse.read_rows 갑구·을구 표 하나의 행을 항목으로

**시그니처** `read_rows(table: Block, section: Section, warnings: list[str]) -> list[ParsedEntry]`

근거: [[JSD-UC-001#UC-S1]] 3·3a · [[JSD-DOM-002]] 2.2 RegistryEntry

**처리**
1. 열 찾기 — `norm(header)`에서 `순위번호` `등기목적` `접수` `등기원인` `권리자및기타사항`의 위치. if `순위번호`나 `등기목적`이 없음 → 경고 `{표id} 머리글을 읽지 못함` → `[]`
2. 행마다(`i`는 tbody 안 1부터)
   1. if 셀 수가 머리글 수와 다름 → 경고 `{표id}-{i} 칸 수가 다름` → 있는 칸만 읽는다
   2. `rank_no = norm(순위번호 칸)` · if 비었음 → 경고, 이 행 건너뜀
   3. `entry_id = f"{section}-{rank_no}"` · if 같은 표·앞 표에서 이미 씀 → `-2`, `-3`을 붙이고 경고
   4. `parent_entry_id` — if `rank_no`가 `N-M` → `f"{section}-{N}"` · else None
   5. `purpose_text` = 등기목적 칸(공백 한 칸으로) · `purpose_code = purpose_code(purpose_text)`
   6. 접수 칸 — `(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일` → `received_at` · `제\s*(\d+)\s*호` → `receipt_no = "제N호"` · 못 읽으면 None + 경고 `{entry_id} 접수일을 읽지 못함`
   7. `cause` = 등기원인 칸(비었으면 None)
   8. 권리자 칸 `t`
      - `amount_manwon` — `(채권최고액|전세금|임차보증금)\s*금?\s*([\d,]+)\s*원` → `won_to_manwon` · purpose가 mortgage·jeonse_right·lease_right인데 없음 → 경고 `{entry_id} 금액을 읽지 못함`
      - `price_manwon` — `거래가액\s*금?\s*([\d,]+)\s*원` → `won_to_manwon`
      - `holder, holder_is_corporation = read_holder(section, purpose_code, t)` · if purpose가 cancellation이 아닌데 holder가 None → 경고 `{entry_id} 권리자를 읽지 못함`
   9. `block_ids = [f"{table.block_id}-{i}"]`
   10. `location_label` = `갑구 {rank_no}번` · `을구 {rank_no}번`
   11. `cancelled = False` · `cancelled_by_entry_id = None`
3. `→` 항목 목록(표 안 순서)

**테스트 관점** `1번근저당권설 정등기말소` → cancellation · 부기 `1-1` → `eul-1-1`, 부모 `eul-1` · `2026년7월18일 제30112호` → 2026-07-18 · `제30112호` · 주택임차권 행 → lease_right · 8000 · 권리자 개인 · 칸이 하나 모자란 행 → 경고 하나, 나머지 필드는 읽힌다 · 경고 문구에 이름이 없다

---

#### service_parse.read_holder 권리자 칸에서 이름과 법인 여부

**시그니처** `read_holder(section: Section, purpose: PurposeCode, text: str) -> tuple[str | None, bool | None]`

근거: [[JSD-API-002]] 1.3 · [[JSD-DOM-002]] 4.4 권리자 성격

**처리**
1. 역할 낱말 — purpose로 고른다
   - ownership_preserve · ownership_transfer → `소유자` 또는 `공유자`
   - mortgage · mortgage_change → `근저당권자`
   - jeonse_right → `전세권자` · lease_right → `임차권자`
   - seizure · provisional_seizure · injunction · auction → `채권자` 또는 `권리자`
   - trust → `수탁자` · provisional_registration → `가등기권자`
   - 그 밖 → 위 낱말 중 먼저 나오는 것
2. if 역할 낱말이 없음 → `(None, None)`
3. 역할 낱말 **마지막** 등장 뒤를 공백으로 나눈다 — 근저당 칸의 `채무자 이서연`은 역할이 달라 잡히지 않는다
4. `공유자`면 `지분 …` 낱말을 건너뛰고 이름마다 모아 `", "`로 잇는다
5. `name` = 첫 낱말 · 다음 낱말이
   - `^\d{6}-\d\*{4}$` → 법인 True
   - `^\d{6}-\*{7}$` 또는 `^\d{6}-\d\*{6}$` → 법인 False
   - 그 밖 → 이름에 법인 표지(`주식회사` `(주)` `은행` `금고` `공사` `조합` `신탁` `캐피탈` `저축은행` `보험`)가 있으면 True, 아니면 False
6. `→ (name, is_corporation)`

**테스트 관점** `소유자 화곡건설주식회사 110111-5**** …` → (`화곡건설주식회사`, True) · `소유자 이서연 910814-******* …` → (`이서연`, False) · `채권최고액 … 채무자 이서연 … 근저당권자 화곡새마을금고 114271-0****` → (`화곡새마을금고`, True) · `임차권자 최지우 950201-*******` → (`최지우`, False) · 말소 행의 빈 칸 → (None, None)

---

#### service_parse.apply_cancellations 말소 행으로 대상 항목에 말소 표시

**시그니처** `apply_cancellations(entries: list[ParsedEntry]) -> None`

근거: [[JSD-UC-001#UC-S1]] 4 · [[JSD-DOM-001#RegistryEntry]]

**처리** — 항목을 제자리에서 고친다
1. `purpose_code == cancellation`인 항목 `c`마다 `norm(c.purpose_text)`에서 `^(\d+(?:-\d+)?)번` → `N`
2. `target` = 같은 구(`c.entry_id`의 앞부분)에서 `rank_no == N`인 항목
3. if `target` 있음 → `target.cancelled = True` · `target.cancelled_by_entry_id = c.entry_id`
4. else → 경고 `{c.entry_id} 말소 대상 {N}번을 찾지 못함`(경고는 부른 쪽 목록에 더한다)
5. 부기 항목의 주등기가 말소되면 부기도 `cancelled = True` · 같은 말소 항목을 가리킨다

**테스트 관점** 아파트 예시 → `eul-1` cancelled, 말소한 항목 `eul-2` · `eul-2` 자신은 cancelled가 아니다 · 없는 번호 말소 → 경고만

---

#### service_parse.purpose_code 등기목적 문구를 코드로

**시그니처** `purpose_code(text: str) -> PurposeCode`

근거: [[JSD-DOM-002]] 2.9 PurposeCode

**처리** `s = norm(text)`. 표를 위에서부터 보고 처음 맞는 것. 순서가 규칙이다 — 긴 말이 먼저

| `s`에 이것이 있으면 | 코드 |
|---|---|
| `말소` | cancellation |
| `가압류` | provisional_seizure |
| `압류` | seizure |
| `가처분` | injunction |
| `가등기` | provisional_registration |
| `경매개시결정` | auction |
| `신탁` | trust |
| `예고등기` | notice_registration |
| `근저당권변경` | mortgage_change |
| `근저당권설정` 또는 `근저당권이전` | mortgage |
| `전세권` | jeonse_right |
| `임차권` | lease_right |
| `소유권보존` | ownership_preserve |
| `소유권이전` | ownership_transfer |
| 그 밖 | other |

**테스트 관점** `소유권이전청구권가등기` → provisional_registration(소유권이전이 아니다) · `1번근저당권설정등기말소` → cancellation · `근저당권변경` → mortgage_change · `주택임차권` → lease_right · `임의경매개시결정` → auction

---

#### service_parse.won_to_manwon 금액 문자열을 만원 정수로

**시그니처** `won_to_manwon(text: str) -> int | None`

**처리** `금` · `,` · `원` · 공백을 뺀다 · if 숫자만 남음 → `int(s) // 10000` · else → None

**테스트 관점** `금210,000,000원` → 21000 · `금 80,000,000 원` → 8000 · `금15,555원` → 1 · `일억원` → None

---

#### service_parse.clean_html 문서 패널에 내려갈 HTML

**시그니처** `clean_html(blocks: list[Block]) -> str`

근거: [[JSD-UI-001#UI-2]] 요소 7 · [[JSD-DOM-002]] 4.4 panel_html

**처리**
1. 블록마다 허용 태그로 다시 쓴다 — `h1` `h2` `h3`은 그대로, 나머지 표가 아닌 블록은 `p`
2. 속성은 `data-block-id` 하나만. `style` `id` `class` `data-category`는 버린다
3. 표는 `<table data-block-id="{id}">` + `<thead><tr><th>머리글…</th></tr></thead>` + `<tbody>`에서 행마다 `<tr data-block-id="{id}-{i}">` + `<td>` 셀
4. 모든 글자는 HTML 이스케이프한다. 원본 태그를 그대로 옮기지 않는다 — 스크립트·링크·이미지가 들어올 길이 없다
5. `→` 블록을 줄바꿈으로 이은 문자열

**테스트 관점** 결과에 `style` `script` `onerror`가 없다 · 행 `tr`마다 `data-block-id`가 있고 `read_rows`의 `block_ids`와 같다 · `<b>` 같은 원문 태그는 글자로 나오지 않고 사라진다(글자만 남음)

---

## 3. 예시 정답표

테스트 고정본은 `tests/registry/fixtures/`의 업스테이지 HTML 4장이다. 금액은 만원, 권리자의 (법)은 법인이다.

**신축 빌라 — 다세대·주의** (`multi_family_caution`, 집합건물)

| 주택 | 값 |
|---|---|
| lot_address · building_name | 서울특별시 강서구 화곡동 123-4 · 해피빌 |
| building_type · 전용면적 · 대지권 미등기 · 별도등기 | multi_family_unit · 44.91 · False · False |

| entry_id | 코드 | 접수 | 금액 | 거래가액 | 권리자 | 말소 | 블록 |
|---|---|---|---|---|---|---|---|
| gap-1 | ownership_preserve | 2025-11-03 제88213호 | | | 화곡건설주식회사 (법) | | 11-1 |
| gap-2 | ownership_transfer | 2026-02-10 제5521호 | | 50000 | 이서연 | | 11-2 |
| eul-1 | mortgage | 2026-07-18 제30112호 | 21000 | | 화곡새마을금고 (법) | | 13-1 |

**아파트 — 안전** (`apartment_safe`, 집합건물. 을구가 쪽을 넘겨 표 둘)

| 주택 | 값 |
|---|---|
| lot_address · building_name | 서울특별시 노원구 상계동 715 · 상계행복아파트 |
| building_type · 전용면적 · 대지권 미등기 · 별도등기 | apartment · 84.97 · False · False |

| entry_id | 코드 | 접수 | 금액 | 거래가액 | 권리자 | 말소 | 블록 |
|---|---|---|---|---|---|---|---|
| gap-1 | ownership_preserve | 1994-05-01 제21093호 | | | 상계주택건설주식회사 (법) | | 11-1 |
| gap-2 | ownership_transfer | 2004-09-03 제45120호 | | | 정수현 | | 11-2 |
| gap-3 | ownership_transfer | 2019-03-12 제10877호 | | 48000 | 김민수 | | 11-3 |
| eul-1 | mortgage | 2004-09-03 제45121호 | 15600 | | 주식회사우리은행 (법) | eul-2 | 13-1 |
| eul-2 | cancellation | 2019-03-12 제10876호 | | | | | 13-2 |
| eul-3 | mortgage | 2021-06-01 제23310호 | 12000 | | 주식회사국민은행 (법) | | 14-1 |

**다가구 — 위험** (`multi_household_danger`, 건물)

| 주택 | 값 |
|---|---|
| lot_address · building_name | 경기도 부천시 원미구 심곡동 55-1 · 없음 |
| building_type · 전용면적 · 대지권 미등기 · 별도등기 | multi_household · 없음 · False · False |

| entry_id | 코드 | 접수 | 금액 | 거래가액 | 권리자 | 말소 | 블록 |
|---|---|---|---|---|---|---|---|
| gap-1 | ownership_preserve | 2012-04-02 제12034호 | | | 박영호 | | 7-1 |
| gap-2 | ownership_transfer | 2023-08-20 제41022호 | | | 주식회사부천하우징 (법) | | 7-2 |
| eul-1 | mortgage | 2023-08-20 제41023호 | 18000 | | 농협은행주식회사 (법) | | 9-1 |
| eul-2 | mortgage | 2024-01-15 제2210호 | 12000 | | 페퍼저축은행주식회사 (법) | | 9-2 |
| eul-3 | lease_right | 2025-12-01 제60331호 | 8000 | | 최지우 | | 9-3 |

**다가구의 토지 등기부** (`multi_household_danger_land`, 토지. 주택 정보 None). 두 번째 문서로 저장되면 `land-` 접두어가 붙는다([[JSD-MS-003#RegistryService.create_extract]])

| entry_id | 코드 | 접수 | 금액 | 거래가액 | 권리자 | 말소 | 블록 |
|---|---|---|---|---|---|---|---|
| gap-1 | ownership_transfer | 2023-08-20 제41022호 | | | 주식회사부천하우징 (법) | | 7-1 |
| eul-1 | mortgage | 2023-08-20 제41023호 | 10000 | | 농협은행주식회사 (법) | | 9-1 |

네 장 모두 경고는 없다.

---

## 4. 미결사항

- [ ] 권리자 이름을 역할 낱말 뒤 **첫 낱말**로 읽는다. OCR이 이름 가운데를 띄우면(`주식회사 우리은행`) 앞부분만 잡힌다. 실제 인터넷등기소 PDF로 확인하고, 필요하면 등록번호 모양 앞까지 이어 붙인다
- [ ] 예시에 없는 모양 — 부기등기(근저당권변경), 공유자 지분, 가압류·신탁·가등기 행은 규칙만 있고 고정본이 없다. 가상 등기부를 한 장 더 만들어 정답표에 넣을지
- [ ] 쪽을 넘긴 표가 머리글 없이 오는 경우 — 이번 출력은 머리글을 반복했다. 머리글이 없으면 앞 표의 열 위치를 쓸지
- [ ] 주민번호 앞자리가 가려지지 않은 채 원문 HTML(`panel_html`)에 남는다 — 본인이 올린 원문을 본인에게 보여 주는 패널이라 두었다. 24시간 뒤 지워진다
