---
doc_id: JSD-MS-001
type: MS
title: 보증금지킴 — 미니스펙 ReviewService
status: draft
upstream: [JSD-DOM-002, JSD-SEQ-001, JSD-API-001, JSD-API-002, JSD-DOM-003]
---

# MINISPEC — ReviewService

## 0. 이 문서가 다루는 것

`review/service.py`의 함수 22개. 클래스 명세 [[JSD-DOM-002#ReviewService]](4.1)의 시그니처를 함수 안쪽까지 내린 것이다. **MS 문서 하나 = 클래스 명세 4장 절 하나 = 코드 파일 하나** — 이 파일을 짤 때 이 문서를 본다. 에이전트 루프(`review/service_agent.py`, 4.2)는 다음 문서다.

형식은 시그니처·근거·입력·처리·출력·예외·호출하는 것·테스트 관점이다. 처리가 몇 줄이면 간략형으로 시그니처·처리·테스트만 둔다. 내부 타입(`ReviewFacts` `UserInput` `Accepted` …)은 [[JSD-DOM-002]] 2.8, 열거형은 2.9, 테이블과 컬럼은 [[JSD-DOM-003]]이다.

**표기** — `→` 반환·결과, `!` 예외(`AppError` 코드), `DB:` 자기 테이블 접근, `if 조건 → 결과 · else → 결과` 분기, `·` 같은 단계 안 구분. `LIMITS`·`PRICES`는 `core/config.py` 상수다.

**이 파일이 지키는 것**
- 자기 테이블은 `reviews` `review_records` `questions` `follow_up_turns` `usage_logs` 다섯이다. 다른 도메인의 행은 그 서비스를 불러서만 만진다([[JSD-DOM-002]] 3.2)
- **트랜잭션 경계는 이 파일이 정한다.** 업스테이지·모델을 기다리는 동안 트랜잭션과 세션을 붙들지 않는다. 루프가 부르는 함수는 부를 때마다 짧은 세션을 연다([[JSD-DOM-002]] 6장)
- 사용자 문장과 에이전트 문장은 저장 전에 가린다. 이름 목록은 `RegistryService.holder_names`와 `reviews.counterparty_name`이다. 이름은 이 파일 밖으로 내보내지 않는다
- 예외 문자열을 로그·`Error.detail`에 쓰지 않는다. 로그에는 `review_id`와 코드만 남긴다

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#ReviewService.create]] | 업로드를 검사·파싱하고 검토를 만든다 |
| [[#ReviewService.parse_upload]] | 파싱 캐시를 보고 없으면 업스테이지로 파싱 |
| [[#ReviewService.get]] | 상단 바 요약과 진행 수치 |
| [[#ReviewService.cancel]] | 검토와 딸린 것을 즉시 지운다 |
| [[#ReviewService.list_messages]] | 대화 한 쪽 |
| [[#ReviewService.stream]] | 대화 스트림 이벤트 |
| [[#ReviewService.receive]] | 답변·되묻기·서류 추가를 받는다 |
| [[#ReviewService.override_values]] | 시세·금액 직접 입력으로 다시 판정 |
| [[#ReviewService.ask]] | 질문을 내고 답을 기다린다 |
| [[#ReviewService.record]] | 대화 메시지 하나를 쌓는다 |
| [[#ReviewService.owner_matches]] | 소유자와 계약 상대방이 같은지 |
| [[#ReviewService.summarize_and_store]] | 합산을 내고 facts에 둔다 |
| [[#ReviewService.check_and_store]] | 합산을 다시 낸 뒤 신호·등급을 facts에 둔다 |
| [[#ReviewService.write_report]] | 합산·신호·의견서를 다시 내고 카드를 남긴다 |
| [[#ReviewService.finish]] | 상태를 닫고 사용량을 갱신 |
| [[#ReviewService.require_live]] | 검토 경로의 404·410 판정 |
| [[#ReviewService.rights_input]] | 합산 입력 채우기 |
| [[#ReviewService.signal_input]] | 신호 입력 채우기 |
| [[#ReviewService.report_input]] | 의견서 입력 채우기 |
| [[#ReviewService.purge_expired]] | 보관 기간이 지난 검토를 비운다 |
| [[#ReviewService.warm_samples]] | 예시 3건의 파싱 캐시를 채운다 |
| [[#ReviewService.usage_report]] | 하루치 사용량 요약 |

---

## 2. 함수

#### ReviewService.create 업로드를 검사·파싱하고 검토를 만든다

**시그니처** `create(upload: Upload | None, sample_id: str | None, deposit_manwon: int, contract_type: ContractType, counterparty_name: str | None, client_ip: str) -> ReviewCreated`

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-API-001#POST/api/reviews]] · [[JSD-UC-001#UC-A1]] 1~3 · [[JSD-UC-001#UC-S10]] · [[JSD-DOM-002]] 5장 결정 1·3

**입력** 라우터가 폼에서 읽은 값. `upload`는 메모리의 바이트다. `client_ip`는 프록시 헤더를 반영한 원문 IP이고 이 함수 밖으로 원문이 나가지 않는다

**처리**
1. if `upload`와 `sample_id`가 둘 다 None이거나 둘 다 있음 → `! missing_input(field file)` · if `deposit_manwon < 1` → `! missing_input(field deposit_manwon)`
2. `is_sample = sample_id is not None` · if `is_sample` → `upload = SampleService.file(sample_id)` (없는 ID면 거기서 `! missing_input`)
3. `check = gate.check_file(upload)` — `! invalid_file`은 그대로 올린다
4. `gate.take_quota(client_ip, check.file_sha256, is_sample, today)` — `! rate_limited`. **트랜잭션 밖, 한 문장**
5. `parsed, from_cache = parse_upload(upload, check, is_sample)` — `! parse_failed`는 그대로. 여기까지 DB 트랜잭션을 열지 않는다
6. 짧은 트랜잭션 하나를 연다
   1. `DB: reviews insert` — `status created`, `deposit_manwon`, `contract_type`, `counterparty_name`(앞뒤 공백 제거, 빈 문자열이면 null), `sample_id`, `facts {}`, `parsed_pages = parsed.billed_pages`, `cost_krw = parsed.billed_pages × PRICES.parse_page_krw`, `expires_at = now + LIMITS.retention_hours`
   2. `RegistryService.create_extract(review_id, parsed.html, parsed.page_count, check.file_sha256)` · if `! not_registry` → 롤백 → `! not_registry`. 검토도 캐시도 생기지 않는다
   3. if not `from_cache` → `gate.remember_html(check.file_sha256, parsed.html, parsed.page_count, is_sample)`
   4. 커밋
7. `upload`를 참조하는 변수를 모두 놓는다. 바이트는 이 함수가 끝나면 버려진다
8. `→ ReviewCreated(review_id, status created, is_sample, expires_at)`. 루프는 라우터가 응답 뒤에 띄운다

**출력** `ReviewCreated`

**예외**

| 조건 | 에러 |
|---|---|
| 파일·예시 둘 다 없음·둘 다 있음, 보증금 1 미만 | `missing_input` |
| 형식·크기·쪽수·암호 | `invalid_file` |
| IP 하루 한도 | `rate_limited` |
| 업스테이지 재시도 뒤 실패 | `parse_failed` |
| 갑구·을구가 없음 | `not_registry` |

**호출하는 것** `SampleService.file` · `gate.check_file` · `gate.take_quota` · [[#ReviewService.parse_upload]] · `RegistryService.create_extract` · `gate.remember_html`

**테스트 관점** 예시 ID로 시작 → `is_sample` true, 한도 행이 늘지 않는다 · 같은 파일 두 번째 → 업스테이지 가짜가 불리지 않고 `parsed_pages` 0 · 등기부가 아닌 PDF → 400, `reviews`·`file_caches` 행이 모두 없다 · 파싱 실패 → 502, 행 없음 · 한도 6번째 → 429 · 파서가 부르는 동안 DB 세션이 열려 있지 않다(가짜 파서 안에서 확인)

---

#### ReviewService.parse_upload 파싱 캐시를 보고 없으면 업스테이지로 파싱

**시그니처** `parse_upload(upload: Upload, check: FileCheck, is_sample: bool) -> tuple[ParsedDocument, bool]`

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-DOM-002]] 5장 결정 3

**처리**
1. `cached = gate.cached_html(check.file_sha256)` · if `cached` → `→ (cached, True)` (`billed_pages` 0)
2. else → `parsed = RegistryService.parse(upload.data, check.media_type)` → `→ (parsed, False)`
3. 캐시에 넣지 않는다. 부른 쪽이 `create_extract`가 성공한 트랜잭션에서 넣는다. 트랜잭션 밖에서만 부른다

**테스트 관점** 캐시 적중이면 파서 호출 0 · 캐시 없으면 파서 1회, `file_caches`에 아직 행이 없다

---

#### ReviewService.get 상단 바 요약과 진행 수치

**시그니처** `get(review_id: str) -> ReviewView`

근거: [[JSD-SEQ-001#SEQ-12]] · [[JSD-API-001#GET/api/reviews/{id}]]

**처리**
1. `review = DB: reviews where id` · if 없음 → `! not_found` · if `status expired` → `! gone`
2. `prop = RegistryService.property(review_id)` · `docs = RegistryService.list(review_id)` · `has_report = ReportService.exists(review_id)`
3. `DB: questions` 수 → `questions_asked` · `status pending`인 가장 최근 행 → `pending_question`(Question DTO) · `DB: follow_up_turns` 수 → `asks_used`
4. `elapsed_sec = (finished_at or now) − created_at`
5. `→ ReviewView` — `subject {building_type: prop.building_type, deposit_manwon, contract_type, region: prop.region}`, `counters {tool_calls, questions_asked, asks_used, elapsed_sec, cost_krw}`, `documents`는 `page_count`를 뺀 목록, `has_report`, `expires_at`

**예외** `not_found` 행 없음 · `gone` expired

**테스트 관점** 응답 어디에도 `counterparty_name`이 없다 · pending 질문이 둘이면(있어서는 안 되지만) 최근 것 · expired → 410

---

#### ReviewService.cancel 검토와 딸린 것을 즉시 지운다

**시그니처** `cancel(review_id: str) -> None`

근거: [[JSD-SEQ-001#SEQ-15]] · [[JSD-API-001#DELETE/api/reviews/{id}]] · [[JSD-DOM-002]] 5장 결정 4

**처리**
1. `review = DB: reviews where id for update` · if 없음 → `! not_found` · if `status expired` → `! gone`. 남긴 행을 지우지 않는다
2. 같은 트랜잭션에서
   1. `hashes = RegistryService.delete_for_review(review_id)`
   2. 해시마다 `gate.forget(hash)` — 예시 캐시는 `forget`이 남긴다
   3. `CitationService.delete_for_review(review_id)` · `ReportService.delete_for_review(review_id)`
   4. `DB: review_records · questions · follow_up_turns delete where review_id` → `DB: reviews delete`
3. 커밋. `usage_logs`는 건드리지 않는다
4. 도는 루프에는 알리지 않는다. 루프가 다음 확인이나 다음 쓰기에서 행이 없는 것을 보고 멈춘다([[#ReviewService.record]] · [[#ReviewService.ask]])

**예외** `not_found` 행 없음 · `gone` expired

**테스트 관점** 지운 뒤 `registry_extracts`·`citations`·`opinions`·`file_caches`(그 해시, 예시 아님)가 모두 0행 · `usage_logs` 행은 남는다 · 예시 파일 캐시는 남는다 · expired 검토 → 410이고 행이 남는다 · `shared_opinions`는 남는다

---

#### ReviewService.list_messages 대화 한 쪽

**시그니처** `list_messages(review_id: str, after_seq: int = 0, limit: int = 200) -> MessagesPage`

근거: [[JSD-SEQ-001#SEQ-11]] · [[JSD-API-001#GET/api/reviews/{id}/messages]]

**처리**
1. `review = DB: reviews where id` · if 없음 → `! not_found` · if expired → `! gone`
2. `limit = min(max(limit, 1), 200)` · `rows = DB: review_records where review_id and seq > after_seq order by seq limit`
3. `cites = CitationService.for_messages(review_id, [row.id])`
4. 행마다 `Message(message_id=row.id, seq, role, kind, text, citations=cites.get(row.id, []), data, created_at)`
5. `→ MessagesPage(messages, next_seq = 마지막 seq 또는 after_seq, status = review.status)`

**테스트 관점** `after_seq`가 마지막 seq면 빈 목록, `next_seq`는 그대로 · 인용이 없는 메시지는 빈 목록 · `limit` 500 → 200

---

#### ReviewService.stream 대화 스트림 이벤트

**시그니처** `stream(review_id: str, last_seq: int = 0) -> AsyncIterator[StreamEvent]`

근거: [[JSD-SEQ-001#SEQ-11]] · [[JSD-API-001#GET/api/reviews/{id}/stream]] · [[JSD-INFRA-001#C4]]

**입력** `last_seq`는 `Last-Event-ID` 헤더 값. 없으면 0

**처리** — 제너레이터. 주기마다 짧은 세션을 연다
1. 첫 확인: `DB: reviews where id` · if 없음 → `! not_found` · if expired → `! gone`. 여기까지는 응답 헤더 전이라 HTTP 에러로 나간다
2. `prev_state = None` · 반복(1초마다)
   1. `page = list_messages(review_id, last_seq, 200)` · 메시지마다 `yield StreamEvent(event message, id = seq, data = Message)` · `last_seq` 갱신
   2. `state = {status, counters, pending_question}` — [[#ReviewService.get]]의 3~4단계와 같은 값 · if `state != prev_state` → `yield StreamEvent(event state, data = state)` · `prev_state = state`
   3. if 행이 사라짐(삭제) → `yield StreamEvent(event error, data = Error(not_found))` → 끝
   4. if `status in (done, failed, expired)` and `DB: follow_up_turns where status running` 없음 and 1에서 새 메시지가 없음 → `yield StreamEvent(event done)` → 끝
3. `delta`는 보내지 않는다

**출력** `StreamEvent` 이어짐. 이벤트 `id`는 message일 때만

**테스트 관점** `last_seq` 5로 붙으면 6부터 · 끝난 검토에 붙으면 남은 메시지 → state → done 순서 · 스트림 도중 삭제 → error 뒤 끝 · 열린 되묻기 차례가 있으면 done을 보내지 않는다

---

#### ReviewService.receive 답변·되묻기·서류 추가를 받는다

**시그니처** `receive(review_id: str, user_input: UserInput) -> Accepted`

근거: [[JSD-SEQ-001#SEQ-7]] · [[JSD-SEQ-001#SEQ-9]] · [[JSD-API-001#POST/api/reviews/{id}/messages]] · [[JSD-UC-001#UC-A3]] · [[JSD-DOM-002]] 5장 결정 10

**입력** `kind` answer면 `question_id`와 `choice`·`text`·`file` 중 하나. `kind` ask면 `text`나 `file` 중 하나 이상

**처리**
1. `review = DB: reviews where id` · if 없음 → `! not_found` · if expired → `! gone`
2. 입력 검사 · if answer이고 `question_id` 없음 → `! missing_input(field question_id)` · if answer이고 `choice`·`text`·`file` 모두 없음 → `! missing_input(field text)` · if ask이고 `text`·`file` 모두 없음 → `! missing_input(field text)`
3. 상태 검사
   - answer: `q = DB: questions where id = question_id and review_id` · if 없거나 `q.status != pending` → `! wrong_state`
   - ask: if not `ReportService.exists(review_id)` → `! wrong_state` · if `DB: follow_up_turns where review_id and status running` 있음 → `! wrong_state` · if `LIMITS.asks`가 있고 차례 수 ≥ `LIMITS.asks` → `! ask_limit` · if `review.llm_cost_krw ≥ LIMITS.cost_krw` → `! ask_limit`
4. if `file` → `check = gate.check_file(file)` → `parsed, from_cache = parse_upload(file, check, False)`. 트랜잭션 밖
5. `names = RegistryService.holder_names(review_id) + [counterparty_name]` · `masked = privacy.mask_text(text, names)` (text가 있을 때)
6. 짧은 트랜잭션 하나
   1. if `file` → `doc = RegistryService.create_extract(review_id, parsed.html, parsed.page_count, check.file_sha256)` · if `! not_registry` → 롤백 → `! not_registry` · if not `from_cache` → `gate.remember_html(...)` · `DB: reviews parsed_pages += billed_pages, cost_krw += billed_pages × PRICES.parse_page_krw`
   2. answer: `answer = 답 값`(아래) → `DB: questions set status answered, answer, answered_at now, answer_document_id = doc.id` → `message_id = record(user, answer, masked 또는 선택지 라벨, AnswerData(question_id, choice, text=masked, document_id))`
   3. ask: `turn_id = DB: follow_up_turns insert (running, document_id = doc.id)` — 부분 unique 위반이면 롤백 → `! wrong_state` → `message_id = record(user, say, masked 또는 "서류를 올렸습니다", None, turn_id)`
   4. 커밋
7. `→ Accepted(message_id, seq, turn_id)` — answer면 `turn_id` None. 기다리던 `ask`가 행을 다시 읽어 가져간다

**답 값** — `q.kind`가 illegal_building · proxy · owner_type이면 `choice`를 고정 선택지 표(라벨 → 열거형 값, [[JSD-PRD-001#R8]])로 바꾼다. 표에 없는 `choice` → `! missing_input(field choice)`. 모름 → `unknown`. 그 밖의 종류는 `choice` 또는 `masked`. 파일 답이면 `"file"`

**예외**

| 조건 | 에러 |
|---|---|
| 입력 없음, 고정 선택지 밖 | `missing_input` |
| 파일 형식 | `invalid_file` |
| 파싱 실패 | `parse_failed` |
| 등기부 아님 | `not_registry` |
| pending이 아닌 질문, 의견서 전 되묻기, 열린 차례 | `wrong_state` |
| 되묻기 한도·비용 한도 | `ask_limit` |

**호출하는 것** `ReportService.exists` · `gate.check_file` · [[#ReviewService.parse_upload]] · `RegistryService.create_extract` · `RegistryService.holder_names` · `gate.remember_html` · `privacy.mask_text` · [[#ReviewService.record]]

**테스트 관점** 대리 질문에 "대리인(위임장 있음)" → `answer = proxy_with_poa` · 이미 timeout인 질문에 답 → 409 · 되묻기 동시 두 요청 → 하나는 202, 하나는 409(부분 unique) · 토지 등기부 파일 답 → 문서 2개, `answer_document_id` 채움 · 되묻기 문장에 소유자 이름 → 저장된 text에 라벨 · 파일이 등기부가 아니면 질문이 pending 그대로

---

#### ReviewService.override_values 시세·금액 직접 입력으로 다시 판정

**시그니처** `override_values(review_id: str, overrides: ValueOverrides) -> Report`

근거: [[JSD-SEQ-001#SEQ-10]] · [[JSD-API-001#PATCH/api/reviews/{id}/values]] · [[JSD-UC-001#UC-A1]] 8a

**처리**
1. `review = DB: reviews where id` · if 없음 → `! not_found` · if expired → `! gone`
2. if `review.status != done` → `! wrong_state` · if 열린 차례 있음 → `! wrong_state`
3. if `price_manwon`도 `entries`도 없음 → `! missing_input(field price_manwon)` · if `price_manwon < 1` → `! missing_input(field price_manwon)`
4. if `entries` → `known = RegistryService.entries(review_id, [e.entry_id])` · if 모르는 ID가 하나라도 있음 → `! missing_input(field entries)`
5. `DB: reviews facts.overrides` — 이전 값에 덮어 합친다(`price_manwon`은 새 값, `entries`는 `entry_id`별로 새 값)
6. `record(user, say, "직접 입력: " + money.format_manwon 목록)` — 금액만 쓰고 이름은 넣지 않는다
7. `write_report(review_id, None, "직접 입력")` — 새 의견서 카드까지 남긴다
8. `→ ReportService.get(review_id)`

**예외** `not_found` 행 없음 · `gone` 만료 · `missing_input` 값 없음, 모르는 entry_id · `wrong_state` done 아님, 열린 차례

**테스트 관점** 가격 5억 입력 → `price_source user_input`, 부채비율 갱신, `revision_no` 1 오름, report 메시지 1개 추가 · 모르는 `entry_id` → 400, facts 그대로 · 두 번 입력하면 뒤 값 · LLM 비용 한도에 닿았으면 `llm_fallback` true

---

#### ReviewService.ask 질문을 내고 답을 기다린다

**시그니처** `ask(review_id: str, args: AskArgs) -> AskAnswer`

근거: [[JSD-SEQ-001#SEQ-7]] · [[JSD-API-002#ask_user]] · [[JSD-UC-001#UC-S7]] · [[JSD-UC-001#UC-A3]] 2a·2c·3a

**처리**
1. 짧은 트랜잭션
   1. `n = DB: questions count where review_id` · if `n ≥ LIMITS.questions` → `! question_limit`
   2. if `args.kind in (illegal_building, proxy, owner_type)` → `options = 고정 선택지 라벨`, `input_type choice` · `help_url`은 illegal_building이면 정부24 확인 방법
   3. `qid = DB: questions insert (asked_no n+1, kind, text, why, input_type, options, help_url, pending)`
   4. `record(agent, question, args.text, Question DTO)` · `DB: reviews status waiting_user`
2. 반복 — 1초마다 새 세션으로 `q = DB: questions where id = qid`
   - if `q` 없음 → `! not_found` (검토 삭제. 루프가 조용히 멈춘다)
   - if `q.status answered` → 3
   - if 경과 ≥ `LIMITS.answer_timeout_sec` → `DB: questions set status timeout, answer unknown` · `record(system, notice, "답변 없이 진행합니다", NoticeData(answer_timeout))` → 3
3. `DB: reviews status running` → `→ AskAnswer(qid, q.answer, q.answer_document_id)`

**예외** `question_limit` 질문 5개 · `not_found` 기다리는 중 삭제

**테스트 관점** 여섯 번째 질문 → question_limit, 행 없음 · 답이 오면 1초 안에 돌아온다 · 시간 가짜로 300초 → `unknown`, notice 1개 · 기다리는 중 `cancel` → 300초를 기다리지 않고 not_found · 기다리는 동안 DB 세션이 열려 있지 않다

---

#### ReviewService.record 대화 메시지 하나를 쌓는다

**시그니처** `record(review_id: str, role: Role, kind: MessageKind, text: str, data: dict | None = None, turn_id: int | None = None, message_id: str | None = None) -> str`

근거: [[JSD-SEQ-001#SEQ-3]] · [[JSD-DOM-003]] 4장 2

**처리** — 부른 쪽 트랜잭션이 있으면 그 안, 없으면 짧은 트랜잭션
1. `DB: reviews where id for update` · if 없음 → `! not_found`. 행 잠금이 같은 검토의 `seq` 쓰기를 한 줄로 세운다 — 루프와 `receive`가 동시에 쌓아도 seq가 겹치지 않는다
2. if `role in (agent, user)` → `text = privacy.mask_text(text, holder_names + [counterparty_name])`
3. `seq = DB: max(seq) where review_id` + 1 (없으면 1)
4. `DB: review_records insert (id = message_id 또는 새 uuid, seq, role, kind, text, data, turn_id)`
5. `→ id`

**테스트 관점** 두 코루틴이 동시에 100개씩 → seq 1~200 빈틈·중복 없음 · 미리 정한 `message_id`로 쌓인다 · 지워진 검토 → not_found · 에이전트 문장 속 이름이 라벨로 바뀐다

---

#### ReviewService.owner_matches 소유자와 계약 상대방이 같은지

**시그니처** `owner_matches(review_id: str) -> bool | None`

근거: [[JSD-SEQ-001#SEQ-4]] · [[JSD-API-002]] 1.3

**처리** `owner = RegistryService.owner(review_id)` · `name = DB: reviews.counterparty_name` · if 둘 중 하나 없음 → `None` · else → 공백을 모두 뺀 두 문자열이 같으면 `True`, 아니면 `False`. 이름은 반환하지 않는다

**테스트 관점** "홍 길동" · "홍길동" → True · 상대방 이름 없음 → None · 소유자가 법인이고 상대방이 개인 → False

---

#### ReviewService.summarize_and_store 합산을 내고 facts에 둔다

**시그니처** `summarize_and_store(review_id: str) -> RightsSummary`

근거: [[JSD-SEQ-001#SEQ-5]] · [[JSD-API-002#summarize_rights]] · [[JSD-UC-001#UC-S2]]

**처리** `inp = rights_input(review_id)` → `rights = RulesService.summarize(inp)` → 짧은 트랜잭션 `DB: reviews facts.rights = rights` → `→ rights`. numbers 메시지는 루프가 남긴다

**테스트 관점** 직접 입력 가격이 있으면 실거래가보다 앞선다(`rules` 순서) · 같은 facts면 같은 결과

---

#### ReviewService.check_and_store 합산을 다시 낸 뒤 신호·등급을 facts에 둔다

**시그니처** `check_and_store(review_id: str) -> SignalCheck`

근거: [[JSD-SEQ-001#SEQ-5]] · [[JSD-API-002#check_signals]] · [[JSD-UC-001#UC-S3]]

**처리**
1. `summarize_and_store(review_id)` — 합산 전이거나 합산 뒤 시세·답이 바뀌었어도 신호가 옛 합산에 기대지 않는다
2. `inp = signal_input(review_id)` → `check = RulesService.check(inp)`
3. 짧은 트랜잭션 `DB: reviews facts.check = check`
4. `→ check`

**테스트 관점** summarize를 부른 적 없이 불러도 `rights`가 채워진다 · 합산 뒤 시세가 facts에 들어오면 부채비율 신호가 새 가격으로 나온다

---

#### ReviewService.write_report 합산·신호·의견서를 다시 내고 카드를 남긴다

**시그니처** `write_report(review_id: str, agent_notes: str | None, revision_reason: str | None) -> ReportResult`

근거: [[JSD-SEQ-001#SEQ-8]] · [[JSD-API-002#write_report]] · [[JSD-UC-001#UC-S8]] · [[JSD-UC-001#UC-A1]] 6~7

**처리**
1. `names = holder_names + [counterparty_name]` · `agent_notes = mask_text(agent_notes, names)` · `revision_reason = mask_text(revision_reason, names)` (있을 때)
2. `check_and_store(review_id)` — 합산을 포함한다
3. `inp = report_input(review_id)`
4. `result = ReportService.write(review_id, inp, agent_notes, revision_reason)` — 문장 생성은 그 안에서 트랜잭션 밖, 인용·의견서 덮기는 한 트랜잭션
5. 짧은 트랜잭션
   1. `llm_krw = infra.openai.usage_krw(result.tokens_in, result.tokens_out)`
   2. `DB: reviews corrections += result.corrections, tokens_in += result.tokens_in, tokens_out += result.tokens_out, llm_cost_krw += llm_krw, cost_krw += llm_krw`
   3. `record(agent, report, "", ReportCard(grade, signal_count, unknown_count, rule_version, revision_no, revision_reason))`
6. `→ result`

**출력** `ReportResult`. 루프는 요약만 모델에 돌려준다

**호출하는 것** [[#ReviewService.check_and_store]] · [[#ReviewService.report_input]] · `ReportService.write` · `infra.openai.usage_krw` · [[#ReviewService.record]] · `privacy.mask_text`

**테스트 관점** 첫 호출 → `revision_no` 1, report 메시지 1개 · 다시 부르면 `revision_no` 2, 메시지 2개 · 가짜 문장 생성기가 토큰 100을 돌려주면 `llm_cost_krw`가 그만큼 오른다 · `revision_reason` 속 이름이 라벨로 저장된다

---

#### ReviewService.finish 상태를 닫고 사용량을 갱신

**시그니처** `finish(review_id: str, status: ReviewStatus) -> None`

근거: [[JSD-SEQ-001#SEQ-2]] · [[JSD-SEQ-001#SEQ-9]] · [[JSD-INFRA-001#C3]]

**처리** — 짧은 트랜잭션
1. `review = DB: reviews where id for update` · if 없음 → 아무것도 하지 않고 끝(삭제된 검토)
2. `DB: reviews set status, finished_at now` — 되묻기 차례 끝이면 `status`는 done 그대로
3. `llm_fallback = ReportService.get(review_id).llm_fallback` if `ReportService.exists` else False
4. `DB: usage_logs upsert on conflict (review_id)` — `is_sample = review.sample_id is not None`, `status`, `tool_calls`, `tokens_in`, `tokens_out`, `parsed_pages`, `cost_krw`, `corrections`, `llm_fallback`, `updated_at now`

**테스트 관점** 두 번 불러도 `usage_logs` 한 행 · 지워진 검토 → 예외 없이 끝 · failed로 닫으면 usage에도 failed

---

#### ReviewService.require_live 검토 경로의 404·410 판정

**시그니처** `require_live(review_id: str) -> None`

근거: [[JSD-SEQ-001#SEQ-C2]] · [[JSD-DOM-002]] 5장 결정 7

**처리** `DB: reviews.status where id` · if 없음 → `! not_found` · if expired → `! gone` · else → 통과. `main.py`가 registry·citation·report·share 검토 경로 라우터에 의존성으로 건다

**테스트 관점** 없는 ID로 원문 보기 → 404 · 만료 검토의 인용 역조회 → 410 · 공유본 보기에는 걸리지 않는다

---

#### ReviewService.rights_input 합산 입력 채우기

**시그니처** `rights_input(review_id: str) -> RightsInput`

근거: [[JSD-API-002]] 1.2 · [[JSD-DOM-002]] 2.8 RightsInput

**처리**
1. `review = DB: reviews` · `facts = ReviewFacts(review.facts)`
2. `entries = RegistryService.entries(review_id)` · `labels = privacy.person_labels(RegistryService.holder_names(review_id))`
3. 항목마다 `EntryFact` — `holder`는 법인이면 그대로, 아니면 `labels[holder]`
4. `prop = RegistryService.property(review_id)`
5. `→ RightsInput(entries, deposit_manwon, building_type = prop.building_type, region = prop.region, override_price_manwon = facts.overrides.price_manwon, trade_price_manwon = facts.price.price_manwon, user_price_manwon = facts.stated.price_manwon, other_tenants_manwon = facts.stated.other_tenants_manwon 또는 tenants 답에서 뽑은 금액, vacant_rooms = facts.stated.vacant_rooms, amount_overrides = facts.overrides.entries를 dict로, today)`

**테스트 관점** 항목의 개인 이름이 라벨로 바뀐다 · facts가 비었으면 가격 후보 셋이 모두 None · tenants 답 "보증금 합계 1억 2천" → `other_tenants_manwon` 12000

---

#### ReviewService.signal_input 신호 입력 채우기

**시그니처** `signal_input(review_id: str) -> SignalInput`

근거: [[JSD-API-002#check_signals]] · [[JSD-DOM-002]] 2.8 SignalInput

**처리**
1. `facts` · `entries`(가린 `EntryFact`, rights_input 2~3과 같다) · `prop = RegistryService.property` → `PropertyFact`
2. `answers = facts.answers` · `proxy_status = ProxyStatus(answers.proxy)` · `illegal_building = IllegalBuilding(answers.illegal_building)` · `owner_type = OwnerType(answers.owner_type)` — 답이 없으면 각각 `unknown`
3. `→ SignalInput(entries, property, rights = facts.rights, owner_matches_counterparty = owner_matches(review_id), proxy_status, illegal_building, owner_type, ledger_main_use = facts.building.main_use, defaulter_matched = facts.defaulter.matched, tenants_answered = "tenants" in answers, failures = facts.failures의 도구 이름 목록, untried = facts.untried, today)`

**테스트 관점** 대리 질문을 안 했으면 `proxy_status unknown` · `facts.rights`는 [[#ReviewService.check_and_store]]가 먼저 채워 None이 아니다

---

#### ReviewService.report_input 의견서 입력 채우기

**시그니처** `report_input(review_id: str) -> ReportInput`

근거: [[JSD-API-002#write_report]] · [[JSD-PRD-001#R10]]

**처리** `facts` · `prop = RegistryService.property`에서 내부 필드(`lot_address` `exclusive_area_m2` `building_name`)를 뺀 사본 · `entries = RegistryService.entries`에서 개인 `holder`를 라벨로 바꾼 사본 → `→ ReportInput(rights = facts.rights, check = facts.check, property, deposit_manwon, contract_type, answers = facts.answers, entries, use_model = review.llm_cost_krw < LIMITS.cost_krw)`

**테스트 관점** 개인 이름이 입력 어디에도 없다 · `llm_cost_krw`가 한도와 같으면 `use_model` false

---

#### ReviewService.purge_expired 보관 기간이 지난 검토를 비운다

**시그니처** `purge_expired(now: datetime) -> int`

근거: [[JSD-SEQ-001#SEQ-16]] · [[JSD-UC-001#UC-A1]] 9 · [[JSD-DOM-002]] 5장 결정 4

**처리**
1. `ids = DB: reviews.id where expires_at < now and status != expired`
2. id마다 트랜잭션 하나 — 하나가 실패해도 다음으로 간다(로그에 id와 코드만)
   1. `hashes = RegistryService.delete_for_review(id)` · 해시마다 `gate.forget` · `CitationService.delete_for_review(id)` · `ReportService.delete_for_review(id)`
   2. `DB: review_records · questions · follow_up_turns delete where review_id`
   3. `DB: reviews set counterparty_name null, facts {}, status expired`
3. `→` 비운 검토 수

**테스트 관점** 25시간 지난 검토 → 딸린 행 0, `reviews` 행은 expired로 남는다 · 같은 시각에 두 번 돌려도 두 번째는 0 · 23시간 된 검토는 그대로

---

#### ReviewService.warm_samples 예시 3건의 파싱 캐시를 채운다

**시그니처** `warm_samples() -> int`

근거: [[JSD-SEQ-001#SEQ-18]] · [[JSD-UC-001#UC-A2]] 4a

**처리** `SampleService.list()`의 예시마다 `upload = SampleService.file(id)` → `check = gate.check_file(upload)` → if `gate.cached_html(check.file_sha256)` 없음 → `parsed = RegistryService.parse(upload.data, check.media_type)` · else → 캐시 값 → `gate.remember_html(hash, html, page_count, is_sample True)` → 채운 수. 검토를 만들지 않는다

**테스트 관점** 빈 캐시 → 3, 파서 3회 · 다시 돌리면 파서 0회, `expires_at` null 유지

---

#### ReviewService.usage_report 하루치 사용량 요약

**시그니처** `usage_report(day: date) -> UsageSummary`

근거: [[JSD-INFRA-001#C3]] · [[JSD-INFRA-001]] 8장 비용 점검

**처리** `DB: usage_logs where updated_at이 day(Asia/Seoul) 안` → `reviews = count`, `failed = count where status failed`, `avg_cost_krw = avg(cost_krw)`(없으면 0) → `UsageSummary`. 한도 비교와 경고 로그는 `jobs.py`가 한다

**테스트 관점** 행이 없는 날 → 0·0·0 · 자정 직전(KST) 갱신 행은 그날로 센다

---

## 3. 미결사항

- [ ] `PRICES.parse_page_krw`의 값 — [[JSD-INFRA-001]] 8장 추정($0.01 × 1,350원 ≈ 14원)을 쓴다. 업스테이지 실제 청구 단가로 확인한다
- [ ] tenants 질문 답 하나에 가구 수·보증금 합계를 함께 받는다([[JSD-PRD-001#R8]]). 지금은 답 문장에서 `factcheck.amounts`로 금액만 뽑고 빈 방 수는 대화에서 말한 값만 쓴다. 질문을 둘로 나눌지
- [ ] `usage_logs.is_sample`은 `sample_id`로만 채운다. 예시 파일을 직접 올린 검토는 예시로 세지 않는다([[JSD-DOM-003]] 5장 되먹임 — 이 문서의 선택)
- [ ] `usage_report`의 날짜 경계를 KST로 두었다. `updated_at`은 되묻기 끝에 다시 쓰여 검토가 날짜를 옮길 수 있다([[JSD-DOM-003]] 5장)
- [ ] `stream`의 주기 1초와 `ask`의 1초 폴링 — 동시 검토 수만큼 DB를 읽는다. 첫 구현에서 잰다([[JSD-SEQ-001]] 미결)
- [ ] 재시작 때 running·waiting_user로 남은 검토를 failed로 닫는 함수는 두지 않았다([[JSD-DOM-002]] 7장 미결)
