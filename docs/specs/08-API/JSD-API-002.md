---
doc_id: JSD-API-002
type: API
title: 보증금지킴 — 에이전트 도구
status: draft
upstream: [JSD-UC-001, JSD-DOM-002, JSD-PRD-001]
---

# API 명세 MCP

## 0. 이 문서가 다루는 것

에이전트가 부르는 도구 8종의 함수 호출 스키마(OpenAI 형식)와 호출 순서 규칙. MCP 서버는 아니지만 "모델이 부르는 도구 목록"이라는 뜻에서 이 형식을 쓴다. REST는 [[JSD-API-001]]. DTO는 [[JSD-DOM-002]].

## 1. 규칙

- 모든 도구는 `{ "ok": bool, "data": ..., "error": str|null }` 봉투로 응답한다. 실패해도 예외를 던지지 않는다
- 등기부·세션 정보는 서버가 세션에서 꺼내 쓴다. 에이전트가 인자로 넘기지 않는다
- 도구 결과의 `data`는 [[JSD-DOM-002]] 5절 DTO를 JSON 직렬화한 것
- 에이전트는 도구를 부르기 전에 한 줄 판단 문장(`thought`)을 낸다. 서버는 도구 결과를 사람이 읽는 한 줄(`tool_result`)로 요약한다

## 2. 에러

| 코드 | 도구 | 뜻 |
|---|---|---|
| `not_registry` | read_registry | 갑구·을구가 없음 |
| `parse_failed` | read_registry | 파싱 서비스 실패 (재시도 후) |
| `no_trades` / `no_region_code` / `api_failed` | lookup_price | 거래 없음 / 법정동코드 없음 / API 실패 |
| `api_failed` | lookup_building | API 실패 |
| `no_snapshot` | match_defaulter | 명단 스냅샷 없음 |
| `question_limit` | ask_user | 질문 5회 초과 |
| `unknown_tool` | (루프) | 목록 밖 도구 |
| `tool_failed` | (루프) | 예상 밖 예외 |

## 3. 도구

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

응답 `data`: Registry.

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

응답 `data`: RightsSummary.

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

응답 `data`: `{ price_manwon, count, period, source: "trade_api" }`.

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

응답 `data`: `{ matched: bool, public_fields, snapshot_date, note: "동명이인 가능" }`.

#### ask_user 사용자에게 묻기

유스케이스 [[JSD-UC-001#UC-S7]] · 서비스 `AgentLoop.ask`

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

응답 `data`: `{ question_id, answer }` (답이 온 뒤). 무응답 5분이면 `answer: "unknown"`.

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

응답 `data`: Report. 서버 내부 전용 인자 `rebuild`(추출값 수정 후 재작성)는 에이전트에 노출하지 않는다.

## 4. 에이전트 순서

| 규칙 | 내용 |
|---|---|
| 첫 호출 | `read_registry` 강제. 다른 도구를 먼저 부르면 거절하고 안내 |
| 마지막 호출 | `write_report`. 필수 검토 항목([[JSD-PRD-001#R11]])이 미시도면 한 번 되돌려 보냄, 두 번째는 통과 |
| 한도 | 도구 20회, 질문 5회, 비용 300원. 도달 시 `write_report` 강제 |
| 병렬 | `lookup_price`·`lookup_building`·`match_defaulter`는 한 턴에 함께 부를 수 있다 |
| 텍스트 응답 | 도구 호출 없이 텍스트만 오면 "도구를 고르세요"로 되돌림. 3회면 `write_report` 강제 |
| 금지 | 도구 목록 밖 이름, 등급·수치 변경 요청 |

시스템 프롬프트 골자: 역할(LH 권리분석 담당자), 도구 8종 설명, 검토 항목 목록([[JSD-RFQ-001#Q37]]), 건물 종류별 필수 검토([[JSD-PRD-001#R11]]), 금지 사항, 진행 문장 형식("을구를 봅니다: …").

## 5. 미결사항

- [ ] OpenAI 호출 방식 (Responses API vs Chat Completions) — SDK 문서 확인 후 확정. 함수 스키마는 동일
- [ ] Terra의 병렬 도구 호출 지원 여부 확인 — 안 되면 순차로
- [ ] `check_signals`의 `defaulter_match`를 에이전트가 `match_defaulter` 결과에서 옮겨 적게 할지, 서버가 세션에서 자동으로 채울지 (후자 예정 — 에이전트 실수 방지)
