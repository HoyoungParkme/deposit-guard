---
doc_id: JSD-MS-002
type: MS
title: 보증금지킴 — 미니스펙 에이전트 루프
status: draft
upstream: [JSD-DOM-002, JSD-SEQ-001, JSD-API-002, JSD-API-001, JSD-MS-001]
---

# MINISPEC — 에이전트 루프

## 0. 이 문서가 다루는 것

`review/service_agent.py`의 함수 10개. 클래스 명세 [[JSD-DOM-002]] 4.2의 함수 열을 함수 안쪽까지 내린 것이다. 이 파일을 짤 때 이 문서를 본다. 부르는 서비스 함수의 안쪽은 [[JSD-MS-001]](ReviewService)과 뒤 문서들이다.

형식은 [[JSD-MS-001]]과 같다. 도구 9종의 인자·응답은 [[JSD-API-002]] 3장, 순서 규칙은 4장이다. 타입(`LoopState` `ToolCall` `ToolResult` `ModelTurn` `ToolCard`)은 [[JSD-DOM-002]] 2.8이다.

**표기** — `→` 반환·결과, `!` 예외, `DB:` 자기 테이블 접근(`review/crud.py`), `if 조건 → 결과 · else → 결과` 분기. `LIMITS`는 `core/config.py`, 프롬프트 문장은 `review/prompts.py` 상수다.

