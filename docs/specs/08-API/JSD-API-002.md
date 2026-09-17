---
doc_id: JSD-API-002
type: API
title: 보증금지킴 — 에이전트 도구 MCP
status: draft
upstream: [JSD-API-001, JSD-UI-001, JSD-DOM-001, JSD-PRD-001, JSD-UC-001]
---

# API 명세 MCP

## 0. 이 문서가 다루는 것

에이전트(LLM)가 부르는 도구 9종의 함수 스키마, 응답 형식, 호출 순서 규칙. MCP 서버를 따로 띄우지는 않지만 "모델이 부르는 도구 목록"이라는 뜻에서 이 형식을 쓴다. 브라우저와 서버 사이는 [[JSD-API-001]].

**3줄 요약.** 에이전트는 **무엇을 언제 확인할지**만 정한다. 등기부 사실·합산·판정은 도구가 내고, 이름·주소 같은 세션 정보는 서버가 꺼내 쓴다. 에이전트의 말풍선에 붙는 인용은 도구가 준 등기 항목 ID를 표식으로 달면 서버가 검증해 만든다.

**두 단계가 있다.**

| 단계 | 언제 | 끝나는 조건 | 도구 |
|---|---|---|---|
| 검토 | 검토 시작부터 의견서까지 | `write_report` 성공 | 9종 전부 |
| 되묻기 | 의견서 뒤 사용자가 입력할 때마다 | 에이전트가 답을 내면 한 차례 끝 | `get_criteria` `summarize_rights` `check_signals` `write_report` `lookup_price`. 서류를 올려 연 차례는 `read_registry`도 |

**도구 묶음.** 3절은 도구를 카드로 나열한다. 묶음은 이 표로 본다.

| 묶음 | 도구 |
|---|---|
| 읽기와 계산 | `read_registry` `summarize_rights` `check_signals` |
| 외부 확인 | `lookup_price` `lookup_building` `match_defaulter` |
| 대화 | `ask_user` `get_criteria` |
| 산출 | `write_report` |

## 1. 규칙

### 1.1 응답 봉투

모든 도구는 같은 봉투로 답한다. 실패해도 예외를 던지지 않고 루프는 계속된다.

```json
{ "ok": true, "data": {}, "error": null, "summary": "등기부 읽음: 다세대·연립 · 갑구 2건 · 을구 1건" }
```

- `summary`는 서버가 만든 사람이 읽는 한 줄이다. 그대로 도구 카드 메시지(`kind: tool`)가 된다
- `data`에 등기 사실이 들어가면 반드시 `entry_id`가 함께 온다. 에이전트는 이 ID로만 인용할 수 있다
- 3절 스키마는 MCP 표기대로 `inputSchema` 키에 적는다. OpenAI 함수 호출로 넘길 때 서버가 `parameters` 키로 옮긴다

### 1.2 세션 정보는 서버가 채운다

- 보증금·계약 형태·계약 상대방·주소·건물 종류는 인자로 받지 않는다. 서버가 검토 세션에서 꺼낸다
- 조회 도구(`lookup_price` `lookup_building` `match_defaulter`)는 인자가 없거나 선택 인자만 있다. 에이전트는 **언제** 부를지만 정한다
- 질문에 대한 답변은 서버가 기록해 두고 다음 도구 호출에 자동으로 반영한다

### 1.3 개인정보를 모델에 보내지 않는다

