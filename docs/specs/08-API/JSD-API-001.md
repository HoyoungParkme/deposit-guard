---
doc_id: JSD-API-001
type: API
title: 보증금지킴 — REST API
status: draft
upstream: [JSD-UC-001, JSD-UI-001, JSD-DOM-002, JSD-INFRA-001]
---

# API 명세 REST

## 0. 이 문서가 다루는 것

브라우저가 부르는 REST 엔드포인트 14개. 에이전트가 부르는 도구 8종은 [[JSD-API-002]]. DTO는 [[JSD-DOM-002]], 테이블은 [[JSD-DOM-001]].

## 1. 규칙

- 경로는 `/api/...`. 세션 ID는 uuid. 응답은 JSON, 시각은 ISO 8601 UTC
- 인증 없음. 세션 ID 자체가 열쇠 (추측 불가). 공유본은 별도 토큰
- 실패는 `{ "error": { "code": "...", "message": "..." } }`. 코드는 2절
- 파일 업로드는 multipart. 바이트는 메모리에서 파싱 API로 전달하고 디스크에 쓰지 않는다
- 응답 본문의 DTO는 [[JSD-DOM-002]] 5절을 그대로 JSON 직렬화한 것

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

## 4. 스키마

요청·응답에 쓰는 타입은 [[JSD-DOM-002]] 5절의 DTO(Report, Question, ReviewEvent 등)를 그대로 쓴다. 이 문서에 따로 정의하지 않는다.

## 5. 미결사항

- [ ] SSE 재생 간격 0.3초가 적절한지
- [ ] `PATCH values`로 고친 값이 근거 하이라이트와 어긋날 때 표시 방식 ("사용자 수정" 배지)
- [ ] PDF 렌더링 방식 (서버 HTML→PDF vs 브라우저 인쇄)
