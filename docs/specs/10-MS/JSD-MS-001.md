---
doc_id: JSD-MS-001
type: MS
title: 보증금지킴 — 미니스펙
status: draft
upstream: [JSD-SEQ-001, JSD-API-001, JSD-API-002, JSD-DOM-002]
---

# MINISPEC

## 0. 이 문서가 다루는 것

서비스 함수 26개. DTO 타입은 [[JSD-DOM-002]]에만 정의돼 있고 여기서는 이름만 쓴다. 분기는 `if 조건 → 결과 · else → 결과`. REST는 [[JSD-API-001]], 에이전트 도구는 [[JSD-API-002]].

## 1. 함수 목록

| 도메인 | 함수 | 한 줄 |
|---|---|---|
| gate | GateService.validate_file | 형식·크기·페이지 검사 |
| gate | GateService.cache_key | 캐시 키 생성 |
| gate | GateService.cache_lookup | 캐시 조회 |
| gate | GateService.rate_check | IP 일일 한도 |
| gate | GateService.record_usage | 비용 집계 |
| review | ReviewService.create | 세션 생성·루프 시작 |
| review | ReviewService.get | 세션 조회 |
| review | ReviewService.stream_events | SSE 스트림 (실시간·재생) |
| review | ReviewService.answer | 답변 접수·재개 |
| review | ReviewService.override_values | 추출값 수정 후 재판정 |
| review | ReviewService.cancel | 취소 |
| review | AgentLoop.run | 에이전트 루프 |
| review | AgentLoop.dispatch | 도구 호출 라우팅·한도 |
| review | AgentLoop.emit | 이벤트 저장·전송 |
| review | AgentLoop.ask | 질문 대기 |
| registry | RegistryService.read | 파싱 + 구조화 |
| registry | RegistryService.structure | 표 → Registry (LLM) |
| registry | RegistryService.get_html | 원문 HTML |
| rules | RulesService.summarize | 권리 합산 |
| rules | RulesService.check | 신호 + 등급 |
| rules | RulesService.criteria | 규칙표 JSON |
| lookup | LookupService.price | 실거래가 |
| lookup | LookupService.building | 건축물대장 |
| lookup | LookupService.defaulter | 명단 대조 |
| report | ReportService.write | 의견서 조립·문장·후검증 |
| report | ReportService.verify_numbers | 후검증 |
| report | ShareService.create | 공유본 |

## 2. 함수

### 2.1 gate

#### GateService.validate_file 파일 검사

**시그니처** `validate_file(upload: UploadFile) -> FileMeta`

**입력** 업로드 파일 (메모리)

**처리**
1. `if content_type ∉ {pdf, jpeg, png} → invalid_file`
2. `if size > 10MB → invalid_file`
3. `if pdf: page_count = pypdf 페이지 수 · if > 20 → invalid_file`; 이미지는 1
4. `sha256(bytes)` 계산

**출력** `FileMeta{hash, page_count, content_type}`

**예외** | 조건 | 에러 | — 위 각 → `invalid_file` (400)

**테스트 관점** 경계값 10MB·20쪽, 잘못된 확장자, PDF 헤더 위조

