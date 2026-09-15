---
doc_id: JSD-API-001
type: API
title: 보증금지킴 — REST API·에이전트 도구
status: draft
upstream: [JSD-UC-001, JSD-UI-001, JSD-DOM-002, JSD-INFRA-001]
---

# API 명세 REST + 에이전트 도구

## 0. 이 문서가 다루는 것

브라우저가 부르는 REST 엔드포인트 14개와, 에이전트가 부르는 도구 8종의 함수 호출 스키마. DTO는 [[JSD-DOM-002]], 테이블은 [[JSD-DOM-001]].

## 1. 규칙

- 경로는 `/api/...`. 세션 ID는 uuid. 응답은 JSON, 시각은 ISO 8601 UTC
- 인증 없음. 세션 ID 자체가 열쇠 (추측 불가). 공유본은 별도 토큰
- 실패는 `{ "error": { "code": "...", "message": "..." } }`. 코드는 2절
- 파일 업로드는 multipart. 바이트는 메모리에서 파싱 API로 전달하고 디스크에 쓰지 않는다
- 도구 입출력은 [[JSD-DOM-002]]의 DTO를 JSON으로 직렬화한 것. 도구는 모두 `{ "ok": bool, "data": ..., "error": str|null }` 봉투로 돌려준다

## 2. 에러

| 코드 | HTTP | 언제 |
|---|---|---|
| `invalid_file` | 400 | 형식·크기·페이지 초과 |
| `missing_input` | 400 | 보증금·계약 형태 없음 |
| `rate_limited` | 429 | IP 일일 한도 |
| `not_found` | 404 | 세션·공유 토큰 없음 |
| `expired` | 410 | 세션 만료(원문 삭제) 또는 공유 만료 |
| `not_registry` | 422 | 등기부로 읽히지 않음 |
| `wrong_state` | 409 | 답변할 질문이 없거나 세션이 끝남 |
| `upstream_failed` | 502 | 파싱 서비스 실패 (재시도 후) |

## 3. 엔드포인트

#### POST/api/reviews 검토 세션 생성

