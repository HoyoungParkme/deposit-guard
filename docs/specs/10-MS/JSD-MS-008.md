---
doc_id: JSD-MS-008
type: MS
title: 보증금지킴 — 미니스펙 ReportService
status: draft
upstream: [JSD-DOM-002, JSD-DOM-003, JSD-SEQ-001, JSD-API-001, JSD-PRD-001, JSD-RFQ-001]
---

# MINISPEC — ReportService

## 0. 이 문서가 다루는 것

`report/service.py`의 함수 8개와 상수 파일 `report/catalog.py`. 클래스 명세 [[JSD-DOM-002#ReportService]](4.8)의 시그니처를 함수 안쪽까지 내린 것이다. 의견서의 구성은 고정이고 문장만 생성한다([[JSD-PRD-001#R9]]). 등급·수치는 `rules`가 낸 값을 옮기기만 한다.

형식은 [[JSD-MS-001]]과 같다. 타입(`ReportInput` `ReportResult` `Report` `Todo` `SpecialClause` `SentenceRequest` `Sentences` `Shareable` `CitationRef`)은 [[JSD-DOM-002]] 2.8, 테이블은 [[JSD-DOM-003#opinions]]이다.

**표기** — `→` 반환·결과, `!` 예외, `DB:` 자기 테이블 접근(`report/crud.py`), `if 조건 → 결과 · else → 결과` 분기. `fmt(n)`은 `money.format_manwon`, `pct(r)`은 `round(r × 100)`%다.

**이 파일이 지키는 것**
- 등급·신호·합산·확인한 것은 `ReportInput`에서 옮기고 여기서 계산하지 않는다
- 모델에 주는 것은 `SentenceRequest`뿐이고, 의견서 전문은 모델로 가지 않는다. 입력에는 처음부터 개인 이름이 없다
- 생성된 문장이 수치·등급을 바꾸면 그 문장을 템플릿 문장으로 바꾸고 교정 수를 올린다
- 문장 생성은 트랜잭션 밖이다. 인용 지우기부터 의견서 덮기까지는 한 트랜잭션이다
- `body`에는 인용을 싣지 않는다. 결론 문장의 `{{c1}}` 표식만 남고 인용은 `get`이 붙인다

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#ReportService.write]] | 의견서를 만들어 덮는다 |
| [[#ReportService.pick_todos]] | 단계별 할 일 고르기 |
| [[#ReportService.pick_clauses]] | 특약 고르고 빈칸 채우기 |
| [[#ReportService.template_sentences]] | 모델 없이 만드는 문장 |
| [[#ReportService.get]] | 의견서와 인용 |
| [[#ReportService.exists]] | 의견서가 있는지 |
| [[#ReportService.shareable]] | 공유본에 담을 사본 |
| [[#ReportService.delete_for_review]] | 의견서 삭제 |

---

## 2. 함수

#### ReportService.write 의견서를 만들어 덮는다

**시그니처** `async write(review_id: str, inp: ReportInput, agent_notes: str | None, revision_reason: str | None) -> ReportResult`

근거: [[JSD-SEQ-001#SEQ-8]] · [[JSD-UC-001#UC-S8]] 1~5·3a · [[JSD-API-002#write_report]] · [[JSD-PRD-001#R9]]

**처리**
1. `todos = pick_todos(inp)` · `clauses = pick_clauses(inp)` · `base = template_sentences(inp)`
2. 문장 — `llm_fallback = False` · `tokens = (0, 0)`
   - if `inp.use_model` → `s = await SentenceWriter.write(SentenceRequest(grade, rights, signals, agent_notes, revision_reason))` — 어댑터가 재시도 1회 뒤에도 실패하면 `s = base`, `llm_fallback = True` · 성공이면 `tokens = (s.tokens_in, s.tokens_out)`
   - else → `s = base`, `llm_fallback = True`
   - 모자란 곳은 `base`로 채운다 — 설명이 없는 신호 code, 물어볼 것이 3개 미만이면 `base`에서 보태고 5개에서 자른다
3. 후검증 — `allowed_manwon` = `rights`의 금액 전부 · `deposit_manwon` · `entries`의 `amount_manwon`·`price_manwon` · `allowed_ratios` = `debt_ratio`·`senior_ratio` · `grade = check.grade.level`
   - 결론 · 신호별 설명 · 물어볼 것 문장마다 `factcheck.contradicts(문장, …)` · if true → `base`의 같은 자리 문장으로 바꾸고 `corrections += 1`(물어볼 것은 그 문장을 뺀다)
4. `now = 지금` · 트랜잭션 하나
   1. `CitationService.clear_report(review_id)`
   2. `cited = CitationService.resolve_markers(review_id, s.conclusion, conclusion, "")` · `corrections += cited.dropped`
   3. 합산 — `CitationService.cite(review_id, rights, "", "선순위 합산 " + fmt(total) + (부채비율이 있으면 " (부채비율 " + pct + ")"), rights.based_on)`
   4. 신호마다 `cite(review_id, signal, code, label, entry_ids)` · 확인한 것마다 `cite(review_id, checked, code, label, entry_ids)` · 특약마다 `cite(review_id, clause, str(순번), title, 특약 entry_ids)`
   5. `body = Report(grade, conclusion {text: cited.text}, rights, signals[{code, severity, label, explanation, source, source_date}], checked[{code, label, result}], todos, clauses, questions_to_ask, notices = NOTICES + 규칙 버전 줄, corrections, llm_fallback, revision_no, revision_reason)` — `citations`는 모두 빈 목록
   6. `prev = DB: opinions.revision_no where review_id` · `revision_no = (prev ?? 0) + 1`
   7. `DB: opinions upsert on conflict (review_id)` — `body`, `subject = {region_short: property.region, building_type, deposit_manwon, contract_type, reviewed_at: now}`, `revision_no`, `revision_reason`, `written_at now`
5. `→ ReportResult(grade.level, len(signals), len(unknowns), corrections, rule_version, revision_no, revision_reason, llm_fallback, tokens_in, tokens_out)`

**호출하는 것** [[#ReportService.pick_todos]] · [[#ReportService.pick_clauses]] · [[#ReportService.template_sentences]] · `SentenceWriter.write` · `factcheck.contradicts` · [[JSD-MS-007#CitationService.clear_report]] · [[JSD-MS-007#CitationService.resolve_markers]] · [[JSD-MS-007#CitationService.cite]]

**테스트 관점** 가짜 작성기가 "근저당 3억" 결론 → 템플릿 결론, corrections 1 · 작성기 실패 → 템플릿 문장, `llm_fallback` true · `use_model` false면 작성기 호출 0 · 두 번 쓰면 `revision_no` 2, 인용은 새 판 것만 · 작성기 입력에 개인 이름이 없다 · 인용 cite 중 실패하면 이전 판 의견서와 인용이 그대로다

---

#### ReportService.pick_todos 단계별 할 일 고르기

**시그니처** `pick_todos(inp: ReportInput) -> list[Todo]`

근거: [[JSD-RFQ-001#Q22]] · [[JSD-RFQ-001#Q37]] · [[JSD-DOM-001#Todo]] · [[JSD-UC-001#UC-S8]] 1

**처리**
1. `signals = {s.code}` · `unknowns = {u.code}` · `mortgages` = 살아 있는 mortgage 항목
2. `TODOS`(3장)의 항목마다 `when`을 본다 — 항상 · 건물 종류 · 신호 code · 확인 못 함 code · 보증금 초과 · 살아 있는 근저당
3. 맞는 항목마다 `Todo(stage, title, how, cost, because)` — `because`는 맞게 한 조건의 사람이 읽는 말(신호 label · 확인 못 함 항목 label · "근저당이 있습니다")
4. 정렬 — 단계 순서(before · signing · balance · after), 같은 단계 안에서는 확인 못 함에서 온 것이 먼저, 그다음 `TODOS` 순서

**테스트 관점** 가격 확인 못 함 → 계약 전 첫 할 일이 시세 직접 확인 · 다가구 → 확정일자 부여현황·전입세대확인서 · 아파트 → 위반건축물 확인이 없다 · 보증금 800만 원 → 계약 직후 미납세 열람이 없다

---

#### ReportService.pick_clauses 특약 고르고 빈칸 채우기

**시그니처** `pick_clauses(inp: ReportInput) -> list[SpecialClause]`

근거: [[JSD-RFQ-001#Q23]] · [[JSD-UC-001#UC-S8]] 2 · [[JSD-PRD-001#R9]]

**처리**
1. `CLAUSES`(3장)를 순서대로 보고 `when`이 맞는 것만
2. 빈칸 채우기 — `{deposit}` = fmt(보증금) · `{mortgagee}` = 가장 큰 살아 있는 근저당의 권리자(법인이면 이름, 개인 라벨이면 `근저당권자`) · `{max_amount}` = 그 채권최고액 fmt · `{balance_date}` = `____년 __월 __일`(사용자가 적는다)
3. `SpecialClause(title, body, source, filled = {채운 키: 값})` · 특약마다 근거 항목(근저당 말소 → 그 근저당, 소유권 변경 통지 → 최근 이전 항목)을 순번과 함께 `write`에 넘긴다

**테스트 관점** 다세대 예시 → 표준 1·2·3 + 근저당 말소(화곡새마을금고, 2.1억) + 보증보험 무효 + 소유권 변경 통지 + 미납세 열람 동의 · 채운 값이 `filled`에 있다 · 개인 근저당권자 이름이 들어가지 않는다

---

#### ReportService.template_sentences 모델 없이 만드는 문장

**시그니처** `template_sentences(inp: ReportInput) -> Sentences`

근거: [[JSD-UC-001#UC-S8]] 3a · [[JSD-DOM-002]] 4.8

**처리**
1. 결론 — 등급별 `CONCLUSIONS` 틀에 채운다. 근거 표식은 결정 신호의 `entry_ids`로 단다
   - danger → `보증금 {deposit}을 넣기엔 위험합니다. {첫 결정 항목 label}. {{entry:…}}`
   - caution → `보증금 {deposit}을 넣기 전에 확인할 것이 있습니다. {결정 항목 label 둘까지}. {{entry:…}}`
   - safe → `등기부와 조회 결과로는 큰 위험이 보이지 않습니다. 부채비율 {pct}입니다.`
   - 결정 항목이 `debt_ratio`면 label은 `선순위와 보증금이 주택 가격의 {pct}입니다` · `trade_price`면 `주택 가격을 확인하지 못했습니다`
2. 설명 — 신호마다 `SIGNAL_EXPLANATIONS[code]`
3. 물어볼 것 — 신호·확인 못 함 code마다 `QUESTIONS[code]`를 모아 중복 없이 5개까지, 3개가 안 되면 `QUESTIONS["common"]`으로 채운다
4. `→ Sentences(conclusion, explanations, questions, tokens_in 0, tokens_out 0)`

**테스트 관점** 위험 등급 · 결론에 결정 신호 표식 · 템플릿 문장끼리는 후검증을 통과한다(금액이 입력 값) · 신호 0개 안전 → 물어볼 것 3개

---

#### ReportService.get 의견서와 인용

**시그니처** `get(review_id: str) -> Report`

근거: [[JSD-SEQ-001#SEQ-14]] · [[JSD-API-001#GET/api/reviews/{id}/report]]

**처리**
1. `op = DB: opinions where review_id` · if 없음 → `! not_found`
2. `refs = CitationService.for_report(review_id)`
3. `report = op.body` 사본 · `conclusion.citations` = `used_in conclusion` · `signals[i].citations` = `used_in signal and ref == code` · `checked[i].citations` = `used_in checked and ref == code` — 각각 key 순서
4. `→ report`

**예외** `not_found` 아직 나오지 않음

**테스트 관점** 결론 `{{c1}}`과 `citations[0].key == "c1"` · 신호 인용이 제 신호에 붙는다 · 합산·특약 인용은 여기 붙지 않는다(역방향 조회로만)

---

#### ReportService.exists 의견서가 있는지

**시그니처** `exists(review_id: str) -> bool`

**처리** `DB: exists opinions where review_id`

**테스트 관점** 쓰기 전 false · 쓴 뒤 true

---

#### ReportService.shareable 공유본에 담을 사본

**시그니처** `shareable(review_id: str) -> Shareable`

근거: [[JSD-SEQ-001#SEQ-14]] · [[JSD-UC-001#UC-A4]] 4 · [[JSD-PRD-001#R14]]

**처리**
1. `op = DB: opinions where review_id` · if 없음 → `! not_found`
2. `r = op.body` 사본 — `clauses = []` · `questions_to_ask = []` · 모든 `citations = []` · 결론의 `{{cN}}` 표식을 지운다
3. 결론 · 신호 설명 · 할 일 문장 · `revision_reason`을 `privacy.mask_text(text, [])`로 한 번 더 — 주민번호 형태 숫자·번지·동호수
4. `→ Shareable(report = r, subject = op.subject)`

**예외** `not_found`

**테스트 관점** 결과에 `{{c` 가 없다 · 특약·물어볼 것이 비었다 · 설명에 들어간 `123-4`가 지워진다

---

#### ReportService.delete_for_review 의견서 삭제

**시그니처** `delete_for_review(review_id: str) -> None`

**처리** `DB: delete opinions where review_id`

**테스트 관점** 지운 뒤 `exists` false

---

## 3. catalog.py 상수

문구는 여기 한곳에 출처와 함께 둔다. 문구를 고치면 이 파일만 바뀐다.

**TODOS** — `code` · 단계 · 제목 · 어디서 어떻게 · 비용 · 언제([[JSD-RFQ-001#Q37]])

| code | 단계 | 제목 | 언제 |
|---|---|---|---|
| price_self_check | before | 시세를 직접 확인하세요 (국토부 실거래가·KB시세) | 확인 못 함 trade_price |
| illegal_building_check | before | 정부24 건축물대장에서 위반건축물 표시를 확인하세요 | 확인 못 함 illegal_building |
| land_registry_check | before | 토지 등기부를 발급해 근저당을 확인하세요 | 확인 못 함 land_registry |
| defaulter_app_check | before | 안심전세앱에서 임대인을 확인하세요 | 확인 못 함 defaulter_list |
| proxy_documents | before | 위임장과 인감증명서(본인발급·3개월 이내)를 확인하세요 | 신호 owner_mismatch |
| trust_documents | before | 신탁원부와 수탁자 동의서를 확인하세요 | 신호 trust |
| fixed_date_status | before | 임대인 동의를 받아 확정일자 부여현황을 열람하세요 | multi_household |
| move_in_households | before | 전입세대확인서를 발급해 기존 세입자를 확인하세요 | multi_household |
| tax_arrears_consent | before | 임대인 동의로 국세·지방세 미납을 열람하세요 | 항상 |
| agent_check | before | 브이월드에서 중개사 등록과 공제증서를 확인하세요 | 항상 |
| id_account_match | signing | 신분증·등기부 소유자·입금 계좌 명의가 같은지 대조하세요 | 항상 |
| clauses_in_contract | signing | 아래 특약을 계약서에 넣으세요 | 항상 |
| tax_after_contract | signing | 계약 직후 동의 없이 미납세를 열람하세요 | 보증금 1,000만 원 초과 |
| lease_report | signing | 30일 안에 임대차 신고를 하세요 | 보증금 6,000만 원 초과 |
| registry_reissue | balance | 잔금 직전 등기부를 다시 떼어 새 항목이 없는지 보세요 | 항상 |
| mortgage_cancel_check | balance | 근저당 말소 접수증을 받고 을구 말소를 확인하세요 | 살아 있는 근저당 |
| move_in_same_day | balance | 잔금 당일 전입신고와 확정일자를 받으세요 (대항력은 다음 날 0시) | 항상 |
| guarantee_insurance | after | 계약기간 절반이 지나기 전 전세보증금반환보증에 가입하세요 | 항상 |
| registry_watch | after | 안심전세앱 등기 변동 알림을 켜세요 | 항상 |
| keep_residence | after | 주민등록과 점유를 유지하고, 증액하면 확정일자를 다시 받으세요 | 항상 |

**CLAUSES** — 순번 · 제목 · 본문 틀 · 출처 · 언제([[JSD-RFQ-001#Q23]]). 1~3은 법무부·국토부 주택임대차표준계약서(2023-10-06) 특약 원문

| 순번 | 제목 | 언제 |
|---|---|---|
| 1 | 담보권 설정 금지 | 항상 |
| 2 | 위반 시 계약 해제 | 항상 |
| 3 | 미고지 선순위·체납 확인 시 해제 | multi_household 또는 tax_arrears가 확인됨이 아님(지금은 늘 해당) |
| 4 | 잔금일 근저당 말소 조건 (`{mortgagee}` 채권최고액 `{max_amount}`) | 살아 있는 근저당 |
| 5 | 보증보험 가입 불가 시 무효 | 등급이 safe가 아님 또는 부채비율 없음 |
| 6 | 소유권 변경 즉시 통지 | 신호 frequent_transfer 또는 corporate_landlord |
| 7 | 미납세 열람 동의 | 보증금 1,000만 원 초과 |

**CONCLUSIONS** — 등급별 결론 틀(2장 template_sentences 1). **SIGNAL_EXPLANATIONS** — 신호 code마다 쉬운 설명 한두 문장과 어느 기관 기준인지. **QUESTIONS** — 신호·확인 못 함 code마다 집주인·중개사에게 물을 문장, `common` 3개. **NOTICES** — AI가 만든 결과이며 법률 자문이 아니라는 것, 전문가 확인 권고, 판정 기준 출처, 원문·대화·의견서는 24시간 뒤 지워진다는 것.

---

## 4. 미결사항

- [ ] 특약 1~3 원문 문구를 표준계약서에서 그대로 옮겨 적는다 — 문구 저작 확인
- [ ] 할 일의 비용 칸(열람 수수료 등) 실제 금액을 기관 안내로 확인한다
- [ ] 월세 계약의 임대차 신고 조건(월세 30만 원 초과)은 월세 금액을 받지 않아 보증금 조건만 본다
- [ ] 특약 3의 "체납 미확인"은 체납을 확인하는 수단이 없어 늘 참이다 — 늘 넣을지 조건을 뺄지
