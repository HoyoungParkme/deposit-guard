---
doc_id: JSD-API-001
type: API
title: 보증금지킴 — REST API
status: draft
upstream: [JSD-UI-001, JSD-DOM-001, JSD-PRD-001, JSD-UC-001]
---

# API 명세 REST

## 0. 이 문서가 다루는 것

브라우저와 서버 사이의 HTTP 경로 16개. 에이전트가 부르는 도구는 다른 문서에서 정한다.

**3줄 요약.** 검토 하나가 `review`이고, 그 안의 모든 진행은 `message` 목록이다. 말풍선·도구 카드·질문·숫자·의견서가 전부 message이며 `kind`로 갈린다. 사용자의 답변과 되묻기도 같은 자원에 POST한다.

**인용이 이 API의 중심이다.** 메시지 본문에는 `{{c1}}` 같은 자리표시가 들어가고 `citations` 배열이 그것을 등기부 블록으로 잇는다. 반대 방향(이 블록이 어디에 쓰였나)은 `GET /api/reviews/{id}/blocks/{blockId}`가 답한다.

## 1. 규칙

- 로그인이 없다. 검토는 추측할 수 없는 `review_id`로만 식별한다. 아는 사람이 곧 권한이다
- 모든 응답은 JSON. 업로드만 `multipart/form-data`, 원문만 `text/html`, 스트림만 `text/event-stream`
- 금액은 **만원 단위 정수**로 주고받는다. 억 표기는 화면이 만든다 ([[JSD-DOM-001#RightsSummary]])
- 시각은 ISO 8601, 시간대 포함
- 실패는 2절의 봉투로 돌려준다. 상태 코드와 `code`를 함께 본다
- 개인정보는 응답에 넣지 않는다. 이름·주민번호 형태의 숫자·상세 주소는 메시지 본문에서 가린다 ([[JSD-PRD-001#N1]])
- 캐시하지 않는다(`Cache-Control: no-store`). 예시 파일 조회만 예외
- 등급과 수치는 서버가 정한 값을 그대로 내려보낸다. 클라이언트가 계산하지 않는다 ([[JSD-PRD-001#R6]])
- 보관 기간이 지난 검토는 `410 gone`으로 답한다. 내용은 남기지 않는다

## 2. 에러

```yaml
Error:
  type: object
  properties:
    code:   { type: string }
    detail: { type: string, description: 사람이 읽는 한 줄 }
    field:  { type: string, nullable: true }
```

| 코드 | 상태 | 언제 |
|---|---|---|
| `missing_input` | 400 | 파일·보증금 같은 필수 입력이 없음 |
| `invalid_file` | 400 | 형식·크기·쪽수 초과, 암호 걸린 PDF |
| `not_registry` | 400 | 등기부가 아닌 문서 |
| `parse_failed` | 502 | 올린 문서의 파싱이 재시도 뒤에도 실패함 |
| `rate_limited` | 429 | IP 하루 한도 초과 (예시 파일은 세지 않음) |
| `not_found` | 404 | 없는 검토·문서·블록·공유 토큰 |
| `gone` | 410 | 보관 기간이 지나 삭제됨 |
| `wrong_state` | 409 | 지금 상태에서 할 수 없는 요청 (예: 검토 중인데 값 수정) |
| `question_limit` | 409 | 질문 한도 초과 |
| `ask_limit` | 429 | 되묻기 한도 초과 |
| `out_of_scope` | 200 | 요청을 거절하고 이유를 메시지로 답함 (등급 변경 요구 등). HTTP는 성공 |
| `internal` | 500 | 예상 밖 오류 |

## 3. 엔드포인트

### 3.1 검토 시작과 상태

#### POST/api/reviews 검토 시작

화면 [[JSD-UI-001#UI-1]] · 유스케이스 [[JSD-UC-001#UC-A1]] [[JSD-UC-001#UC-A2]] · 서비스 `ReviewService.create`

```yaml
/api/reviews:
  post:
    summary: 등기부와 조건을 받아 검토를 만들고 대화를 시작한다
    requestBody:
      multipart/form-data:
        file:              { type: string, format: binary }   # file 또는 sample_id 하나
        sample_id:         { type: string }                   # GET /api/samples의 id
        deposit_manwon:    { type: integer, minimum: 1 }
        contract_type:     { type: string, enum: [jeonse, monthly] }
        counterparty_name: { type: string, nullable: true }
    responses:
      201:
        content: { review_id: uuid, status: created, is_sample: bool, expires_at: datetime }
      400: missing_input | invalid_file | not_registry
      429: rate_limited
      502: parse_failed
```

등기부 파싱은 이 요청 안에서 끝난다(같은 파일이면 파싱 캐시를 쓴다). 파일 바이트는 디스크에 쓰지 않고 요청이 끝나면 버린다. 응답 직후 대화가 시작되므로 클라이언트는 바로 스트림에 붙는다.

#### GET/api/reviews/{id} 검토 상태

화면 [[JSD-UI-001#UI-2]] · 서비스 `ReviewService.get`

```yaml
/api/reviews/{id}:
  get:
    summary: 상단 바에 필요한 요약과 진행 수치
    responses:
      200:
        content:
          review_id: uuid
          status: { enum: [created, running, waiting_user, done, failed, expired] }
          subject: { building_type, deposit_manwon, contract_type, region }   # 이름은 싣지 않는다 (1절)
          counters: { tool_calls, questions_asked, asks_used, elapsed_sec, cost_krw }
          pending_question: Question | null
          documents: [{ document_id, kind, label }]
          has_report: bool
          expires_at: datetime
      404: not_found
      410: gone
```

#### DELETE/api/reviews/{id} 검토 중단·삭제

화면 [[JSD-UI-001#UI-2]] · 서비스 `ReviewService.cancel`

```yaml
/api/reviews/{id}:
  delete:
    summary: 진행 중이면 멈추고, 원문·대화·의견서와 그 파일의 파싱 캐시(예시 파일 제외)를 즉시 지운다
    responses:
      204: {}
      404: not_found
      410: gone          # 이미 만료됨. 남은 만료 행은 지우지 않는다
```

### 3.2 대화

#### GET/api/reviews/{id}/messages 대화 불러오기

화면 [[JSD-UI-001#UI-2]] · 서비스 `ReviewService.list_messages`

```yaml
/api/reviews/{id}/messages:
  get:
    summary: 재방문·재접속·스트림 폴백에 쓴다
    parameters:
      after_seq: { type: integer, default: 0 }
      limit:     { type: integer, default: 200 }
    responses:
      200: { messages: [Message], next_seq: integer, status: string }
      404: not_found
      410: gone
```

#### GET/api/reviews/{id}/stream 대화 스트림

화면 [[JSD-UI-001#UI-2]] · 유스케이스 [[JSD-UC-001#UC-S9]] · 서비스 `ReviewService.stream`

```yaml
/api/reviews/{id}/stream:
  get:
    summary: text/event-stream. Last-Event-ID로 이어 받는다
    parameters:
      Last-Event-ID: { in: header, type: integer, description: 마지막으로 받은 message.seq }
    events:
      - event: message   # 완성된 말풍선·카드 하나. data = Message
      - event: delta     # 생성 중인 문장 조각. data = { message_id, seq, text }
      - event: state     # 상태·수치 변경. data = { status, counters, pending_question }
      - event: done      # 더 보낼 것이 없음. 연결을 닫는다
      - event: error     # data = Error
    ends: done 또는 error 뒤 종료
```

`delta`는 화면에 글자가 흐르게 하는 용도이며 없어도 동작해야 한다. 프록시가 스트림을 막으면 클라이언트는 `GET /messages`를 짧은 주기로 조회해 같은 결과를 얻는다.

#### POST/api/reviews/{id}/messages 사용자 발화

화면 [[JSD-UI-001#UI-2]] · 유스케이스 [[JSD-UC-001#UC-A3]] · 서비스 `ReviewService.receive`

```yaml
/api/reviews/{id}/messages:
  post:
    summary: 질문에 답하거나, 되묻거나, 서류를 더 올린다
    requestBody:
      application/json:
        kind:        { enum: [answer, ask] }
        question_id: { type: string, nullable: true }   # kind=answer일 때 필수
        text:        { type: string, nullable: true }
        choice:      { type: string, nullable: true }   # 선택지 답변
      multipart/form-data:
        kind:        answer | ask
        question_id: string
        file:        binary                             # 토지 등기부 등 추가 서류
    responses:
      202: { message_id, seq }      # 접수. 결과는 스트림으로 온다
      400: missing_input | invalid_file | not_registry
      409: wrong_state | question_limit
      429: ask_limit
      502: parse_failed
```

답변과 되묻기를 한 경로로 받는다. 화면에서 둘 다 같은 입력창이기 때문이다. 서버는 `kind`와 `question_id`로 구분한다.

### 3.3 문서와 인용

#### GET/api/reviews/{id}/documents 문서 목록

화면 [[JSD-UI-001#UI-2]] · 서비스 `RegistryService.list`

```yaml
/api/reviews/{id}/documents:
  get:
    summary: 문서 패널의 탭 목록
    responses:
      200: { documents: [{ document_id, kind: building|land|collective, label, page_count }] }
```

#### GET/api/reviews/{id}/documents/{documentId} 원문 보기

화면 [[JSD-UI-001#UI-2]] · 서비스 `RegistryService.get_html`

```yaml
/api/reviews/{id}/documents/{documentId}:
  get:
    summary: 파싱된 등기부 HTML. 블록마다 data-block-id가 붙어 있다
    responses:
      200: { content: text/html }
      404: not_found
      410: gone      # 보관 기간 경과. 원문은 대화·의견서와 함께 사라진다
```

#### GET/api/reviews/{id}/blocks/{blockId} 이 줄이 쓰인 곳

화면 [[JSD-UI-001#UI-2]] · 서비스 `CitationService.usages`

```yaml
/api/reviews/{id}/blocks/{blockId}:
  get:
    summary: 등기부 한 줄이 합산·신호·특약 어디에 쓰였는지 되짚는다
    responses:
      200:
        content:
          block_id: string
          excerpt: string                       # 그 줄의 짧은 원문
          used_in:
            - { kind: rights,  label: "선순위 합산 2.1억 (부채비율 78%)" }
            - { kind: signal,  label: "근저당이 두 달 전에 설정됐습니다", signal_code: recent_mortgage }
            - { kind: clause,  label: "보증보험 가입 불가 시 무효" }
            - { kind: message, label: "을구를 봤습니다…", message_id: uuid }
      404: not_found
```

### 3.4 의견서

#### GET/api/reviews/{id}/report 의견서

화면 [[JSD-UI-001#UI-3]] · 유스케이스 [[JSD-UC-001#UC-S8]] · 서비스 `ReportService.get`

```yaml
/api/reviews/{id}/report:
  get:
    summary: 등급·근거·할 일·특약이 담긴 의견서 전체
    responses:
      200: Report        # 4절 스키마
      404: not_found     # 아직 나오지 않음
      410: gone
```

#### PATCH/api/reviews/{id}/values 추출값 수정

화면 [[JSD-UI-001#UI-3]] · 서비스 `ReviewService.override_values`

```yaml
/api/reviews/{id}/values:
  patch:
    summary: 시세나 금액을 고쳐 규칙만 다시 돌린다. 등기부 읽기·외부 조회는 하지 않는다
    requestBody:
      application/json:
        price_manwon: { type: integer, nullable: true }
        entries: [{ entry_id: string, amount_manwon: integer }]
    responses:
      200: Report        # 갱신된 의견서. 대화에는 "직접 입력" 메시지와 새 의견서 카드가 남는다
      400: missing_input # 이 검토의 등기부에 없는 entry_id (field entries)
      409: wrong_state   # 검토가 끝나지 않음
```

#### POST/api/reviews/{id}/shares 공유 링크 만들기

화면 [[JSD-UI-001#UI-3]] · 서비스 `ShareService.create`

```yaml
/api/reviews/{id}/shares:
  post:
    summary: 마스킹한 사본을 만들고 토큰을 돌려준다
    responses:
      201: { token: string, url: string, expires_at: datetime }
      404: not_found
```

#### GET/api/shares/{token} 공유본 보기

화면 [[JSD-UI-001#UI-5]] · 서비스 `ShareService.get`

```yaml
/api/shares/{token}:
  get:
    summary: 이름·상세 주소·원문·대화를 뺀 읽기 전용 의견서
    responses:
      200:
        content:
          report: Report          # citations 없음, review_log 없음
          subject: { region_short, building_type, deposit_manwon, contract_type, reviewed_at }
          expires_at: datetime
      404: not_found
      410: gone                   # 만료. 화면은 만료 안내만 띄운다
```

### 3.5 공개 정보

#### GET/api/criteria 판정 기준

화면 [[JSD-UI-001#UI-4]] · 유스케이스 [[JSD-PRD-001#R6]] · 서비스 `RulesService.criteria`

```yaml
/api/criteria:
  get:
    summary: 코드의 규칙 상수를 그대로 내려보낸다. 화면이 표로 그린다
    responses:
      200:
        content:
          rule_version: "2026-09-15"
          grades:        [{ level, condition }]
          signals:       [{ code, severity, label, source, source_date }]
          debt_ratio:    { formula, danger: 0.90, caution: 0.70, senior: 0.54 }
          required_checks: { apartment: [...], multi_family_unit: [...], multi_household: [...], officetel: [...] }
          price_order:   [trade_api, registry_sale, user_input]
          priority_repayment: [{ region, amount_manwon, effective_date }]
          checklist:     [{ no, label, source_kind }]
          limits:        { tool_calls, questions, asks, answer_timeout_sec, file_mb, pages, retention_hours }
          sources:       [{ name, what_it_defines, as_of }]
```

#### GET/api/samples 예시 목록

화면 [[JSD-UI-001#UI-1]] · 서비스 `SampleService.list`

```yaml
/api/samples:
  get:
    summary: 시작 화면의 예시 카드 3개
    responses:
      200:
        content:
          samples:
            - sample_id: multi_family_caution
              title: 신축 빌라
              summary: 시세가 없고 근저당이 큰 다세대
              region: 서울 강서구
              deposit_manwon: 18000
              contract_type: jeonse
```

#### GET/health 헬스체크

서비스 `HealthService.check`

```yaml
/health:
  get:
    responses:
      200: { status: ok, db: ok, version: string }
      503: { status: degraded, db: fail }
```

## 4. 공통 스키마

### 4.1 메시지

대화의 한 칸. 말풍선도 카드도 모두 이것이다.

```yaml
Message:
  type: object
  properties:
    message_id: { type: string, format: uuid }
    seq:        { type: integer, description: 검토 안에서 1부터. Last-Event-ID로 쓴다 }
    role:       { enum: [agent, user, system] }
    kind:       { enum: [say, tool, question, answer, numbers, report, notice, error] }
    text:       { type: string, description: "사람이 읽는 문장. 인용 자리에 {{c1}} 같은 표시가 들어간다" }
    citations:  { type: array, items: Citation }
    data:       { type: object, nullable: true, description: kind별 본문. 아래 표 }
    created_at: { type: string, format: date-time }
```

| kind | 누가 | data에 담기는 것 | 화면 |
|---|---|---|---|
| `say` | agent | 없음 | 말풍선 |
| `tool` | agent | `{ tool, status: running·ok·failed, error_code, elapsed_ms, summary, detail }` | 도구 카드 |
| `question` | agent | `Question` | 질문 카드 |
| `answer` | user | `{ question_id, choice, text, document_id }` | 사용자 말풍선 |
| `numbers` | agent | `RightsSummary` | 숫자 네 칸 |
| `report` | agent | `{ grade, signal_count, unknown_count, rule_version, revision_no, revision_reason }` | 의견서 카드. 판이 올라가면 이전 카드는 흐려진다 |
| `notice` | system | `{ code }` | 안내 띠 (답변 없이 진행, 한도 도달 등) |
| `error` | system | `Error` | 오류 줄 |

### 4.2 인용

```yaml
Citation:
  type: object
  properties:
    key:        { type: string, description: "본문의 {{c1}}과 맞는 키" }
    label:      { type: string, example: "을구 2번" }
    document_id:{ type: string, format: uuid }
    block_ids:  { type: array, items: string, description: 원문 HTML의 data-block-id }
    entry_ids:  { type: array, items: string, description: 등기 항목 ID. 합산·신호와 이어진다 }
```

화면은 `{{c1}}`을 칩으로 바꾸고, 누르면 `block_ids`의 첫 블록으로 이동해 강조한다. 여러 개면 패널 머리에서 순회한다 ([[JSD-UI-001#UI-2]]).

### 4.3 질문

```yaml
Question:
  type: object
  properties:
    question_id: { type: string }
    kind:        { enum: [illegal_building, price, tenants, proxy, owner_type, land_registry, other] }
    text:        { type: string }
    why:         { type: string, description: 왜 묻는지 한 줄 }
    input_type:  { enum: [choice, number, text, file] }
    options:     { type: array, items: string, nullable: true }
    help_url:    { type: string, nullable: true }
    asked_no:    { type: integer, description: 몇 번째 질문인지 }
```

### 4.4 의견서

```yaml
Report:
  type: object
  properties:
    grade:       { level: safe|caution|danger, deciders: [string], unknowns: [string], rule_version: string }
    conclusion:  { text: string, citations: [Citation] }
    rights:      RightsSummary
    signals:     [{ code, severity, label, explanation, source, source_date, citations: [Citation] }]
    checked:     [{ code, label, result: ok|unknown|n_a, citations: [Citation] }]
    todos:       [{ stage: before|signing|balance|after, title, how, cost, because: [string] }]
    clauses:     [{ title, body, source, filled: object }]
    questions_to_ask: [string]
    notices:     [string]
    corrections: { type: integer, description: 후검증에서 바꾼 문장 수 }
    llm_fallback:{ type: boolean }
    revision_no: { type: integer, description: 판. 첫 판은 1이고 다시 쓸 때마다 1 오른다 }
    revision_reason: { type: string, nullable: true, description: 다시 쓴 이유. 이름을 가린 한 줄. 첫 판은 null }
```

### 4.5 권리 합산

```yaml
RightsSummary:
  type: object
  properties:
    senior_mortgage_manwon: integer
    senior_lease_manwon:    integer
    other_tenants_manwon:   integer
    senior_total_manwon:    integer
    deposit_manwon:         integer
    price_manwon:           { type: integer, nullable: true }
    price_source:           { enum: [trade_api, registry_sale, user_input], nullable: true }
    debt_ratio:             { type: number, nullable: true }
    senior_ratio:           { type: number, nullable: true }
    multi_household_unknown:boolean
    based_on:               { type: array, items: string, description: 합산에 쓴 등기 항목 ID }
```

## 5. 미결사항

- [ ] 되묻기 한도를 질문 한도와 따로 둘지 — 이 문서는 `asks`로 따로 세는 안. 숫자는 정하지 않았다
- [ ] `delta` 이벤트를 1차에 구현할지 — 없어도 동작하지만 데모에서 보이는 차이가 크다
- [ ] 인용의 단위 — `block_ids`가 표의 행인지 셀인지. 파싱 결과 구조에 달렸다
- [ ] `out_of_scope`를 HTTP 200으로 두는 것이 맞는지 — 거절도 대화의 일부라 메시지로 답하는 안
- [ ] 공유본에서 `Report.citations`를 통째로 빼는지, 라벨만 남기는지
- [x] PDF 저장을 클라이언트 인쇄로 두면 이 문서에 엔드포인트가 없다 — 결정(2026-09-17): 브라우저 인쇄. 엔드포인트를 두지 않는다([[JSD-UC-001#UC-A4]] 2)