화면 [[JSD-UI-001#UI-1]] · 유스케이스 [[JSD-UC-001#UC-A1]] [[JSD-UC-001#UC-A2]] [[JSD-UC-001#UC-S10]] · 서비스 `ReviewService.create`

```yaml
/api/reviews:
  post:
    summary: 파일·조건을 받아 검사·캐시 확인 후 세션을 만들고 에이전트 루프를 시작한다
    requestBody:
      multipart/form-data:
        file: binary            # 또는 sample_id
        sample_id: string       # apartment_safe | multi_family_caution | multi_household_danger
        deposit_manwon: integer
        contract_type: jeonse | monthly
        counterparty_name: string  # 선택
    responses:
      201: { session_id, status, cached: bool, is_sample: bool }
      400: invalid_file | missing_input
      429: rate_limited
```

`cached=true`면 클라이언트는 이벤트 스트림에서 재생 이벤트를 받는다.

#### GET/api/reviews/{id} 세션 조회

화면 [[JSD-UI-001#UI-2]] [[JSD-UI-001#UI-3]] · 유스케이스 [[JSD-UC-001#UC-A1]] · 서비스 `ReviewService.get`

```yaml
/api/reviews/{id}:
  get:
    responses:
      200: { session_id, status, building_type, deposit_manwon, contract_type, is_sample, cached, pending_question: Question|null, created_at, expires_at }
      404: not_found
```

#### GET/api/reviews/{id}/events 진행 이벤트 스트림 (SSE)

화면 [[JSD-UI-001#UI-2]] · 유스케이스 [[JSD-UC-001#UC-S9]] · 서비스 `ReviewService.stream_events`

```yaml
/api/reviews/{id}/events:
  get:
    summary: text/event-stream. Last-Event-ID 헤더로 재개. 캐시 세션이면 저장된 이벤트를 0.3초 간격으로 재생
    events:
      - id: seq
        event: thought | tool_call | tool_result | question | answer | report | error
        data: ReviewEvent JSON
    ends: report 또는 error 이벤트 후 종료
```

#### POST/api/reviews/{id}/answers 질문에 답하기

화면 [[JSD-UI-001#UI-2]] · 유스케이스 [[JSD-UC-001#UC-A3]] [[JSD-UC-001#UC-S7]] · 서비스 `ReviewService.answer`

```yaml
/api/reviews/{id}/answers:
  post:
    requestBody:
      application/json: { question_id: string, answer: any }   # "unknown" 허용
      multipart/form-data: { question_id, file }               # 토지 등기부 요청일 때
    responses:
      202: { accepted: true }
      409: wrong_state
```

#### PATCH/api/reviews/{id}/values 추출값 수정

화면 [[JSD-UI-001#UI-3]] · 유스케이스 [[JSD-UC-001#UC-A1]] (8a) · 서비스 `ReviewService.override_values`

```yaml
/api/reviews/{id}/values:
  patch:
    summary: 시세 또는 특정 entry의 금액을 고치고 rules 도구만 다시 돌려 의견서를 갱신한다
    requestBody: { price_manwon?: integer, entries?: [{ entry_id, amount_manwon }] }
    responses:
      200: Report
      409: wrong_state
```

#### GET/api/reviews/{id}/report 의견서

화면 [[JSD-UI-001#UI-3]] · 유스케이스 [[JSD-UC-001#UC-A1]] · 서비스 `ReportService.get`

```yaml
/api/reviews/{id}/report:
  get:
    responses:
      200: Report
      404: not_found
```

#### GET/api/reviews/{id}/document 원문 HTML

화면 [[JSD-UI-001#UI-3]] (원문 패널) · 유스케이스 [[JSD-UC-001#UC-A1]] · 서비스 `RegistryService.get_html`

```yaml
/api/reviews/{id}/document:
  get:
    parameters: { kind: building | land | collective }
    responses:
      200: text/html   # 블록마다 data-block-id
      410: expired     # 24h 지나 삭제됨
```

#### GET/api/reviews/{id}/report.pdf PDF 저장

화면 [[JSD-UI-001#UI-3]] · 유스케이스 [[JSD-UC-001#UC-A4]] · 서비스 `ReportService.render_pdf`

```yaml
/api/reviews/{id}/report.pdf:
  get:
    responses:
      200: application/pdf
```

#### POST/api/reviews/{id}/shares 공유 링크 생성

화면 [[JSD-UI-001#UI-3]] · 유스케이스 [[JSD-UC-001#UC-A4]] · 서비스 `ShareService.create`

```yaml
/api/reviews/{id}/shares:
  post:
    responses:
      201: { token, url, expires_at }
```

#### GET/api/shares/{token} 공유본 조회

화면 [[JSD-UI-001#UI-5]] · 유스케이스 [[JSD-UC-001#UC-A4]] · 서비스 `ShareService.get`

```yaml
/api/shares/{token}:
  get:
    responses:
      200: Report (마스킹, review_log·evidence 제외)
      410: expired
```

#### DELETE/api/reviews/{id} 검토 취소

화면 [[JSD-UI-001#UI-2]] · 유스케이스 [[JSD-UC-001#UC-A1]] · 서비스 `ReviewService.cancel`

```yaml
/api/reviews/{id}:
  delete:
    summary: 루프 중단, 문서 삭제, 상태 failed(cancelled)
    responses: { 204: {} }
```

#### GET/api/samples 예시 파일 목록

화면 [[JSD-UI-001#UI-1]] · 유스케이스 [[JSD-UC-001#UC-A2]] · 서비스 `SampleService.list`

```yaml
/api/samples:
  get:
    responses:
      200: [{ sample_id, title, subtitle, building_type, deposit_manwon, contract_type, download_url }]
```

#### GET/api/criteria 판정 기준

화면 [[JSD-UI-001#UI-4]] · 유스케이스 [[JSD-PRD-001#R6]] · 서비스 `RulesService.criteria`

```yaml
/api/criteria:
  get:
    summary: 코드의 규칙 상수에서 생성. 등급표·신호표·건물별 필수 검토·가격 산정 순서·최우선변제금·기준일·출처
    responses: { 200: object }
```

#### GET/health 헬스체크

유스케이스 [[JSD-INFRA-001#C1]] · 서비스 `HealthService.check`

```yaml
/health:
  get:
    responses:
      200: { db: ok, recent_failure_rate: number, version }
      503: { db: fail }
```

## 4. 도구 (에이전트 함수 호출)

OpenAI 함수 호출 스키마. 모든 도구는 `{ ok, data, error }` 봉투로 응답한다. 인자·응답의 DTO는 [[JSD-DOM-002]].

#### read_registry 등기부 읽기

유스케이스 [[JSD-UC-001#UC-S1]] · 서비스 `RegistryService.read`

```json
{
  "name": "read_registry",
  "description": "업로드된 등기부 문서를 파싱해 표제부·갑구·을구 항목을 구조화한다. 검토의 첫 호출이어야 한다.",
  "parameters": {
    "type": "object",
    "properties": { "document_id": { "type": "string", "description": "세션의 문서 ID. 생략하면 첫 문서" } },
    "required": []
  }
}
```

응답 `data`: Registry. 실패 `error`: `not_registry` / `parse_failed`.

#### summarize_rights 권리 합산

유스케이스 [[JSD-UC-001#UC-S2]] · 서비스 `RulesService.summarize`

```json
{
  "name": "summarize_rights",
  "description": "말소 제외 선순위 채권을 합산하고 주택 가격이 있으면 부채비율을 계산한다.",
  "parameters": {
    "type": "object",
    "properties": {
      "price_manwon": { "type": "integer" },
      "price_source": { "type": "string", "enum": ["trade_api", "registry_sale", "user_input"] },
      "other_tenants_manwon": { "type": "integer", "description": "다가구 세입자 보증금 합. 모르면 생략" },
      "vacant_rooms": { "type": "integer", "description": "빈 방 수. 다가구만" }
    },
    "required": []
  }
}
```

응답 `data`: RightsSummary. 등기부는 세션에서 자동으로 가져온다 (인자로 넘기지 않음).

#### check_signals 위험 신호·등급

유스케이스 [[JSD-UC-001#UC-S3]] · 서비스 `RulesService.check`

```json
{
  "name": "check_signals",
  "description": "규칙표로 위험 신호를 판정하고 등급을 낸다. 판정 결과는 바꿀 수 없다.",
  "parameters": {
    "type": "object",
    "properties": {
      "counterparty_name": { "type": "string" },
      "proxy_status": { "type": "string", "enum": ["self", "proxy_with_poa", "proxy_without_poa", "unknown"] },
      "illegal_building": { "type": "string", "enum": ["yes", "no", "unknown"] },
      "owner_type": { "type": "string", "enum": ["individual", "corporation", "unknown"] },
      "defaulter_match": { "type": "boolean" },
      "building_main_use": { "type": "string" }
    },
    "required": []
  }
}
```

응답 `data`: `{ signals: Signal[], grade: Grade }`.

#### lookup_price 시세 조회

유스케이스 [[JSD-UC-001#UC-S4]] · 서비스 `LookupService.price`

```json
{
  "name": "lookup_price",
  "description": "국토부 실거래가에서 최근 12개월 동일 단지·유사 면적 매매 평균을 찾는다.",
  "parameters": {
    "type": "object",
    "properties": {
      "address": { "type": "string" },
      "building_type": { "type": "string" },
      "building_name": { "type": "string" },
      "area_m2": { "type": "number" }
    },
    "required": ["address", "building_type"]
  }
}
```

응답 `data`: `{ price_manwon, count, period, source: "trade_api" }`. 실패 `error`: `no_trades` / `no_region_code` / `api_failed`.

#### lookup_building 건축물대장 조회

유스케이스 [[JSD-UC-001#UC-S5]] · 서비스 `LookupService.building`

```json
{
  "name": "lookup_building",
  "description": "건축HUB에서 주용도·대장 구분·가구수·세대수·사용승인일을 조회한다. 위반건축물 여부는 제공되지 않는다.",
  "parameters": {
    "type": "object",
    "properties": { "address": { "type": "string" } },
    "required": ["address"]
  }
}
```

응답 `data`: `{ main_use, ledger_kind: "general"|"collective", households, families, approved_at, multiple_candidates: bool }`.

#### match_defaulter 임대인 명단 대조

유스케이스 [[JSD-UC-001#UC-S6]] · 서비스 `LookupService.defaulter`

```json
{
  "name": "match_defaulter",
  "description": "HUG 상습 채무불이행자 공개 명단 스냅샷과 이름을 완전 일치로 대조한다.",
  "parameters": {
    "type": "object",
    "properties": { "name": { "type": "string" } },
    "required": ["name"]
  }
}
```

응답 `data`: `{ matched: bool, public_fields, snapshot_date, note: "동명이인 가능" }`. 실패 `error`: `no_snapshot`.

#### ask_user 사용자에게 묻기

유스케이스 [[JSD-UC-001#UC-S7]] · 서비스 `ReviewService.ask`

```json
{
  "name": "ask_user",
  "description": "부족한 정보를 사용자에게 한 번 묻는다. 검토가 멈추고 답이 오면 재개된다. 한 검토에 최대 5회.",
  "parameters": {
    "type": "object",
    "properties": {
      "kind": { "type": "string", "enum": ["illegal_building", "price", "tenants", "proxy", "owner_type", "land_registry", "other"] },
      "text": { "type": "string" },
      "why": { "type": "string" },
      "options": { "type": "array", "items": { "type": "string" } },
      "input_type": { "type": "string", "enum": ["choice", "number", "text", "file"] },
      "help_url": { "type": "string" }
    },
    "required": ["kind", "text", "why", "input_type"]
  }
}
```

응답 `data`: `{ question_id, answer }` (답이 온 뒤). 한도 초과 `error`: `question_limit`. 무응답 5분이면 `answer: "unknown"`.

#### write_report 의견서 작성

유스케이스 [[JSD-UC-001#UC-S8]] · 서비스 `ReportService.write`

```json
{
  "name": "write_report",
  "description": "등급·신호·합산·답변을 바탕으로 의견서를 만든다. 검토의 마지막 호출이어야 한다. 숫자와 등급은 입력값 그대로 쓴다.",
  "parameters": {
    "type": "object",
    "properties": {
      "agent_notes": { "type": "string", "description": "에이전트가 검토하며 느낀 특이점 한두 문장. 문장 생성 참고용" }
    },
    "required": []
  }
}
```

응답 `data`: Report. 서버가 단계별 할 일·특약을 규칙으로 고르고 LLM으로 문장을 만든 뒤 후검증한다.

### 4.1 에이전트 순서 규칙

| 규칙 | 내용 |
|---|---|
| 첫 호출 | `read_registry` 강제. 다른 도구를 먼저 부르면 거절 |
| 마지막 호출 | `write_report`. 필수 검토 항목([[JSD-PRD-001#R11]])이 미시도면 한 번 되돌려 보냄 |
| 한도 | 도구 20회, 질문 5회, 비용 300원. 도달 시 `write_report` 강제 |
| 병렬 | `lookup_price`·`lookup_building`·`match_defaulter`는 한 턴에 함께 부를 수 있다 |
| 진행 문장 | 도구 호출 전 에이전트가 한 줄(`thought`)을 내고, 서버가 도구 결과 요약(`tool_result`)을 만든다 |
| 금지 | 도구 목록 밖 이름, 등급·수치 변경 요청 |

## 5. 미결사항

- [ ] OpenAI 호출 방식 (Responses API vs Chat Completions) — SDK 문서 확인 후 확정. 함수 스키마는 동일
- [ ] SSE 재생 간격 0.3초가 적절한지
- [ ] `PATCH values`로 고친 값이 근거 하이라이트와 어긋날 때 표시 방식 ("사용자 수정" 배지)
- [ ] PDF 렌더링 방식 (서버 HTML→PDF vs 브라우저 인쇄)
