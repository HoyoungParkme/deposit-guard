---
doc_id: JSD-MS-003
type: MS
title: 보증금지킴 — 미니스펙 RegistryService
status: draft
upstream: [JSD-DOM-002, JSD-DOM-003, JSD-SEQ-001, JSD-API-001, JSD-API-002]
---

# MINISPEC — RegistryService

## 0. 이 문서가 다루는 것

`registry/service.py`의 함수 11개. 클래스 명세 [[JSD-DOM-002#RegistryService]](4.3)의 시그니처를 함수 안쪽까지 내린 것이다. 이 파일을 짤 때 이 문서를 본다. 표를 읽는 순수 함수 `registry/service_parse.py`(4.4)는 다음 문서다.

형식은 [[JSD-MS-001]]과 같다. 타입(`Registry` `Property` `RegistryEntry` `DocumentBrief` `ParsedDocument` `ParsedRegistry` `Owner` `BlockExcerpt`)은 [[JSD-DOM-002]] 2.8, 테이블은 [[JSD-DOM-003#registry_extracts]]·[[JSD-DOM-003#registry_entries]]다.

**표기** — `→` 반환·결과, `!` 예외, `DB:` 자기 테이블 접근(`registry/crud.py`), `if 조건 → 결과 · else → 결과` 분기.

**이 파일이 지키는 것**
- 자기 테이블은 `registry_extracts`·`registry_entries` 둘이다. 다른 도메인을 부르지 않는다 — 부르는 것은 자기 포트(`DocumentParser`)뿐이다([[JSD-DOM-002]] 3.2)
- **가리지 않은 값을 돌려준다.** 이름을 가리는 것과 소유자 일치 계산은 `review`가 한다. 계약 상대방 이름은 이 도메인에 들어오지 않는다
- 트랜잭션을 열지 않는다. 쓰는 함수는 부른 쪽(`ReviewService`)의 트랜잭션 안에서 돈다
- 파일 바이트는 `parse`의 인자로만 오간다. 저장하지 않는다

**등기부 순서** — 여러 함수가 같은 순서를 쓴다. 문서는 `registry_extracts.created_at` 오름차순, 문서 안은 갑구 먼저(`CASE section WHEN 'gap' THEN 0 ELSE 1 END`), 같은 구 안은 `registry_entries.id` 오름차순. `section`을 글자로 정렬하지 않는다 — eul이 gap보다 앞선다([[JSD-DOM-003]] 4장 3).

**건물 등기부** — 검토에서 `kind`가 land가 아닌 첫 문서다. 주택 정보와 소유자는 여기서만 읽는다.

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#RegistryService.parse]] | 파일 바이트를 업스테이지 HTML로 |
| [[#RegistryService.create_extract]] | 파싱 HTML에서 항목을 읽어 저장 |
| [[#RegistryService.read]] | 에이전트가 읽을 등기부 한 장 |
| [[#RegistryService.list]] | 문서 목록 |
| [[#RegistryService.get_html]] | 문서 패널 원문 |
| [[#RegistryService.property]] | 건물 등기부의 주택 정보 |
| [[#RegistryService.owner]] | 현재 소유자 |
| [[#RegistryService.holder_names]] | 개인 권리자 이름, 등기부 순서 |
| [[#RegistryService.entries]] | 이 검토의 등기 항목 |
| [[#RegistryService.block_excerpt]] | 원문 블록 하나의 항목과 한 줄 |
| [[#RegistryService.delete_for_review]] | 검토의 문서·항목 삭제 |

---

## 2. 함수

#### RegistryService.parse 파일 바이트를 업스테이지 HTML로

**시그니처** `async parse(data: bytes, media_type: str) -> ParsedDocument`

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-UC-001#UC-S1]] 1·1a · [[JSD-INFRA-001#C8]]

**처리**
1. `→ await self.parser.parse(data, media_type)` — 포트 한 번. 타임아웃 30초·재시도 1회는 어댑터 안이다
2. 어댑터가 재시도 뒤 실패하면 `! parse_failed`를 그대로 올린다
3. 바이트를 변수·로그·예외 메시지에 남기지 않는다

**테스트 관점** 가짜 파서가 HTML을 돌려주면 그대로 · 가짜 파서가 parse_failed → 그대로 올라온다 · DB를 만지지 않는다

---

#### RegistryService.create_extract 파싱 HTML에서 항목을 읽어 저장

**시그니처** `create_extract(review_id: str, html: str, page_count: int, file_sha256: str) -> DocumentBrief`

근거: [[JSD-SEQ-001#SEQ-1]] 22~27 · [[JSD-SEQ-001#SEQ-7]] · [[JSD-UC-001#UC-S1]] 2~6·2a · [[JSD-DOM-001#RegistryExtract]]

**입력** 업스테이지 HTML(캐시에서 왔을 수 있다), 쪽수, 파일 해시. 부른 쪽의 트랜잭션 안에서 부른다

**처리**
1. `parsed = service_parse.read_extract(html)` — 갑구·을구가 없으면 거기서 `! not_registry`
2. `existing = DB: registry_extracts where review_id` (등기부 순서)
3. if `len(existing) ≥ 2` → `! wrong_state` · if `len(existing) == 1` and `parsed.kind != land` → `! wrong_state`
4. `prefix = "land-" if existing else ""`
5. `label` — building → `건물 등기부` · collective → `집합건물 등기부` · land → `토지 등기부`
6. `DB: registry_extracts insert` — `kind = parsed.kind`, `label`, `page_count`, `file_sha256`, `html = parsed.panel_html`, `warnings = parsed.warnings`, `read_by_agent false`. if `parsed.kind != land` and `parsed.property` → `lot_address · region · building_type · land_right_unregistered · separate_land_registry · exclusive_area_m2 · building_name`을 채운다 · else → 모두 null
7. `parsed.entries`를 문서 순서대로 `DB: registry_entries insert` — `entry_id = prefix + 원래 id`, `parent_entry_id`·`cancelled_by_entry_id`에도 같은 `prefix`, `location_label`은 토지면 앞에 `토지 `를 붙인다(`토지 을구 1번`). 한 번에 여러 행을 넣되 순서를 지킨다 — `id` 순서가 문서 순서다
8. `→ DocumentBrief(document_id, kind, label, page_count)`

**출력** `DocumentBrief`

**예외**

| 조건 | 에러 |
|---|---|
| 갑구·을구가 없음 | `not_registry` |
| 이미 두 장, 두 번째가 토지 등기부가 아님 | `wrong_state` |

**호출하는 것** `service_parse.read_extract`

**테스트 관점** 다세대 예시 HTML → 문서 1행, 항목 수가 정답표와 같다 · 부기 `1-1`의 `parent_entry_id`가 `eul-1` · 토지 등기부를 두 번째로 → `land-gap-1`, 주택 열은 null, 라벨 `토지 을구 1번` · 두 번째가 건물 등기부 → wrong_state · 세 번째 → wrong_state · 저장된 `html`에 `data-block-id`가 있고 스크립트 태그가 없다

---

#### RegistryService.read 에이전트가 읽을 등기부 한 장

**시그니처** `read(review_id: str, document_id: str | None = None) -> Registry`

근거: [[JSD-SEQ-001#SEQ-4]] · [[JSD-API-002#read_registry]] · [[JSD-UC-001#UC-S1]] 6

**처리**
1. if `document_id` → `ex = DB: registry_extracts where id = document_id and review_id` · if 없음 → `! not_found`
2. else → `ex = DB: registry_extracts where review_id and read_by_agent false` 등기부 순서 첫 행 · if 없음 → 이미 다 읽었으면 등기부 순서 마지막 행 · 그래도 없으면 `! not_found`
3. `DB: registry_extracts set read_by_agent true where id = ex.id`
4. `rows = DB: registry_entries where extract_id = ex.id order by id`
5. `building = Property(ex의 주택 열)` if `ex.kind != land` else None
6. `→ Registry(document_id = ex.id, doc_kind = ex.kind, building, gap = section gap 행들, eul = section eul 행들, warnings = ex.warnings)` — 행은 `RegistryEntry` DTO(내부 필드 포함)

**예외** `not_found` 없는 문서 · 이 검토에 문서가 없음

**테스트 관점** 인자 없이 두 번 부르면 첫째는 건물, 둘째는 토지 · 셋째는 마지막 문서를 다시 준다 · 다른 검토의 `document_id` → not_found · 이름이 가려지지 않은 채 온다(가리기는 루프 몫)

---

#### RegistryService.list 문서 목록

**시그니처** `list(review_id: str) -> list[DocumentBrief]`

근거: [[JSD-API-001#GET/api/reviews/{id}/documents]] · [[JSD-SEQ-001#SEQ-12]]

**처리** `DB: registry_extracts(id, kind, label, page_count) where review_id` 등기부 순서 → `DocumentBrief` 목록. `html`을 읽지 않는다

**테스트 관점** 문서가 없으면 빈 목록 · 올린 순서대로

---

#### RegistryService.get_html 문서 패널 원문

**시그니처** `get_html(review_id: str, document_id: str) -> str`

근거: [[JSD-API-001#GET/api/reviews/{id}/documents/{documentId}]] · [[JSD-UI-001#UI-2]] 요소 7

**처리** `DB: registry_extracts.html where id = document_id and review_id` · if 없음 → `! not_found` · else → html. 허용 태그 정리는 저장 때 끝났다(`service_parse`). 라우터가 `text/html`로 내보낸다

**테스트 관점** 다른 검토의 문서 → not_found · 돌려준 HTML의 `data-block-id`가 `registry_entries.block_ids`와 겹친다

---

#### RegistryService.property 건물 등기부의 주택 정보

**시그니처** `property(review_id: str) -> Property | None`

근거: [[JSD-SEQ-001#SEQ-6]] · [[JSD-SEQ-001#SEQ-12]] · [[JSD-UC-001#UC-S2]]

**처리** 건물 등기부(`kind != land` 등기부 순서 첫 행)의 주택 열 → `Property`(내부 필드 `lot_address` `exclusive_area_m2` `building_name` 포함) · 없으면 None

**테스트 관점** 토지 등기부만 있으면 None · 내부 필드가 채워져 온다(조회용)

---

#### RegistryService.owner 현재 소유자

**시그니처** `owner(review_id: str) -> Owner | None`

근거: [[JSD-SEQ-001#SEQ-4]] · [[JSD-SEQ-001#SEQ-6]] · [[JSD-UC-001#UC-S6]] 2a

**처리**
1. 건물 등기부의 `DB: registry_entries where section gap and cancelled false and purpose_code in (ownership_preserve, ownership_transfer) order by id desc limit 1`
2. if 없음 → None
3. if `holder`에 여러 이름(쉼표·가운뎃점으로 나뉨) → 첫 이름만 · 로그에 `review_id`와 `co_owned` 경고(이름은 남기지 않는다)
4. `→ Owner(name, is_corporation = holder_is_corporation or False, acquired_at = received_at, cause = purpose_code, entry_id)`

**테스트 관점** 보존 뒤 이전 → 이전의 권리자 · 이전 항목이 말소됐으면 그 앞 항목 · 토지 등기부의 갑구는 보지 않는다 · 공유자 둘 → 첫 이름

---

#### RegistryService.holder_names 개인 권리자 이름, 등기부 순서

**시그니처** `holder_names(review_id: str) -> list[str]`

근거: [[JSD-API-002]] 1.3 · [[JSD-MS-002#service_agent.mask_for_model]]

**처리** `DB: registry_entries.holder where review_id and holder is not null and holder_is_corporation is not true` 등기부 순서 → 이름 목록. 같은 이름도 나온 대로 둔다(라벨은 첫 등장이 정한다). 공유 표기면 이름마다 나눠 넣는다

**테스트 관점** 법인명이 없다 · 갑구 개인 A가 을구에도 나오면 두 번 들어가고 순서는 갑구가 먼저 · 토지 등기부 이름은 건물 등기부 뒤

---

#### RegistryService.entries 이 검토의 등기 항목

**시그니처** `entries(review_id: str, entry_ids: list[str] | None = None) -> list[RegistryEntry]`

근거: [[JSD-SEQ-001#SEQ-3]] · [[JSD-SEQ-001#SEQ-5]] · [[JSD-SEQ-001#SEQ-10]]

**처리** `DB: registry_entries where review_id` · if `entry_ids is not None` → `and entry_id in entry_ids` · 등기부 순서 → `RegistryEntry` 목록. 없는 ID는 조용히 빠진다. 빈 목록을 받으면 빈 목록이다 — 대조는 부르는 쪽이 한다

**테스트 관점** `["eul-2", "eul-9"]`에 eul-9가 없으면 하나만 · 다른 검토의 항목은 같은 `entry_id`여도 안 온다 · None이면 전부

---

#### RegistryService.block_excerpt 원문 블록 하나의 항목과 한 줄

**시그니처** `block_excerpt(review_id: str, block_id: str) -> BlockExcerpt | None`

근거: [[JSD-SEQ-001#SEQ-13]] · [[JSD-API-001#GET/api/reviews/{id}/blocks/{blockId}]]

**처리**
1. `row = DB: registry_entries where review_id and block_ids @> [block_id]` 첫 행 · if 없음 → None
2. `html = DB: registry_extracts.html where id = row.extract_id`
3. 표준 HTML 파서로 `data-block-id = block_id`인 요소의 텍스트를 모아 공백을 줄이고 80자에서 자른다
4. `→ BlockExcerpt(entry_id = row.entry_id, document_id = row.extract_id, excerpt)`

**테스트 관점** 을구 2번 행의 블록 → `eul-2`와 "근저당권설정 … 채권최고액 금 210,000,000원" 앞부분 · 어느 항목에도 없는 머리글 블록 → None

---

#### RegistryService.delete_for_review 검토의 문서·항목 삭제

**시그니처** `delete_for_review(review_id: str) -> list[str]`

근거: [[JSD-SEQ-001#SEQ-15]] · [[JSD-SEQ-001#SEQ-16]] · [[JSD-DOM-002]] 5장 결정 3

**처리** `hashes = DB: distinct registry_extracts.file_sha256 where review_id` → `DB: registry_entries delete where review_id` → `DB: registry_extracts delete where review_id` → `→ hashes`. 부른 쪽 트랜잭션 안

**테스트 관점** 건물·토지 두 장 → 해시 둘, 중복 없음 · 지운 뒤 두 테이블 모두 0행 · 다른 검토의 문서는 남는다

---

## 3. 미결사항

- [ ] 두 번째 문서가 토지 등기부가 아닐 때 `wrong_state`(409)로 답한다 — 화면 문구는 "토지 등기부만 더 올릴 수 있습니다". 건물 등기부를 잘못 올린 사용자가 바꿔 올리는 길(문서 교체)은 없다
- [ ] 공유 소유자 표기(쉼표·가운뎃점) 나누기는 예시 3건에 없다 — 실제 등기부 표기로 확인한다([[JSD-DOM-002]] 7장 미결)
- [ ] `block_excerpt`가 호출마다 HTML을 파싱한다 — 문서 하나가 수십 KB라 괜찮다고 본다. 느리면 항목 행에 발췌를 저장한다