- 개인 소유자·권리자·채무자 이름은 `개인 A` `개인 B`로 바꿔 보낸다. 법인명(은행·건설사)은 그대로 둔다
- 소유자와 계약 상대방이 같은지는 서버가 계산해 `owner_matches_counterparty`로 넘긴다
- 주소는 시군구·동까지만 보낸다. 지번과 동호수는 보내지 않는다
- 주민번호 형태의 숫자는 어디에도 싣지 않는다 ([[JSD-PRD-001#N1]])

### 1.4 인용 표식

에이전트의 말풍선(`kind: say`)은 사실을 말할 때 그 근거 항목을 표식으로 단다.

```text
을구에는 근저당이 하나 있습니다. 채권최고액 2억 1,000만원, 접수일 2026년 7월 18일 {{entry:eul-2}}.
갑구 1·2번을 보면 신축 뒤 한 번 매매됐습니다 {{entry:gap-1,gap-2}}.
```

서버는 말풍선을 내보내기 전에 표식을 처리한다.

1. `entry_id`가 이 검토의 등기부에 실제로 있는지 확인한다
2. 있으면 `Citation`을 만들고 표식을 `{{c1}}`로 바꾼다 ([[JSD-API-001#GET/api/reviews/{id}/messages]])
3. 없으면 표식을 지우고 교정 수를 올린다. 그 문장에 금액·비율이 있으면 후검증에 넘긴다
4. 금액·비율·등급어가 도구 출력과 다르면 그 문장을 버리고 도구 출력으로 만든 문장으로 바꾼다 ([[JSD-PRD-001#R10]])

인용을 달 수 없는 사실 문장은 쓰지 않는다. 도구 결과를 설명하는 문장은 직전 도구 카드가 근거이므로 표식이 없어도 된다.

## 2. 에러

| 코드 | 도구 | 뜻 | 에이전트가 할 일 |
|---|---|---|---|
| `read_registry_first` | 전부 | 등기부를 읽기 전에 다른 도구를 부름 | `read_registry`를 먼저 부른다 |
| `no_region_code` | lookup_price · lookup_building | 주소로 법정동을 찾지 못함 | 가격은 다음 순서로, 대장은 확인 못 함으로 |
| `no_trades` | lookup_price | 같은 단지 거래 없음 | 등기부 거래가액으로 넘어간다 |
| `api_failed` | lookup_price · lookup_building | 공공 API 실패 (재시도 후) | 같은 조회를 반복하지 않는다 |
| `not_found` | lookup_building | 대장에 건물이 없음 | 확인 못 함으로 둔다 |
| `no_snapshot` | match_defaulter | 명단 스냅샷이 없음 | 확인 못 함으로 두고 안내한다 |
| `no_name` | match_defaulter | 대조할 이름이 없음 | 계약 상대방 이름을 묻거나 넘어간다 |
| `question_limit` | ask_user | 질문 5회 초과 | 묻지 않고 확인 못 함으로 둔다 |
| `required_unchecked` | write_report | 필수 검토 항목을 시도하지 않음 (한 번만) | 목록의 도구를 부른다 |
| `unknown_tool` | 루프 | 목록 밖 도구 | 목록 안에서 고른다 |
| `tool_failed` | 루프 | 예상 밖 예외 | 다음 도구로 넘어간다 |
| `tool_limit` | 루프 | 되묻기 한 차례에 도구 5회 초과. 그 호출은 부르지 않음 | 도구 없이 답한다 |

등기부가 아닌 파일과 파싱 실패는 도구 에러가 아니다. 파일을 올린 요청이 `not_registry`(400)·`parse_failed`(502)로 답한다 ([[JSD-API-001]] 2장).

## 3. 도구 정의


#### read_registry 등기부 읽기

유스케이스 [[JSD-UC-001#UC-S1]] · 개념 [[JSD-DOM-001#RegistryExtract]] [[JSD-DOM-001#RegistryEntry]] · 서비스 `RegistryService.read`

```json
{
  "name": "read_registry",
  "description": "올라온 등기부를 표제부·갑구·을구 항목으로 읽는다. 검토의 첫 호출이어야 한다. 토지 등기부가 추가로 올라오면 document_id를 넣어 다시 부른다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "document_id": { "type": "string", "description": "읽을 문서. 생략하면 아직 읽지 않은 첫 문서" }
    },
    "required": []
  }
}
```

응답 `data`

```json
{
  "document_id": "uuid",
  "doc_kind": "collective",
  "building": {
    "region": "서울 강서구 화곡동",
    "building_type": "multi_family_unit",
    "is_collective": true,
    "land_right_unregistered": false,
    "separate_land_registry": false
  },
  "owner_matches_counterparty": true,
  "gap": [
    { "entry_id": "gap-1", "rank_no": "1", "purpose_code": "ownership_preserve", "received_at": "2025-11-03", "holder": "화곡건설주식회사", "holder_is_corporation": true, "cancelled": false },
    { "entry_id": "gap-2", "rank_no": "2", "purpose_code": "ownership_transfer", "received_at": "2026-02-10", "price_manwon": 50000, "holder": "개인 A", "holder_is_corporation": false, "cancelled": false }
  ],
  "eul": [
    { "entry_id": "eul-1", "rank_no": "1", "purpose_code": "mortgage", "amount_manwon": 15600, "cancelled": true },
    { "entry_id": "eul-2", "rank_no": "2", "purpose_code": "mortgage", "received_at": "2026-07-18", "amount_manwon": 21000, "holder": "주식회사○○은행", "cancelled": false }
  ],
  "warnings": []
}
```

#### summarize_rights 권리 합산

유스케이스 [[JSD-UC-001#UC-S2]] · 개념 [[JSD-DOM-001#RightsSummary]] · 서비스 `RulesService.summarize`

```json
{
  "name": "summarize_rights",
  "description": "말소 제외 선순위를 채권최고액으로 합산하고 주택 가격이 있으면 부채비율을 낸다. 가격과 다른 세입자 보증금은 생략하면 서버가 조회 결과와 답변에서 정해진 순서로 채운다. 사용자가 대화에서 직접 말한 값만 인자로 넣는다. 서버가 이 검토의 사용자 메시지·답변에 그 값이 있는지 대조하고 없으면 그 인자를 버린다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "price_manwon": { "type": "integer", "description": "사용자가 대화에서 말한 시세. 없으면 생략" },
      "other_tenants_manwon": { "type": "integer", "description": "사용자가 말한 다른 세입자 보증금 합. 없으면 생략" },
      "vacant_rooms": { "type": "integer", "description": "다가구 빈 방 수. 사용자가 말했을 때만" }
    },
    "required": []
  }
}
```

응답 `data`: [[JSD-API-001]] 4.5절 `RightsSummary`. `based_on`에 합산에 쓴 `entry_id`가 온다.

#### check_signals 위험 신호와 등급

유스케이스 [[JSD-UC-001#UC-S3]] · 개념 [[JSD-DOM-001#RiskSignal]] [[JSD-DOM-001#Grade]] · 서비스 `RulesService.check`

```json
{
  "name": "check_signals",
  "description": "규칙표로 위험 신호와 등급을 정한다. 결과는 바꿀 수 없다. 인자는 없다. 질문 답변과 명단 대조 결과는 서버가 채운다. 대리 여부·위반건축물·임대인 유형은 ask_user의 답으로만 정해진다.",
  "inputSchema": { "type": "object", "properties": {}, "required": [] }
}
```

응답 `data`

```json
{
  "grade": { "level": "caution", "deciders": ["recent_mortgage", "frequent_transfer"], "unknowns": ["trade_price"], "rule_version": "2026-09-15" },
  "signals": [
    { "code": "recent_mortgage", "severity": "caution", "label": "근저당이 두 달 전에 설정됐습니다", "source": "국토교통부 전세사기 예방 자료", "entry_ids": ["eul-2"] },
    { "code": "frequent_transfer", "severity": "caution", "label": "신축 직후 첫 세입자입니다", "source": "국토교통부 전세사기 예방 자료", "entry_ids": ["gap-1", "gap-2"] }
  ]
}
```


#### lookup_price 실거래가 조회

유스케이스 [[JSD-UC-001#UC-S4]] · 개념 [[JSD-DOM-001#PriceEstimate]] · 서비스 `LookupService.price`

```json
{
  "name": "lookup_price",
  "description": "국토부 실거래가에서 최근 12개월 같은 단지·유사 면적 매매를 찾는다. 주소와 건물 종류는 서버가 채운다. lookup_building, match_defaulter와 한 턴에 함께 부를 수 있다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "area_m2": { "type": "number", "description": "전용면적을 알 때만. 생략하면 등기부 값" }
    },
    "required": []
  }
}
```

응답 `data`: `{ price_manwon, count, period, source: "trade_api", samples: [{ date, amount_manwon, area_m2 }] }`

#### lookup_building 건축물대장 조회

유스케이스 [[JSD-UC-001#UC-S5]] · 개념 [[JSD-DOM-001#BuildingLedger]] · 서비스 `LookupService.building`

```json
{
  "name": "lookup_building",
  "description": "건축HUB에서 주용도·대장 구분·가구수·세대수·사용승인일을 조회한다. 위반건축물 여부는 이 경로로 오지 않으므로 필요하면 ask_user로 묻는다. 주소는 서버가 채운다.",
  "inputSchema": { "type": "object", "properties": {}, "required": [] }
}
```

응답 `data`: `{ main_use, ledger_kind: "general"|"collective", households, families, approved_at, multiple_candidates }`

#### match_defaulter 공개 명단 대조

유스케이스 [[JSD-UC-001#UC-S6]] · 개념 [[JSD-DOM-001#DefaulterRecord]] · 서비스 `LookupService.defaulter`

```json
{
  "name": "match_defaulter",
  "description": "HUG 상습 채무불이행자 공개 명단과 이름을 완전 일치로 대조한다. 이름은 서버가 채우며 모델에는 결과만 온다. 일치는 동명이인일 수 있다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target": { "type": "string", "enum": ["owner", "counterparty"], "description": "생략하면 계약 상대방, 없으면 소유자" }
    },
    "required": []
  }
}
```

응답 `data`: `{ matched: bool, match_count, snapshot_date, note: "동명이인 가능. 나이·주소로 직접 확인" }`. 공개 항목(나이·주소·채무)은 모델에 보내지 않고 의견서 화면에서만 보인다.


#### ask_user 사용자에게 묻기

유스케이스 [[JSD-UC-001#UC-S7]] · 개념 [[JSD-DOM-001#Question]] · 화면 [[JSD-UI-001#UI-2]] · 서비스 `ReviewService.ask`

```json
{
  "name": "ask_user",
  "description": "서류와 조회로 알 수 없는 것을 한 번 묻는다. 대화가 멈추고 답이 오면 재개된다. 한 검토에 최대 5회. 이유 없는 질문은 하지 않는다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "kind": { "type": "string", "enum": ["illegal_building", "price", "tenants", "proxy", "owner_type", "land_registry", "other"] },
      "text": { "type": "string", "description": "질문 한 문장" },
      "why": { "type": "string", "description": "왜 묻는지 한 문장" },
      "input_type": { "type": "string", "enum": ["choice", "number", "text", "file"] },
      "options": { "type": "array", "items": { "type": "string" } },
      "help_url": { "type": "string" }
    },
    "required": ["kind", "text", "why", "input_type"]
  }
}
```

응답 `data`: `{ question_id, answer, document_id }`. 5분 무응답이면 `answer: "unknown"`. 파일 답변이면 `document_id`가 오고 에이전트는 `read_registry(document_id)`를 부른다.

#### get_criteria 판정 기준 조회

유스케이스 [[JSD-UC-001#UC-A3]] · 개념 [[JSD-DOM-001#OfficialCriterion]] · 화면 [[JSD-UI-001#UI-4]] · 서비스 `RulesService.criteria`

```json
{
  "name": "get_criteria",
  "description": "판정 규칙과 공식 출처를 조회한다. 사용자가 기준·이유를 되물을 때 규칙을 지어내지 않고 이 결과로만 답한다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "topic": { "type": "string", "enum": ["grade", "signals", "debt_ratio", "required_checks", "price_order", "priority_repayment", "limits", "sources"] },
      "signal_code": { "type": "string", "description": "특정 신호의 규칙만 볼 때" }
    },
    "required": ["topic"]
  }
}
```

응답 `data`: [[JSD-API-001#GET/api/criteria]] 응답 중 해당 부분과 `rule_version`.


#### write_report 의견서 작성

유스케이스 [[JSD-UC-001#UC-S8]] · 개념 [[JSD-DOM-001#Opinion]] · 화면 [[JSD-UI-001#UI-3]] · 서비스 `ReportService.write`

```json
{
  "name": "write_report",
  "description": "등급·신호·합산·답변으로 의견서를 만든다. 검토 단계의 마지막 호출이다. 되묻기 단계에서 값이 바뀌어 summarize_rights·check_signals를 다시 불렀다면 revision_reason을 넣어 다시 부른다. 숫자와 등급은 도구 출력 그대로 쓰인다.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_notes": { "type": "string", "description": "검토하며 본 특이점 한두 문장. 결론 문장 생성의 참고" },
      "revision_reason": { "type": "string", "description": "되묻기 단계에서 다시 쓸 때만. 예: 사용자가 시세 5억 5천을 알려 줌" }
    },
    "required": []
  }
}
```

응답 `data`: `{ grade, signal_count, unknown_count, corrections, rule_version }`. 의견서 전문은 모델에 돌려주지 않는다. 대화에는 의견서 카드(`kind: report`)가 뜨고 화면은 [[JSD-API-001#GET/api/reviews/{id}/report]]로 읽는다.

## 4. 에이전트 순서

### 4.1 검토 단계

| 규칙 | 내용 |
|---|---|
| 첫 호출 | `read_registry` 강제. 다른 도구를 먼저 부르면 `read_registry_first` |
| 마지막 호출 | `write_report`. 필수 검토 항목([[JSD-PRD-001#R11]])을 시도하지 않았으면 한 번 되돌려 보낸다. 두 번째는 통과 |
| 병렬 | `lookup_price`·`lookup_building`·`match_defaulter`는 한 턴에 함께 부를 수 있다 |
| 텍스트만 | 도구 없이 글만 내면 "도구를 고르세요"로 되돌린다. 3회면 `write_report`를 강제로 부른다 |
| 말풍선 | 도구를 부르기 전 판단 문장 하나를 `say`로 낸다. "무엇을 봅니다: 왜" 형식 |
| 한도 | 도구 20회, 비용 한도. 도달하면 `write_report`를 강제로 부른다 ([[JSD-PRD-001#R10]]). 질문 5회에 닿으면 더 묻지 않고 확인 못 함으로 진행한다 |
| 금지 | 목록 밖 도구, 등급·수치를 바꾸는 요청, 도구 결과 밖의 사실 |

### 4.2 되묻기 단계

| 규칙 | 내용 |
|---|---|
| 시작 | 의견서가 나온 뒤 사용자가 `ask`를 보낼 때마다 한 차례 |
| 답 | 텍스트 답이 기본이다. 사실 문장에는 인용 표식을 단다 |
| 규칙 질문 | "왜 90%인가" 같은 기준 질문은 `get_criteria`를 부른 뒤 그 결과로만 답한다 |
| 값 제공 | 사용자가 시세·세입자 보증금 같은 값을 주면 `summarize_rights` → `check_signals` → `write_report(revision_reason)` 순서로 다시 돌린다 |
| 서류 추가 | 사용자가 토지 등기부 등을 첨부하면 `read_registry(document_id)`부터 다시 돌린다 |
| 거절 | 등급·수치를 바꿔 달라는 요청은 도구를 부르지 않고 이유를 말한다. 메시지 코드 `out_of_scope` |
| 한도 | 한 차례에 도구 5회. 넘는 호출은 부르지 않고 `tool_limit`을 돌려준다. 검토 전체의 되묻기 횟수 한도는 미결 |

### 4.3 시스템 프롬프트 골자

- 역할: LH 전세임대 권리분석 담당자. 서류를 받아 훑고, 이 집·이 계약에서 무엇을 확인할지 스스로 정한다
- 도구 9종과 두 단계의 순서 규칙
- 검토 항목 전체 목록([[JSD-RFQ-001#Q37]])과 건물 종류별 필수 검토([[JSD-PRD-001#R11]]). 목록 밖 항목을 만들지 않는다
- 인용 표식 문법과 "인용을 달 수 없는 사실은 말하지 않는다"
- 말투: 존댓말, 쉬운 말, 한 말풍선 두세 문장. 법률 자문처럼 단정하지 않는다
- 개인 이름은 보이지 않으며 알려고 하지 않는다

## 5. 미결사항

- [ ] 되묻기 횟수 한도와 비용 — 한 차례 도구 5회는 정했고, 검토 전체에서 몇 번까지 받을지는 정하지 않았다
- [ ] OpenAI 호출 방식 — Responses API와 Chat Completions 중 무엇으로 할지. 함수 스키마는 같다
- [ ] 병렬 도구 호출 지원 여부 확인 — 안 되면 순차로 부르고 카드만 묶는다
- [ ] 인용 표식 문법 — `{{entry:eul-2}}` 형태를 모델이 안정적으로 지키는지 예시 3건으로 확인한다
- [ ] 개인 이름을 `개인 A`로 바꿀 때 같은 사람이 갑구·을구에 동시에 나오면 같은 라벨을 붙이는 규칙
- [ ] `match_defaulter` 일치 시 공개 항목(나이·주소)을 의견서 화면에만 보일지, 아예 보이지 않을지
