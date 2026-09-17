---
doc_id: JSD-MS-007
type: MS
title: 보증금지킴 — 미니스펙 CitationService
status: draft
upstream: [JSD-DOM-002, JSD-DOM-003, JSD-SEQ-001, JSD-API-001, JSD-API-002]
---

# MINISPEC — CitationService

## 0. 이 문서가 다루는 것

`citation/service.py`의 함수 7개. 클래스 명세 [[JSD-DOM-002#CitationService]](4.7)의 시그니처를 함수 안쪽까지 내린 것이다. 에이전트 문장·의견서의 사실이 등기부 어느 줄에 기대는지 잇고, 원문 한 줄에서 그 줄이 쓰인 곳으로 거꾸로 간다([[JSD-DOM-001#Citation]]).

형식은 [[JSD-MS-001]]과 같다. 타입(`Citation` DTO · `CitedText` `CitationRef` `BlockUsages` `BlockExcerpt` `RegistryEntry`)은 [[JSD-DOM-002]] 2.8, 테이블은 [[JSD-DOM-003#citations]]이다.

**표기** — `→` 반환·결과, `!` 예외, `DB:` 자기 테이블 접근(`citation/crud.py`), `if 조건 → 결과 · else → 결과` 분기.

**이 파일이 지키는 것**
- **인용 행 하나가 진실이다.** 메시지·의견서 본문에는 `{{c1}}` 표식만 있고, 인용은 응답을 만들 때 이 행에서 붙인다([[JSD-DOM-002]] 5장 결정 5). 앞방향과 역방향이 같은 행을 읽는다
- **지어낼 수 없다.** 인용을 만들기 전에 반드시 `RegistryService.entries`로 이 검토에 있는 항목인지 대조한다. 대조를 통과한 항목이 없으면 인용을 만들지 않는다
- 인용 행 하나는 등기부 하나를 가리킨다. 항목이 두 등기부(건물·토지)에 걸치면 등기부마다 행 하나다
- 트랜잭션을 열지 않는다. 부른 쪽의 트랜잭션 안에서 돈다

**키** — `key`는 한 자리(`used_in`·`ref`) 안에서 `c1`·`c2`… 순서다. 새 키 번호는 그 자리 기존 행 수 + 1이다.

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#CitationService.resolve_markers]] | 문장의 `{{entry:…}}` 표식을 인용으로 |
| [[#CitationService.cite]] | 항목 ID 목록으로 인용 만들기 |
| [[#CitationService.for_messages]] | 메시지들의 인용 |
| [[#CitationService.for_report]] | 의견서의 인용 |
| [[#CitationService.usages]] | 원문 블록 하나가 쓰인 곳 |
| [[#CitationService.clear_report]] | 이전 의견서의 인용 지우기 |
| [[#CitationService.delete_for_review]] | 검토의 인용 전부 지우기 |

---

## 2. 함수

#### CitationService.resolve_markers 문장의 표식을 인용으로

**시그니처** `resolve_markers(review_id: str, text: str, used_in: CitationUse, ref: str) -> CitedText`

근거: [[JSD-SEQ-001#SEQ-3]] · [[JSD-SEQ-001#SEQ-8]] · [[JSD-API-002]] 1.4 · [[JSD-UC-001#UC-A1]] 7a

**입력** 에이전트 말풍선(`used_in message`, `ref = message_id`) 또는 의견서 결론(`used_in conclusion`, `ref = ""`)

**처리**
1. 표식 찾기 — `\{\{entry:([^}]+)\}\}`. 없으면 `→ CitedText(text, [], 0)`
2. `ids` = 모든 표식의 쉼표로 나눈 `entry_id`(앞뒤 공백 제거, 중복 제거)
3. `known = {e.entry_id: e for e in RegistryService.entries(review_id, ids)}`
4. `n = DB: count citations where review_id and used_in and ref` · `citations = []` · `dropped = 0`
5. 표식마다 문장 안 순서대로
   1. `hits = [known[i] for i in 표식 ids if i in known]`
   2. if `hits` 비었음 → 표식을 빈 문자열로 바꾼다 · `dropped += 1`
   3. else → `hits`를 `document_id`로 묶는다(등기부 순서). 묶음마다
      - `n += 1` · `key = f"c{n}"`
      - `usage_label` = 표식이 든 문장(앞뒤 문장 부호까지)을 40자에서 자른 것. 결론이면 앞에 `결론: `
      - `DB: citations insert (review_id, used_in, ref, key, label = 묶음 첫 항목의 location_label, usage_label, document_id, entry_ids, block_ids = 묶음 항목 block_ids 합)`
      - `citations += Citation(key, label, document_id, block_ids, entry_ids)`
   4. 표식을 묶음 키들을 이은 `{{c1}}{{c2}}`로 바꾼다
6. 연속 공백 한 칸으로 정리 → `→ CitedText(text, citations, dropped)`

**테스트 관점** `{{entry:eul-2}}` 있음 → `{{c1}}`, 행 1개, label `을구 2번` · `{{entry:gap-1,gap-2}}` → 한 행에 두 항목 · `{{entry:eul-1,land-eul-1}}` → `{{c1}}{{c2}}`, 등기부마다 한 행 · 없는 `eul-9` → 표식 삭제, dropped 1, 행 없음 · 같은 메시지로 두 번 부르면 두 번째 키는 이어진다 · 다른 검토의 `entry_id`는 대조에서 빠진다

---

#### CitationService.cite 항목 ID 목록으로 인용 만들기

**시그니처** `cite(review_id: str, used_in: CitationUse, ref: str, usage_label: str, entry_ids: list[str]) -> list[Citation]`

근거: [[JSD-SEQ-001#SEQ-8]] · [[JSD-DOM-001#Citation]]

**입력** 의견서의 합산(`rights`, `ref ""`)·신호(`signal`, 신호 code)·확인한 것(`checked`, 항목 code)·특약(`clause`, 특약 순번)

**처리**
1. if `entry_ids` 비었음 → `[]`
2. `hits = RegistryService.entries(review_id, entry_ids)` · if 비었음 → `[]` — 근거 없는 인용을 만들지 않는다
3. `hits`를 `document_id`로 묶고, 묶음마다 resolve_markers 5.3과 같이 키를 이어 붙여 insert
4. `→ Citation` 목록

**테스트 관점** 합산 `based_on` [eul-1, gap-2] → 한 행(같은 등기부) · 모두 없는 ID → 빈 목록, 행 없음 · 신호 code가 `ref`로 남는다

---

#### CitationService.for_messages 메시지들의 인용

**시그니처** `for_messages(review_id: str, message_ids: list[str]) -> dict[str, list[Citation]]`

근거: [[JSD-SEQ-001#SEQ-11]] · [[JSD-API-001#GET/api/reviews/{id}/messages]]

**처리** if `message_ids` 비었음 → `{}` · `DB: citations where review_id and used_in message and ref in message_ids order by ref, id` → `{ref: [Citation…]}`. 인용 없는 메시지는 키가 없다

**테스트 관점** 메시지 200개에 쿼리 1번 · 순서가 key 순서

---

#### CitationService.for_report 의견서의 인용

**시그니처** `for_report(review_id: str) -> list[CitationRef]`

근거: [[JSD-SEQ-001#SEQ-14]] · [[JSD-API-001#GET/api/reviews/{id}/report]]

**처리** `DB: citations where review_id and used_in != message order by id` → `CitationRef(used_in, ref, Citation)` 목록. 붙이는 자리는 `ReportService.get`이 정한다

**테스트 관점** 메시지 인용은 빠진다 · 다시 쓴 뒤에는 새 판의 인용만 있다

---

#### CitationService.usages 원문 블록 하나가 쓰인 곳

**시그니처** `usages(review_id: str, block_id: str) -> BlockUsages`

근거: [[JSD-SEQ-001#SEQ-13]] · [[JSD-API-001#GET/api/reviews/{id}/blocks/{blockId}]] · [[JSD-UI-001#UI-2]] 규칙

**처리**
1. `ex = RegistryService.block_excerpt(review_id, block_id)` · if None → `! not_found`
2. `rows = DB: citations where review_id and block_ids @> jsonb_build_array(block_id) order by id`
3. 행마다 `{kind: used_in, label: usage_label}` + if signal → `signal_code = ref` · if message → `message_id = ref`
4. 같은 (`used_in`, `ref`)는 한 번만
5. `→ BlockUsages(block_id, excerpt = ex.excerpt, used_in)`

**예외** `not_found` 블록이 이 검토 원문의 항목 블록이 아님

**테스트 관점** 을구 2번 줄 → 합산·신호·메시지가 모두 나온다 · 머리글 블록 → 404 · 아무 곳에도 안 쓰인 줄 → 발췌와 빈 목록

---

#### CitationService.clear_report 이전 의견서의 인용 지우기

**시그니처** `clear_report(review_id: str) -> None`

근거: [[JSD-SEQ-001#SEQ-8]] · [[JSD-MS-008#ReportService.write]]

**처리** `DB: delete citations where review_id and used_in != message`. `ReportService.write`가 새 인용을 만들기 전에 같은 트랜잭션에서 부른다

**테스트 관점** 메시지 인용은 남는다 · 새 결론 인용을 만든 뒤에 부르면 안 된다(순서는 write가 지킨다)

---

#### CitationService.delete_for_review 검토의 인용 전부 지우기

**시그니처** `delete_for_review(review_id: str) -> None`

근거: [[JSD-SEQ-001#SEQ-15]] · [[JSD-SEQ-001#SEQ-16]]

**처리** `DB: delete citations where review_id`

**테스트 관점** 지운 뒤 0행

---

## 3. 미결사항

- [ ] 한 자리에 같은 신호 code가 둘이면 `ref`로 구분되지 않는다([[JSD-DOM-003]] 5장) — 신호 code는 검토당 하나만 나오므로 지금은 생기지 않는다
- [ ] `usage_label`을 문장 40자로 자른다 — 역방향 목록에서 문장이 잘려 보인다. 화면에서 너무 짧으면 60자로 늘린다