근거: [[JSD-UC-001#UC-S10]] · [[JSD-API-001#POST/api/reviews]]

#### GateService.cache_key 캐시 키

**시그니처** `cache_key(file_hash, deposit_manwon, contract_type, counterparty_name|None) -> str`

**처리** `sha256(f"{file_hash}|{deposit}|{type}|{name or ''}")`

**테스트 관점** 이름 유무로 키가 달라짐, 같은 입력은 같은 키

#### GateService.cache_lookup 캐시 조회

**시그니처** `cache_lookup(key) -> UUID | None`

**처리** `select file_cache where cache_key=key and (expires_at is null or expires_at > now())` → `session_id` · 없으면 `None`

**테스트 관점** 만료된 키는 miss, 예시 키는 만료 없음

#### GateService.rate_check IP 한도

**시그니처** `rate_check(ip: str, is_sample: bool) -> None`

**처리**
1. `if is_sample → return`
2. `count = select count(*) from review_sessions where client_ip_hash=sha256(ip) and created_at >= today and is_sample=false`
3. `if count >= 5 → rate_limited`

**테스트 관점** 5번째 허용, 6번째 거절, 예시는 카운트 안 됨, 자정 리셋

#### GateService.record_usage 비용 집계

**시그니처** `record_usage(session_id, kind, units, cost_krw) -> None`

**처리** `insert usage_log` + `review_sessions.cost_krw += cost_krw`

**테스트 관점** 합계 일치

### 2.2 review

#### ReviewService.create 세션 생성

**시그니처** `create(upload|sample_id, deposit_manwon, contract_type, counterparty_name, ip) -> CreateResult`

**입력** 파일 또는 예시 ID, 조건, IP

**처리**
1. `if sample_id → bytes = assets/samples/{id}.pdf, is_sample=True · else → bytes = upload`
2. `meta = validate_file`
3. `rate_check(ip, is_sample)`
4. `key = cache_key(...)`; `hit = cache_lookup(key)`
5. `if hit → insert review_sessions(status=done, cached_from=hit) → return {session_id, cached=True}`
6. `insert review_sessions(status=created, ...)`
7. `background: AgentLoop.run(session_id, bytes)`
8. `return {session_id, cached=False}`

**출력** `CreateResult{session_id, status, cached, is_sample}`

**예외** invalid_file, rate_limited, missing_input

**호출하는 것** GateService 전부, AgentLoop.run

**테스트 관점** 캐시 히트 시 루프가 시작되지 않음, 예시는 한도 무시, 바이트가 디스크에 없음

근거: [[JSD-SEQ-001#SEQ-1]] [[JSD-SEQ-001#SEQ-3]] · [[JSD-API-001#POST/api/reviews]]

#### ReviewService.get 세션 조회

**시그니처** `get(session_id) -> SessionView`

**처리** `select` → `if none → not_found`; `pending_question = 마지막 question 이벤트 (status=waiting_user일 때)`

**테스트 관점** waiting_user일 때 질문 포함

#### ReviewService.stream_events SSE

**시그니처** `stream_events(session_id, last_event_id: int|None) -> AsyncIterator[SSE]`

**처리**
1. `session = get`; `src = session.cached_from or session_id`
2. `if session.cached_from → 저장된 이벤트를 seq > last_event_id부터 0.3초 간격으로 yield → 끝`
3. `else → 저장된 이벤트(seq > last_event_id) 먼저 yield, 이후 루프의 이벤트 큐를 구독해 yield`
4. `report 또는 error 이벤트 후 종료`

**테스트 관점** 재접속 시 중복 없음, 캐시 재생 순서, 종료 조건

근거: [[JSD-SEQ-001#SEQ-1]] [[JSD-SEQ-001#SEQ-3]] · [[JSD-API-001#GET/api/reviews/{id}/events]]

#### ReviewService.answer 답변 접수

**시그니처** `answer(session_id, question_id, answer: Any, file: UploadFile|None) -> None`

**처리**
1. `if status != waiting_user or pending.question_id != question_id → wrong_state`
2. `if file → meta = validate_file; doc_id = RegistryService.read(session_id, bytes, kind=land).id; answer = doc_id`
3. `emit(answer 이벤트)`; `status=running`
4. `AgentLoop.resume(session_id, answer)`

**테스트 관점** 잘못된 question_id, 파일 답변, unknown

근거: [[JSD-SEQ-001#SEQ-2]] · [[JSD-API-001#POST/api/reviews/{id}/answers]]

#### ReviewService.override_values 추출값 수정

**시그니처** `override_values(session_id, price_manwon|None, entries: list[{entry_id, amount_manwon}]) -> Report`

**처리**
1. `if status != done → wrong_state`
2. `registry = load`; 각 entry의 `amount_manwon` 덮어쓰기, `user_modified=True`
3. `rights = RulesService.summarize(registry, deposit, price=price_manwon, source=user_input, answers)`
4. `{signals, grade} = RulesService.check(registry, rights, answers)`
5. `report = ReportService.write(..., rebuild=True)`
6. `emit(answer "시세 직접 입력 N")`; `update reports`

**테스트 관점** 등기부 읽기·외부 조회가 호출되지 않음, `price_source=user_input`

근거: [[JSD-SEQ-001#SEQ-4]]

#### ReviewService.cancel 취소

**시그니처** `cancel(session_id) -> None`

**처리** `AgentLoop.stop`; `delete review_documents`; `status=failed(cancelled)`

**테스트 관점** 취소 후 SSE가 error 이벤트로 끝남

#### AgentLoop.run 에이전트 루프

**시그니처** `run(session_id: UUID, file_bytes: bytes) -> None`

**입력** 세션, 파일 바이트 (메모리)

**처리**
1. `status=running`; `messages = [system(역할·도구·검토 항목·필수 검토·금지), user(세션 요약: 건물 미정, 보증금, 형태, 상대방)]`
2. 반복 (최대 20회):
   1. `resp = openai.chat(messages, tools=8종, tool_choice=auto)`; `record_usage(llm)`
   2. `if resp에 tool_call 없음 → messages += "도구를 고르세요"; retries+=1 · if retries==3 → forced=write_report`
   3. `if 첫 호출 and tool != read_registry → 거절 tool_result "read_registry가 먼저"`
   4. `emit(thought, resp.text)`; `emit(tool_call)`
   5. `result = dispatch(tool, args)`
   6. `emit(tool_result, 요약문)`; `messages += tool_result`
   7. `if tool == write_report and result.ok → break`
   8. `if tool_calls ≥ 20 or cost ≥ 300 → forced=write_report`
   9. `if tool == write_report 요청인데 필수 항목 미시도 (R11) and not forced → tool_result "미시도: [...]" (1회)`
3. `status=done`; `emit(report)`
4. `finally: file_bytes = None` (참조 해제)

**출력** 없음 (이벤트·DB)

**예외** | 파싱 실패·등기부 아님 | `status=failed`, `emit(error)` |

**호출하는 것** dispatch, emit, ask, RegistryService·RulesService·LookupService·ReportService

**테스트 관점** 첫 호출 강제, 텍스트 응답 3회 → 강제 의견서, 20회 한도, 필수 항목 미시도 되돌림 1회, 병렬 tool_calls 처리, 파일 바이트 해제

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-UC-001#UC-S9]] · [[JSD-API-002]] 4절

#### AgentLoop.dispatch 도구 라우팅

**시그니처** `dispatch(session, tool: str, args: dict) -> ToolResult`

**처리**
1. `if tool ∉ 8종 → {ok:false, error:"unknown_tool"}`
2. `tool_calls += 1`
3. 매핑: `read_registry→RegistryService.read` · `summarize_rights→RulesService.summarize` · `check_signals→RulesService.check` · `lookup_price→LookupService.price` · `lookup_building→LookupService.building` · `match_defaulter→LookupService.defaulter` · `ask_user→ask` · `write_report→ReportService.write`
4. `try → {ok:true, data}` · `except ToolError e → {ok:false, error:e.code}` · `except Exception → {ok:false, error:"tool_failed"}` (루프는 계속)

**테스트 관점** 미지 도구 거절, 예외가 루프를 죽이지 않음

#### AgentLoop.emit 이벤트

**시그니처** `emit(session_id, kind, text, tool=None, data=None) -> ReviewEvent`

**처리** `seq = max+1`; `data = scrub_pii(data)`; `insert review_events`; 구독 큐에 push

**테스트 관점** seq 연속, PII 제거(이름·주민번호 패턴)

#### AgentLoop.ask 질문 대기

**시그니처** `ask(session, question: Question) -> Any`

**처리**
1. `if questions_asked >= 5 → ToolError("question_limit")`
2. `questions_asked += 1`; `status=waiting_user`; `emit(question)`
3. `await event.wait(timeout=300)` · `if timeout → answer="unknown"; emit(answer "답변 없이 진행")`
4. `status=running`; `return answer`

**테스트 관점** 한도, 타임아웃, 정상 답변 반영

근거: [[JSD-SEQ-001#SEQ-2]] · [[JSD-API-002#ask_user]]

### 2.3 registry

#### RegistryService.read 등기부 읽기

**시그니처** `read(session_id, file_bytes, kind_hint: str|None) -> Registry`

**처리**
1. `html, blocks = upstage.parse(file_bytes)` (타임아웃 30s, 재시도 1) · 실패 → `ToolError("parse_failed")`
2. `record_usage(parse, pages)`
3. `sections = split(html, ["표제부", "갑구", "을구"])` · `if 갑구·을구 없음 → ToolError("not_registry")`
4. `registry = structure(sections)`
5. `registry.building.building_type = classify(표제부 텍스트)` (아파트/다세대·연립/다가구·단독/오피스텔/기타)
6. `insert review_documents(html, registry, doc_kind)`; `update review_sessions.building_type`
7. `return registry`

**예외** parse_failed, not_registry

**호출하는 것** structure, upstage client

**테스트 관점** 예시 3건 필수 필드 정답 일치, 등기부 아닌 PDF 거절, 토지 등기부(kind=land)

근거: [[JSD-UC-001#UC-S1]] · [[JSD-API-002#read_registry]]

#### RegistryService.structure 구조화

**시그니처** `structure(sections: dict[str, str]) -> Registry`

**처리**
1. 갑구·을구 표를 행 단위 텍스트 + `block_id`로 나열
2. `openai.chat(구조화 프롬프트, response_format=Registry JSON schema)` · 실패 시 1회 재요청 · 그래도 실패 → 해당 구간 빈 목록 + warning
3. 후처리: `purpose_code` 정규화(사전 매핑), `cancelled` 판정(취소선 마크·"말소" 등기목적·말소 대상 순위 참조), 부기등기 `parent_rank_no` 연결과 감액 반영
4. `block_id` 비어 있으면 warning

**테스트 관점** 말소 항목 제외, 부기 감액, 거래가액 추출, purpose_code 매핑표

#### RegistryService.get_html 원문

**시그니처** `get_html(session_id, kind) -> str`

**처리** `select parsed_html` · `if none (만료) → expired`

### 2.4 rules (순수 함수, 외부 의존 없음)

#### RulesService.summarize 권리 합산

**시그니처** `summarize(registries: list[Registry], deposit_manwon: int, price_manwon: int|None, price_source: str|None, other_tenants_manwon: int|None, vacant_rooms: int|None, region: str) -> RightsSummary`

**처리**
1. `mortgage = Σ eul.amount where purpose_code=mortgage and not cancelled` (건물+토지, 부기 감액 반영)
2. `lease = Σ eul.amount where purpose_code=lease_right and not cancelled`
3. `if building_type == multi_household: tenants = (other_tenants or 0) + (vacant_rooms or 0) × 최우선변제금[region]; unknown = other_tenants is None` · else `tenants=0, unknown=False`
4. `senior = mortgage + lease + tenants`
5. `if price → debt_ratio = (senior + deposit)/price, senior_ratio = senior/price` · else `None`
6. `based_on = 사용한 entry_id`

**테스트 관점** 말소 제외, 토지 합산, 다가구 가산, 가격 없음, 5건 이상 단위 테스트

근거: [[JSD-PRD-001#R4]] · [[JSD-API-002#summarize_rights]]

#### RulesService.check 신호·등급

**시그니처** `check(registries, rights: RightsSummary, ctx: CheckContext) -> tuple[list[Signal], Grade]`

**입력** ctx = counterparty_name, proxy_status, illegal_building, owner_type, defaulter_match, building_main_use, today

**처리** (규칙표 [[JSD-PRD-001#R5]] 순서)
1. `encumbrance: gap.purpose_code ∈ {seizure, injunction, provisional, auction, notice} and not cancelled → danger`
2. `trust: gap purpose_code==trust or cause contains 신탁 → danger`
3. `lease_registration: eul purpose_code==housing_lease and not cancelled → danger`
4. `owner_mismatch: counterparty and counterparty != 최종 소유자 → if proxy_status==proxy_with_poa → caution · else → danger`
5. `defaulter_match → danger`
6. `illegal_building==yes or main_use contains 근린생활 (아파트 제외) → danger`
7. `land_right_unregistered or separate_land_registry → caution`
8. `recent_mortgage: 미말소 근저당 received_at ≥ today-90d → caution`
9. `frequent_transfer: 보존등기 ≤ 1y or 2년 내 ownership_transfer ≥ 2 → caution`
10. `corporate_owner: 최종 소유자 holder_is_corporation or owner_type==corporation → caution`
11. `senior_excess: rights.senior_ratio > 0.54 → caution`
12. `multi_household_unknown: rights.multi_household_unknown → caution`
13. 등급: `if any danger or debt_ratio > 0.90 → danger · elif any caution or 0.70 < debt_ratio ≤ 0.90 or price is None or 소유자 미확인 → caution · else → safe`
14. `deciders`, `unknowns` 채움; 각 Signal에 `evidence_ids`(entry_id·answer_id) 필수

**출력** (signals, grade)

**테스트 관점** 규칙 12개 각각 양·음성, 경계 70/90/54, 대리인 완화, 가격 없음 → 최소 주의

근거: [[JSD-PRD-001#R5]] [[JSD-PRD-001#R6]] · [[JSD-API-002#check_signals]]

#### RulesService.criteria 규칙표

**시그니처** `criteria() -> dict`

**처리** 코드의 규칙 상수(경계·신호·필수 검토·가격 순서·최우선변제금·기준일·출처)를 JSON으로

**테스트 관점** PRD R5·R6·R11과 일치 (스냅샷 테스트)

### 2.5 lookup

#### LookupService.price 실거래가

**시그니처** `price(address, building_type, building_name|None, area_m2|None) -> PriceResult`

**처리**
1. `key = cache("price", args)` → hit 반환
2. `lawd = region_code(address)` · 없음 → `ToolError("no_region_code")`
3. 건물 종류별 API 12개월 호출(5s 타임아웃, 재시도 1) → 실패 `api_failed`
4. `건물명 일치 and |면적-area| ≤ 3%` 필터 · 0건 → `ToolError("no_trades")`
5. `평균, 건수, 기간` 캐시 저장(24h) 후 반환

**테스트 관점** 캐시 히트, 코드 없음, 0건, XML 파싱 (녹화된 응답으로)

근거: [[JSD-UC-001#UC-S4]] · [[JSD-API-002#lookup_price]]

#### LookupService.building 건축물대장

**시그니처** `building(address) -> BuildingResult`

**처리** 캐시 → 건축HUB 표제부 조회(5s, 재시도 1) → 여러 건이면 건물명 유사도로 선택 + `multiple_candidates=True` → 캐시

**테스트 관점** 여러 동, 실패 사유

#### LookupService.defaulter 명단 대조

**시그니처** `defaulter(name) -> DefaulterResult`

**처리** `select hug_defaulters where name = :name` · 스냅샷 없음 → `ToolError("no_snapshot")` · 항상 `note="동명이인 가능"`

**테스트 관점** 완전 일치만, 스냅샷 없음

### 2.6 report

#### ReportService.write 의견서 작성

**시그니처** `write(session, registry, rights, signals, grade, answers, review_log, agent_notes|None, rebuild=False) -> Report`

**처리**
1. `checked = 검토 항목 목록(Q37 계약 전 항목) × (시도됨 → ok / 답 unknown·도구 실패 → unknown / 해당 없음 → n_a)`
2. `todos = select_todos(building_type, signals, grade.unknowns)` — 규칙표(계약 전·당일·잔금·입주 후) 상수에서 조건 일치 항목
3. `clauses = [standard_1, standard_2] + (standard_3 if multi_household or 체납 unknown) + (mortgage_release if 근저당) + (insurance_condition if grade != safe) + (owner_change_notice if frequent_transfer) + (tax_consent if 체납 unknown)`; 빈칸 채움(보증금·날짜·채권자)
4. `llm = openai.chat(결론 1문장 + 신호별 쉬운 설명 + 질문 3~5개; 입력은 등급·수치·신호만; "숫자·등급 변경 금지")` · 실패 1회 재시도 · 그래도 실패 → 템플릿 문장, `llm_fallback=True`
5. `report = Report(...)`; `corrections = verify_numbers(report, rights, grade)`
6. `notices = 고정 3개`
7. `insert/update reports`

**출력** Report

**테스트 관점** todos 선택 규칙(다가구·근저당·unknown), 특약 빈칸 채움, LLM 실패 폴백, 후검증 교정

근거: [[JSD-UC-001#UC-S8]] · [[JSD-API-002#write_report]]

#### ReportService.verify_numbers 후검증

**시그니처** `verify_numbers(report, rights, grade) -> int`

**처리**
1. 결론·설명 문장에서 금액(억·천·만원)·백분율·등급어 추출
2. `if 금액 ∉ {rights의 값들} or 비율 ≠ round(debt_ratio) or 등급어 ≠ grade → 해당 문장을 템플릿 문장으로 교체, corrections += 1`
3. 반환 corrections

**테스트 관점** 숫자 바뀐 문장 교체, 정상 문장 통과, 단위 변환(1억 2천 = 12000만원)

#### ShareService.create 공유본

**시그니처** `create(session_id) -> ShareResult`

**처리** `report = load` → `masked = mask(report)` (holder 이름, 주민번호 패턴, 주소 동 이하, review_log·evidence 제거) → `token = secrets(22)` → `insert shares(expires=now+7d)`

**테스트 관점** 마스킹 필드 전부, 만료

## 3. 미결사항

- [ ] `region(주소) → 최우선변제금 지역` 매핑 상수 (과밀억제권역 시군구 목록) — 출처·기준일 명시
- [ ] `scrub_pii` 규칙 (이름 패턴은 등기부 holder 목록으로, 주민번호는 정규식)
- [ ] `select_todos` 규칙표 상수의 전체 목록 — RFQ Q37을 그대로 코드화
- [ ] OpenAI 호출 헬퍼의 재시도·타임아웃 기본값