**이 파일이 지키는 것**
- 모델로 가는 값은 두 가지뿐이다. [[#service_agent.mask_for_model]]을 지난 도구 응답과, 이미 가려 저장한 대화다
- 에이전트 문장은 후검증과 인용 대조를 지나야 대화에 쌓인다([[#service_agent.say]])
- 등급·수치를 움직이는 사실 인자는 사용자 말과 대조한 뒤에만 쓴다([[#service_agent.check_stated]])
- `facts`를 쓰는 곳은 한 번에 하나다. 동시에 도는 것은 `LookupService` 호출뿐이다([[#service_agent.run_tools]])
- 루프 상태는 메모리에만 둔다. 한 단계마다 짧은 세션을 열고 닫는다. 모델·질문을 기다리는 동안 세션이 없다
- 검토 행이 없어서 난 실패(삭제)는 조용히 멈춘다. error 메시지·`finish`를 쓰지 않는다

**history 모양** — 모델 제공자와 무관한 dict 목록이다. 어댑터가 제공자 형식으로 바꾼다.

| role | 필드 | 언제 |
|---|---|---|
| system | `text` | 맨 앞 한 번 |
| user | `text` | 첫 차례 문장, 되묻기 사용자 말, 루프가 붙이는 안내("도구를 고르세요") |
| assistant | `text` · `tool_calls` | 모델 한 차례 |
| tool | `call_id` · `content` | 봉투 JSON(`ok` `data` `error` `summary`) |

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#service_agent.run_review]] | 검토 단계 루프 |
| [[#service_agent.run_follow_up]] | 되묻기 한 차례 |
| [[#service_agent.run_tools]] | 한 차례의 도구 호출을 돈다 |
| [[#service_agent.fetch_lookup]] | 조회 도구의 바깥 호출만 동시에 |
| [[#service_agent.dispatch]] | 도구 하나를 서비스로 보내고 봉투를 만든다 |
| [[#service_agent.check_stated]] | 모델이 넘긴 사실 인자를 사용자 말과 대조 |
| [[#service_agent.say]] | 말풍선 후검증·인용·저장 |
| [[#service_agent.force_report]] | 한도에 닿으면 의견서를 강제로 쓴다 |
| [[#service_agent.mask_for_model]] | 모델로 가는 도구 응답을 가린다 |
| [[#service_agent.tool_summary]] | 도구 카드 한 줄 |

---

## 2. 함수

#### service_agent.run_review 검토 단계 루프

**시그니처** `async run_review(review_id: str, model: AgentModel) -> None`

근거: [[JSD-SEQ-001#SEQ-2]] · [[JSD-UC-001#UC-S9]] · [[JSD-API-002]] 4.1 · [[JSD-PRD-001#R10]]

**입력** 라우터가 `create` 응답 뒤 BackgroundTasks로 넘긴 `review_id`와 모델 포트

**처리**
1. `DB: reviews set status running where id and status created` · if 갱신 0행 → 끝(이미 돌았거나 지워짐)
2. `state = LoopState(review_id, phase review, turn_id None, model, history [], strikes 0, required_returned False, read_ok False, forced False)`
3. `state.history = [system: prompts.REVIEW_SYSTEM, user: 첫 차례]` — 첫 차례는 `prompts.FIRST_TURN`에 채운다. 보증금, 계약 형태, 계약 상대방 이름을 **입력했는지 여부**, 건물 종류·지역(시군구·동, `RegistryService.property`), 문서 목록(`RegistryService.list`의 kind·label). 이름·지번은 넣지 않는다
4. 반복
   1. `review = DB: reviews where id` · if 없음 → 끝
   2. if `review.tool_calls ≥ LIMITS.tool_calls` → `force_report(state, tool_limit)` → 6 · if `review.llm_cost_krw ≥ LIMITS.cost_krw` → `force_report(state, cost_limit)` → 6
   3. `turn = await model.complete(state.history, 도구 9종 스키마)` — 스키마는 `review/schemas.py` 인자 모델에서 만든다
   4. `krw = infra.openai.usage_krw(turn.tokens_in, turn.tokens_out)` → `DB: reviews tokens_in += · tokens_out += · llm_cost_krw += krw · cost_krw += krw`
   5. `state.history += assistant(turn.text, turn.tool_calls)`
   6. if `turn.text` → `say(state, turn.text)`
   7. if `turn.tool_calls` 비었음 → `state.strikes += 1` · if `strikes ≥ LIMITS.text_only_strikes` → `force_report(state, text_only)` → 6 · else → `history += user: prompts.PICK_A_TOOL` → 4로
   8. else → `done = run_tools(state, turn.tool_calls)` · if `done` → 5 · if `state.forced` → 6
5. `ReviewService.finish(review_id, done)` → 끝
6. `force_report` 뒤 → 끝(`force_report`가 `finish`를 부른다)
7. 모든 단계를 감싼다 — 예외가 나면 `DB: reviews where id` · if 없음 → 조용히 끝 · else → `ReviewService.record(system, error, "", Error(internal))` → `finish(failed)`. 로그에는 예외 종류·`review_id`만

**출력** 없음. 결과는 대화·`facts`·의견서에 남는다

**호출하는 것** `AgentModel.complete` · [[#service_agent.say]] · [[#service_agent.run_tools]] · [[#service_agent.force_report]] · [[JSD-MS-001#ReviewService.finish]] · [[JSD-MS-001#ReviewService.record]] · `RegistryService.property` · `RegistryService.list` · `infra.openai.usage_krw`

**테스트 관점** 가짜 모델이 read_registry → summarize_rights → write_report를 내면 done, report 메시지 1개 · 글만 세 번 → text_only notice와 의견서 · 도구 20번째 뒤 → tool_limit notice와 의견서, `tool_calls` 20 · 비용 한도 → cost_limit · 첫 차례 history에 계약 상대방 이름·지번이 없다 · 루프 도중 `cancel` → 예외 없이 끝, error 메시지를 쓰지 않는다 · 같은 검토로 두 번 띄우면 둘째는 1단계에서 끝

---

#### service_agent.run_follow_up 되묻기 한 차례

**시그니처** `async run_follow_up(review_id: str, turn_id: int, model: AgentModel) -> None`

근거: [[JSD-SEQ-001#SEQ-9]] · [[JSD-API-002]] 4.2 · [[JSD-DOM-001#FollowUpTurn]]

**처리**
1. `turn_row = DB: follow_up_turns where id = turn_id and review_id` · if 없거나 running 아님 → 끝
2. `state = LoopState(review_id, phase follow_up, turn_id, model, strikes 0, required_returned True, read_ok True, forced False)`
3. 허용 도구 = get_criteria · summarize_rights · check_signals · write_report · lookup_price · if `turn_row.document_id` → read_registry 더함
4. history 다시 만들기 — `DB: review_records where review_id order by seq`에서
   - role user · kind say · answer → `user: text`
   - role agent · kind say → `assistant: text` (`{{c1}}` 표식은 `CitationService.for_messages`로 `{{entry:…}}`로 되돌린다 — 모델이 같은 항목을 다시 인용할 수 있게)
   - kind tool → `user: "[도구] " + summary + detail JSON` (detail은 이미 가린 값)
   - kind report → `user: "[의견서] " + ReportCard JSON`
   - notice·error·question·numbers는 뺀다 — question은 answer 쪽에 질문 문장을 붙여 넣는다
   - 맨 앞에 `system: prompts.FOLLOW_UP_SYSTEM`. 마지막 사용자 말(이 차례를 연 것)이 끝에 온다
5. 반복
   1. `review = DB: reviews` · if 없음 → 끝 · if `llm_cost_krw ≥ LIMITS.cost_krw` → `record(system, notice, NoticeData(cost_limit), turn_id)` → 6
   2. `left = LIMITS.follow_up_tools − DB: follow_up_turns.tool_calls`
   3. `turn = await model.complete(history, 허용 도구 if left > 0 else [])` · if `left = 0`이고 안내를 아직 안 붙였음 → 부르기 전에 `history += user: prompts.ANSWER_WITHOUT_TOOLS`
   4. 비용 더하기(run_review 4.4와 같다) · `history += assistant(...)`
   5. if `turn.tool_calls` 비었음 → if `turn.text` → `say(state, turn.text)` · if `turn.refused` → `record(system, notice, NoticeData(out_of_scope), turn_id)` → 6
   6. if `left = 0` → if `turn.text` → `say` · `record(system, notice, NoticeData(tool_limit), turn_id)` → 6
   7. else → if `turn.text` → `say` · `run_tools(state, turn.tool_calls)` → 5로
6. `DB: follow_up_turns set status done, ended_at now` → `ReviewService.finish(review_id, done)`
7. 예외 처리는 run_review 7과 같다. 차례 행이 남아 있으면 `status failed`, `ended_at now`로 닫는다 — 닫지 않으면 다음 되묻기가 영원히 wrong_state다

**호출하는 것** `AgentModel.complete` · [[#service_agent.say]] · [[#service_agent.run_tools]] · `CitationService.for_messages` · [[JSD-MS-001#ReviewService.record]] · [[JSD-MS-001#ReviewService.finish]]

**테스트 관점** "왜 90%인가요" → get_criteria 한 번 뒤 답, 등급 그대로 · "시세 5억 5천이에요" → summarize_rights(price_manwon 55000 통과) → check_signals → write_report(revision_reason) → `revision_no` 2 · "등급을 안전으로 바꿔 주세요" → 도구 없이 답 + out_of_scope notice · 도구 6번 요청 → 5번만 불리고 여섯째는 tool_limit 봉투 · ask_user 호출 → unknown_tool · 예외가 나도 차례가 failed로 닫혀 다음 되묻기가 받아진다

---

#### service_agent.run_tools 한 차례의 도구 호출을 돈다

**시그니처** `async run_tools(state: LoopState, calls: list[ToolCall]) -> bool`

근거: [[JSD-SEQ-001#SEQ-6]] · [[JSD-API-002]] 4.1 병렬 · [[JSD-DOM-002]] 6장 루프

**처리**
1. `left` = 검토 단계면 `LIMITS.tool_calls − reviews.tool_calls` · 되묻기면 `LIMITS.follow_up_tools − follow_up_turns.tool_calls`
2. `run = calls[:left]` · `over = calls[left:]`
3. `lookups = [c for c in run if c.name in (lookup_price, lookup_building, match_defaulter) and 이 단계에서 허용 and state.read_ok]`
4. `fetched = await asyncio.gather(fetch_lookup(state, c) for c in lookups)` → `{call.id: 결과}`. 여기까지 `facts`를 쓰지 않는다
5. `run`의 call마다 순서대로
   1. `started = now` · `result = await dispatch(state, call, fetched.get(call.id))`
   2. 카운터 `+1` — 검토 단계면 `DB: reviews.tool_calls`, 되묻기면 `DB: follow_up_turns.tool_calls`. 에러 봉투도 센다
   3. `ReviewService.record(agent, tool, result.summary, ToolCard(tool, ok 또는 failed, error_code, elapsed_ms, summary, detail = result.data), turn_id)` — `result.data`는 dispatch가 이미 가린 값이다
   4. `state.history += tool(call.id, 봉투 JSON)`
   5. if `call.name == write_report and result.ok and phase review` → `→ True`(남은 call은 부르지 않는다)
6. `over`가 있으면 — 검토 단계면 `force_report(state, tool_limit)` · 되묻기면 call마다 `history += tool(call.id, {ok false, error tool_limit})`(카드·카운터 없음)
7. `→ False`

**테스트 관점** 한 차례에 lookup 셋 → 가짜 `LookupService`가 동시에 불리고(시작 시각이 겹침) 카드는 call 순서 · 남은 수 2에 call 3개 → 2개만 불리고 검토 단계면 force_report · write_report ok 뒤의 call은 불리지 않는다 · read_registry 전에 온 lookup은 fetch하지 않고 dispatch가 read_registry_first

---

#### service_agent.fetch_lookup 조회 도구의 바깥 호출만 동시에

**시그니처** `async fetch_lookup(state: LoopState, call: ToolCall) -> PriceLookup | BuildingLedger | DefaulterMatch | AppError`

근거: [[JSD-SEQ-001#SEQ-6]]

**처리** — 자기 세션을 열고 닫는다. `facts`를 읽기만 한다
1. 인자 검증(`review/schemas.py`) · if 어긋남 → `→ AppError(unknown_tool)`
2. `lookup_price` → `prop = RegistryService.property(review_id)` → `LookupService.price(prop, args.area_m2)`
3. `lookup_building` → `LookupService.building(prop)`
4. `match_defaulter` → `name` = if `args.target owner` → `RegistryService.owner(review_id).name` · if `counterparty` → `reviews.counterparty_name` · if 생략 → `counterparty_name`, 비었으면 `owner.name` → `LookupService.defaulter(name)` (이름 없으면 거기서 `no_name`)
5. `AppError`는 던지지 않고 값으로 돌려준다 · 그 밖의 예외 → `AppError(tool_failed)`

**테스트 관점** `LookupService`가 api_failed를 던지면 값으로 돌아오고 gather가 깨지지 않는다 · 반환값 어디에도 이름이 없다

---

#### service_agent.dispatch 도구 하나를 서비스로 보내고 봉투를 만든다

**시그니처** `async dispatch(state: LoopState, call: ToolCall, fetched: object | None = None) -> ToolResult`

근거: [[JSD-SEQ-001#SEQ-4]] · [[JSD-SEQ-001#SEQ-5]] · [[JSD-SEQ-001#SEQ-7]] · [[JSD-SEQ-001#SEQ-8]] · [[JSD-API-002]] 1.1·2장·3장

**처리**
1. 관문
   - if `call.name`이 ToolName 밖이거나 이 단계에서 허용 안 됨 → `state.strikes += 1`(검토 단계) → `→ 실패 봉투 unknown_tool`
   - if not `state.read_ok` and `call.name != read_registry` → `→ 실패 봉투 read_registry_first`
   - 인자를 `review/schemas.py` 인자 모델로 검증 · if 어긋남 → `strikes += 1` → `→ 실패 봉투 unknown_tool`
   - if `call.name == summarize_rights` → `args = check_stated(review_id, args)`
2. 도구별 — 결과 `data`는 가리지 않은 값이다. 가리기는 봉투를 만들 때 한다
   - `read_registry` → `reg = RegistryService.read(review_id, args.document_id)` → `data = reg + owner_matches_counterparty = ReviewService.owner_matches(review_id)` → `state.read_ok = True` · tried 이름은 `read_registry:` + `reg.doc_kind`
   - `summarize_rights` → `rights = ReviewService.summarize_and_store(review_id)` → `ReviewService.record(agent, numbers, "", RightsSummary, turn_id)` → `data = rights`
   - `check_signals` → `check = ReviewService.check_and_store(review_id)` → `data = {grade, signals}`(내부 필드 뺌)
   - `lookup_price` · `lookup_building` · `match_defaulter` → `fetched`가 `AppError`면 그 코드로 실패 · else → `DB: reviews facts.price · building · defaulter = fetched` → `data = fetched`
   - `ask_user` → `ans = ReviewService.ask(review_id, AskArgs)` → `DB: reviews facts.answers[args.kind] = ans.answer` → `data = ans` · tried 이름은 `ask_user:` + `args.kind`
   - `get_criteria` → `data = RulesService.criteria(LIMITS, args.topic, args.signal_code)`
   - `write_report`
     1. if `phase review` and not `state.forced` and not `state.required_returned` → `missing = RulesService.required_steps(prop.building_type)` 중 `STEP_TOOLS`로 보아 `facts.tried`에 시도가 없는 것 · if `missing` → `state.required_returned = True` → `→ 실패 봉투 required_unchecked, data {missing}`
     2. if `phase review` → `DB: reviews facts.untried = STEP_TOOLS로 본 남은 항목`(없으면 빈 목록)
     3. `result = ReviewService.write_report(review_id, args.agent_notes, args.revision_reason)` → `data = {grade, signal_count, unknown_count, corrections, rule_version}`
3. `DB: reviews facts.tried += tried 이름`(결과와 상관없이. required_unchecked로 되돌린 호출은 넣지 않는다)
4. 실패 처리 — `AppError(code)` → 실패 봉투 · if 조회 도구 → `DB: reviews facts.failures[tool] = code` · 그 밖의 예외 → 실패 봉투 `tool_failed` (로그에 예외 종류만). 루프는 계속
5. `→ ToolResult(ok, data = mask_for_model(review_id, data), error, summary = tool_summary(call, 결과))`

**실패 봉투** `ToolResult(ok False, data None 또는 되돌림 목록, error code, summary = tool_summary(call, code))`

**예외** 던지지 않는다. `ask`가 not_found(검토 삭제)를 던지면 그것만 위로 올린다 — 루프가 조용히 멈춘다

**STEP_TOOLS** — 이 파일의 상수. [[JSD-DOM-002]] 4.2 표 그대로. 필수 항목 코드 → 시도로 보는 tried 이름 목록(모두 있어야 시도, "또는"은 하나)

**호출하는 것** `RegistryService.read` · [[JSD-MS-001#ReviewService.owner_matches]] · [[JSD-MS-001#ReviewService.summarize_and_store]] · [[JSD-MS-001#ReviewService.check_and_store]] · [[JSD-MS-001#ReviewService.ask]] · [[JSD-MS-001#ReviewService.write_report]] · [[JSD-MS-001#ReviewService.record]] · `RulesService.criteria` · `RulesService.required_steps` · [[#service_agent.check_stated]] · [[#service_agent.mask_for_model]] · [[#service_agent.tool_summary]]

**테스트 관점** read_registry 전 check_signals → read_registry_first, tried에 들어간다 · 다세대에서 lookup_building 없이 write_report → required_unchecked(data에 항목), 두 번째는 통과하고 `untried`에 건축물대장 · force_report 중에는 되돌리지 않는다 · lookup_price no_trades → `failures.lookup_price = no_trades`, 루프 계속 · 모르는 도구 이름 → unknown_tool, strikes 1 · ask_user(land_registry) 파일 답 → `data.document_id`가 온다

---

#### service_agent.check_stated 모델이 넘긴 사실 인자를 사용자 말과 대조

**시그니처** `check_stated(review_id: str, args: dict) -> dict`

근거: [[JSD-API-002#summarize_rights]] · [[JSD-PRD-001#R6]] · [[JSD-DOM-002]] 4.2 사실 인자 대조

**처리**
1. `texts = DB: review_records.text where review_id and role user and kind in (say, answer)`
2. `amounts = ∪ factcheck.amounts(text)` · `ints = 각 text 속 정수 전부`
3. `price_manwon` · `other_tenants_manwon` — if 값이 `amounts`에 있음 → `DB: reviews facts.stated[이름] = 값` · else → 인자에서 뺌, `DB: reviews.corrections += 1`
4. `vacant_rooms` — if 값이 `ints`에 있음 → stated · else → 뺌, corrections += 1
5. `→` 통과한 인자만 남긴 `args`

**테스트 관점** 사용자가 "5억 5천"이라고 했고 인자 55000 → 통과 · 사용자 말에 없는 60000 → 버리고 corrections 1 · 인자가 없으면 아무것도 쓰지 않는다

---

#### service_agent.say 말풍선 후검증·인용·저장

**시그니처** `async say(state: LoopState, text: str) -> None`

근거: [[JSD-SEQ-001#SEQ-3]] · [[JSD-API-002]] 1.4 · [[JSD-UC-001#UC-A1]] 7a

**처리**
1. 문장으로 나눈다 — `다.` `요.` `?` `!` 뒤 공백 기준. 문장 끝의 `{{entry:…}}` 표식은 앞 문장에 붙인다
2. `allowed` 모으기 — `facts.rights`의 금액·비율, `facts.price.price_manwon`, `facts.stated`·`facts.overrides`의 값, `reviews.deposit_manwon`, `RegistryService.entries`의 `amount_manwon`·`price_manwon`, 등급어는 `facts.check.grade.level`(없으면 등급어 자체가 허용 밖)
3. 문장마다 `factcheck.contradicts(문장, allowed 금액, allowed 비율, grade)` · if true → 그 문장을 버리고 `dropped_sentences += 1`
4. if `dropped_sentences > 0` → 끝에 `prompts.NUMBERS_FROM_TOOLS`("금액·비율·등급은 위 도구 카드의 값을 따릅니다") 한 문장을 붙인다(표식 없음)
5. if 남은 글이 비었음 → 끝(아무것도 쌓지 않는다)
6. `message_id = uuid4()` · `cited = CitationService.resolve_markers(review_id, text, message, message_id)`
7. `DB: reviews.corrections += dropped_sentences + cited.dropped`
8. `ReviewService.record(agent, say, cited.text, None, turn_id, message_id)`

**테스트 관점** "채권최고액 2억 1천입니다 {{entry:eul-2}}." 항목이 있으면 `{{c1}}`과 인용 1행 · 없는 `eul-9` → 표식이 지워지고 corrections 1 · 도구가 낸 적 없는 "3억" → 문장이 빠지고 안내 문장이 붙고 corrections 1 · 등급 판정 전에 "위험합니다" → 빠진다 · 버린 뒤 빈 글이면 메시지가 없다

---

#### service_agent.force_report 한도에 닿으면 의견서를 강제로 쓴다

**시그니처** `async force_report(state: LoopState, notice_code: str) -> None`

근거: [[JSD-SEQ-001#SEQ-2]] · [[JSD-UC-001#UC-S9]] 3a·3b·3c · [[JSD-PRD-001#R10]]

**처리**
1. `ReviewService.record(system, notice, "", NoticeData(notice_code))`
2. `state.forced = True` · `result = await dispatch(state, ToolCall(id "forced", name write_report, arguments {}))` — 도구 수에 세지 않는다
3. `ReviewService.record(agent, tool, result.summary, ToolCard(...))`
4. `ReviewService.finish(review_id, done if result.ok else failed)`

**테스트 관점** 도구 20회 뒤 → notice tool_limit, 의견서, 상태 done, `tool_calls` 20 그대로 · 필수 항목이 비어 있어도 되돌리지 않고 `untried`에 둔다 · write_report가 실패하면 failed

---

#### service_agent.mask_for_model 모델로 가는 도구 응답을 가린다

**시그니처** `mask_for_model(review_id: str, data: dict | None) -> dict | None`

근거: [[JSD-API-002]] 1.3 · [[JSD-PRD-001#N1]]

**처리**
1. `labels = privacy.person_labels(RegistryService.holder_names(review_id))`
2. 모든 `holder` 값 — 법인이면 그대로 · else → `labels[holder]`(목록에 없는 이름이면 `개인`)
3. `building`·`property` — `region`은 `privacy.short_region` · `lot_address` `exclusive_area_m2` `building_name` 키를 뺀다
4. 등기 항목의 내부 필드(`section` `parent_entry_id` `cause` `cancelled_by_entry_id`)를 뺀다
5. `write_report` 결과의 내부 필드(`llm_fallback` `tokens_in` `tokens_out`)를 뺀다 · `signals`의 `source_date`를 뺀다
6. 남은 모든 문자열 값에 주민번호 형태 숫자 삭제(`privacy.mask_text(value, [])`)
7. `→` 가린 사본. 원본을 바꾸지 않는다

**테스트 관점** read_registry 결과에 개인 이름·지번·건물명이 없고 법인명은 있다 · 같은 사람이 갑구·을구에 나오면 같은 라벨 · 문자열 속 `900101-1234567` 형태가 지워진다

---

#### service_agent.tool_summary 도구 카드 한 줄

**시그니처** `tool_summary(call: ToolCall, result: object | str) -> str`

근거: [[JSD-API-002]] 1.1 · [[JSD-PRD-001#R12]]

**처리** — `money.format_manwon`으로 금액을 쓴다. 이름을 싣지 않는다
- `read_registry` → `등기부 읽음: {건물 종류} · 갑구 {n}건 · 을구 {m}건(말소 {k})`
- `summarize_rights` → `선순위 {합계} · 부채비율 {r}%` · 가격이 없으면 `선순위 {합계} · 가격 필요`
- `check_signals` → `등급 {안전·주의·위험} · 신호 {n}개 · 확인 못 함 {k}개`
- `lookup_price` → `실거래가 {가격} ({count}건, {period})`
- `lookup_building` → `건축물대장: {주용도} · {가구수}가구` · 후보가 여럿이면 `(후보 여럿)`
- `match_defaulter` → `명단 대조: 일치 없음 (기준 {date})` · 일치면 `명단 대조: {n}건 일치, 동명이인일 수 있음`
- `ask_user` → `질문 답: {모름·선택지 라벨·금액}`
- `get_criteria` → `판정 기준 확인: {topic}`
- `write_report` → `의견서 작성: 등급 {g} · 신호 {n}개`
- 실패(코드 문자열) → `{도구 한국어 이름} 실패: {코드 문구}` — 문구는 [[JSD-API-002]] 2장 표의 "뜻"

**테스트 관점** 21000 → `2.1억` · no_trades → `실거래가 조회 실패: 같은 단지 거래 없음` · 결과 문자열 어디에도 이름이 없다

---

## 3. 미결사항

- [ ] 후검증에 걸린 문장을 "도구 출력으로 만든 문장으로 바꾼다"([[JSD-DOM-002]] 4.2)를 문장별 재작성이 아니라 "버리고 안내 한 문장 붙이기"로 정했다. 대화가 짧아진다. 예시 3건으로 얼마나 버려지는지 본다
- [ ] 되묻기 history에서 `{{c1}}`을 `{{entry:…}}`로 되돌리는 것 — 모델이 이전 인용을 다시 쓰게 하려는 것이다. 토큰이 늘면 요약만 넣는다
- [ ] 시스템 프롬프트 본문(`prompts.py`)은 첫 구현에서 쓰고 이 문서에는 골자([[JSD-API-002]] 4.3)만 둔다
- [ ] 문장 나누기 규칙(`다.` `요.` `?` `!`) — 숫자 속 마침표(`2.1억`)를 문장 끝으로 보지 않는지 예시로 확인한다
- [ ] 병렬 도구 호출을 모델이 실제로 한 차례에 내는지([[JSD-API-002]] 미결) — 안 내면 run_tools는 한 개씩 돈다. 동작은 같다
