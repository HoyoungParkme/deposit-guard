---
doc_id: JSD-MS-013
type: MS
title: 보증금지킴 — 미니스펙 바깥 연동
status: draft
upstream: [JSD-DOM-002, JSD-INFRA-001, JSD-API-002, JSD-RFQ-001]
---

# MINISPEC — 포트와 어댑터

## 0. 이 문서가 다루는 것

바깥 연동 어댑터 6개와 `infra/openai.py`의 함수 2개. 클래스 명세 [[JSD-DOM-002]] 4.13을 함수 안쪽까지 내린 것이다. 포트는 `typing.Protocol`이고, 서비스 생성자의 기본값이 이 어댑터다. 테스트는 가짜를 넣는다([[JSD-DOM-002]] 6장).

| 포트 | 어댑터 | 파일 | 바깥 |
|---|---|---|---|
| `AgentModel` | `OpenAIAgentModel` | `review/adapters/openai_agent.py` | OpenAI Responses API |
| `DocumentParser` | `UpstageParser` | `registry/adapters/upstage.py` | 업스테이지 Document Parse |
| `TradeSource` | `DataGoKrTradeSource` | `lookup/adapters/data_go_kr.py` | 국토부 실거래가 API 4종 |
| `LedgerSource` | `DataGoKrLedgerSource` | `lookup/adapters/data_go_kr.py` | 건축HUB 건축물대장 표제부 |
| `DefaulterSource` | `HugDefaulterSource` | `lookup/adapters/hug.py` | HUG 상습 채무불이행자 공개 명단 페이지 |
| `SentenceWriter` | `OpenAISentenceWriter` | `report/adapters/openai_writer.py` | OpenAI Responses API |

형식은 [[JSD-MS-001]]과 같다. 타입은 [[JSD-DOM-002]] 2.8이다.

**이 파일들이 지키는 것**
- 바깥 형식을 DTO로 바꾸는 데서 끝나고 판단하지 않는다
- 키·모델 ID·URL은 환경 변수다(`OPENAI_API_KEY` `OPENAI_MODEL` `UPSTAGE_API_KEY` `DATA_GO_KR_KEY` `HUG_DEFAULTERS_URL`). 값은 `.env.example`에 이름만 둔다([[JSD-INFRA-001#C7]])
- 로그에 요청 URL·본문·응답 본문을 남기지 않는다. httpx·httpcore 로거는 WARNING이다 — 서비스 키와 번·지가 URL에 있다
- 바깥 실패는 한 번 다시 시도한 뒤 정해진 코드로 올린다. 예외 문자열을 싣지 않는다
- HTTP 클라이언트는 `httpx.AsyncClient` 하나를 앱 수명 동안 쓴다(OpenAI는 SDK 클라이언트)

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#OpenAIAgentModel.complete]] | 에이전트 모델 한 차례 |
| [[#OpenAISentenceWriter.write]] | 의견서 문장 생성 |
| [[#UpstageParser.parse]] | 파일 → 업스테이지 HTML |
| [[#DataGoKrTradeSource.fetch]] | 한 달치 실거래가 |
| [[#DataGoKrLedgerSource.fetch]] | 건축물대장 표제부 |
| [[#HugDefaulterSource.fetch_all]] | 공개 명단 전체 |
| [[#openai.client]] | OpenAI 클라이언트 |
| [[#openai.usage_krw]] | 토큰 → 원화 |

---

## 2. 함수

#### OpenAIAgentModel.complete 에이전트 모델 한 차례

**시그니처** `async complete(history: list[dict], tools: list[dict]) -> ModelTurn`

근거: [[JSD-MS-002#service_agent.run_review]] · [[JSD-API-002]] 1.1 · [[JSD-INFRA-001#C7]]

**입력** 제공자와 무관한 history([[JSD-MS-002]] 0장 표)와 도구 스키마 목록(`name` `description` `inputSchema`). 되묻기 단계면 생성자에서 `follow_up True`

**처리**
1. history 옮기기 — system → `instructions` · user → `{"role": "user", "content": text}` · assistant 글 → `{"role": "assistant", "content": text}` · assistant 도구 호출 → call마다 `{"type": "function_call", "call_id", "name", "arguments": JSON 문자열}` · tool → `{"type": "function_call_output", "call_id", "output": content}`
2. 도구 옮기기 — `{"type": "function", "name", "description", "parameters": inputSchema}`
3. `client().responses.create(model = OPENAI_MODEL, instructions, input, tools, parallel_tool_calls = True)` · if `follow_up` → `text = {"format": {"type": "json_schema", "name": "answer", "schema": {answer: string, refused: boolean}}}`
4. 타임아웃 60초. 시간 초과·5xx·연결 오류면 한 번 더. 그래도 실패하면 예외를 올린다(루프가 error 메시지 + failed)
5. 응답 읽기 — `output`의 `function_call` 항목 → `ToolCall(id = call_id, name, arguments = JSON 파싱, 실패하면 {})` · `message`의 `output_text`를 이은 것 → `text`
6. if `follow_up` and 도구 호출 없음 → `text`를 JSON으로 읽어 `answer`·`refused` · 읽기 실패 → `text` 그대로, `refused False`
7. `→ ModelTurn(text 또는 None, tool_calls, refused, tokens_in = usage.input_tokens, tokens_out = usage.output_tokens)`

**테스트 관점** 가짜 SDK 응답(function_call 2개 + 글) → ToolCall 2개와 text · 깨진 arguments → `{}` · 되묻기에서 `{"answer": "…", "refused": true}` → refused true · 5xx 한 번 뒤 성공 → 정상 · 로그에 history가 없다

---

#### OpenAISentenceWriter.write 의견서 문장 생성

**시그니처** `async write(req: SentenceRequest) -> Sentences`

근거: [[JSD-MS-008#ReportService.write]] · [[JSD-UC-001#UC-S8]] 3·3a · [[JSD-PRD-001#R9]]

**처리**
1. `instructions` — "등급과 숫자를 바꾸지 말 것. 입력에 있는 금액·비율만 쓸 것. 결론 한 문장, 신호마다 쉬운 설명 한두 문장, 집주인·중개사에게 물을 질문 3~5개. 사실 뒤에는 입력의 entry_id로 `{{entry:…}}`를 단다. 존댓말, 법률 자문처럼 단정하지 않는다"
2. `input` — `SentenceRequest`를 JSON으로. 개인 이름은 처음부터 없다(`개인 A`)
3. `responses.create(model = OPENAI_MODEL, instructions, input, text.format = json_schema {conclusion: string, explanations: [{code: string, text: string}], questions: [string]})`
4. 타임아웃 30초 · 실패하면 한 번 더 · 그래도 실패 또는 JSON 읽기 실패 → 예외(부른 쪽이 템플릿으로 바꾼다)
5. `→ Sentences(conclusion, explanations = {code: text}, questions, tokens_in, tokens_out)`

**테스트 관점** 가짜 응답 JSON → Sentences · 스키마에 안 맞는 JSON → 예외 · 입력 JSON에 개인 이름·지번이 없다

---

#### UpstageParser.parse 파일 → 업스테이지 HTML

**시그니처** `async parse(data: bytes, media_type: str) -> ParsedDocument`

근거: [[JSD-MS-003#RegistryService.parse]] · [[JSD-UC-001#UC-S1]] 1·1a · [[JSD-INFRA-001#C8]]

**처리**
1. `POST https://api.upstage.ai/v1/document-digitization` — `Authorization: Bearer UPSTAGE_API_KEY`, multipart `document = (파일 이름 "upload", data, media_type)`, `model = document-parse`, `output_formats = ["html"]`, `ocr = auto`
2. 타임아웃 30초 · 시간 초과·5xx·연결 오류면 한 번 더 · 4xx는 다시 하지 않는다
3. 실패 → `! parse_failed`
4. 응답 `content.html`이 비었으면 → `! parse_failed`
5. `→ ParsedDocument(html = content.html, page_count = usage.pages, billed_pages = usage.pages)`
6. 바이트를 파일로 쓰지 않는다. 요청이 끝나면 참조를 놓는다

**테스트 관점** 저장해 둔 응답(`api 2.0`, `usage.pages 1`) → html과 1쪽 · 30초 넘김 두 번 → parse_failed · 422 → 다시 하지 않고 parse_failed

---

#### DataGoKrTradeSource.fetch 한 달치 실거래가

**시그니처** `async fetch(kind: str, region_code: str, year_month: str) -> list[Trade]`

근거: [[JSD-MS-006#LookupService.price]] · [[JSD-RFQ-001#Q26]]

**처리**
1. 경로 — `apt` → `RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade` · `rh` → `RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade` · `offi` → `RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade` · `sh` → `RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade`, 앞에 `https://apis.data.go.kr/1613000/`
2. 인자 — `serviceKey = DATA_GO_KR_KEY`, `LAWD_CD = region_code`, `DEAL_YMD = year_month`, `pageNo`, `numOfRows = 1000`
3. 타임아웃 5초 · 실패하면 한 번 더 · `header.resultCode`가 `000`이 아니면 실패 → `! api_failed`
4. XML `item`마다 — `cdealType`이 `O`(해제된 거래)면 버린다 · `amount_manwon = int(dealAmount에서 쉼표 뺌)` · `date = dealYear·dealMonth·dealDay` · `area_m2 = excluUseAr`(단독다가구는 `totalFloorAr`) · `building_name = aptNm · mhouseNm · offiNm`(단독다가구는 빈 문자열) · 지번 필드(`jibun` `bonbun` `bubun`)는 담지 않는다
5. `totalCount`가 한 쪽을 넘으면 다음 쪽을 이어 받는다
6. `→ Trade` 목록

**테스트 관점** 저장해 둔 아파트 XML → `시영3차(라이프)아파트` 45800 39.6㎡ · 해제 거래 제외 · `resultCode` 오류 → api_failed · 결과에 지번이 없다

---

#### DataGoKrLedgerSource.fetch 건축물대장 표제부

**시그니처** `async fetch(region_code: str, bun: str, ji: str) -> list[LedgerRow]`

근거: [[JSD-MS-006#LookupService.building]] · [[JSD-UC-001#UC-S5]]

**처리**
1. `GET https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo` — `serviceKey`, `sigunguCd = region_code[:5]`, `bjdongCd = region_code[5:]`, `platGbCd = 0`, `bun`, `ji`, `_type = json`, `numOfRows = 100`
2. 타임아웃 5초 · 한 번 더 · `resultCode`가 `00`이 아니면 → `! api_failed`
3. `items.item`이 객체 하나면 목록으로 감싼다 · 비었으면 `[]`
4. 행마다 — `main_use = mainPurpsCdNm` · `ledger_kind = collective if regstrGbCdNm == "집합" else general` · `households = hhldCnt` · `families = fmlyCnt` · `approved_at = useAprDay(YYYYMMDD, 공백이면 None)` · `dong_name = dongNm` · 주건축물(`mainAtchGbCd == "0"`)만 · `platPlc`·`newPlatPlc`는 버린다
5. `→ LedgerRow` 목록

**테스트 관점** 저장해 둔 JSON → `판매시설`·집합·`dongNm` · 결과에 대지위치·도로명주소가 없다 · item 하나짜리 응답 → 목록 한 개

---

#### HugDefaulterSource.fetch_all 공개 명단 전체

**시그니처** `async fetch_all() -> list[DefaulterRow]`

근거: [[JSD-MS-006#LookupService.refresh_defaulters]] · [[JSD-UC-001#UC-S6]] 1·1a · [[JSD-RFQ-001#Q17]]

**처리**
1. `page = 1`부터 `HUG_DEFAULTERS_URL`의 목록 페이지를 받는다. 응답 바이트를 `cp949`로 푼다
2. 목록 표의 행마다 이름·나이·주소·채무액·체납 기간 칸을 읽어 `DefaulterRow` · 채무액은 원 단위 문자열이면 만원으로
3. 행이 없는 쪽이 오거나 마지막 쪽 표시에 닿으면 멈춘다 · 안전장치로 500쪽에서 멈춘다
4. 쪽마다 타임아웃 10초 · 한 번 더 · 그래도 실패 → 예외(부른 쪽이 스냅샷을 그대로 둔다)
5. 표 머리글이 예상 열과 다르면 예외 — 구조가 바뀐 페이지를 조용히 0건으로 읽지 않는다
6. 로그에는 쪽 수와 건수만

**테스트 관점** 저장한 cp949 고정본 두 쪽 → 행 수 합 · 머리글이 바뀐 고정본 → 예외 · 2쪽에서 오류 → 예외, 부분 결과를 돌려주지 않는다

---

#### openai.client OpenAI 클라이언트

**시그니처** `client() -> AsyncOpenAI`

근거: [[JSD-INFRA-001#C7]]

**처리** 처음 부를 때 `AsyncOpenAI(api_key = OPENAI_API_KEY, max_retries = 0)`을 만들어 두고 같은 것을 돌려준다. 다시 시도는 어댑터가 정한다

**테스트 관점** 두 번 불러도 같은 객체

---

#### openai.usage_krw 토큰 → 원화

**시그니처** `usage_krw(tokens_in: int, tokens_out: int) -> int`

근거: [[JSD-INFRA-001#C3]] · [[JSD-INFRA-001]] 8장 비용 추정

**처리** `ceil(tokens_in × PRICES.openai_in_krw_per_1m / 1_000_000 + tokens_out × PRICES.openai_out_krw_per_1m / 1_000_000)`. 단가는 `core/config.py` `PRICES`(환율 반영한 원화)

**테스트 관점** 0·0 → 0 · 소수는 올림

---

## 3. 미결사항

- [ ] OpenAI 호출 방식 — Responses API로 적었다([[JSD-INFRA-001]] 9장 미결). 도구 호출과 JSON 스키마 출력을 한 요청에 함께 쓰는 형식은 첫 구현에서 SDK 문서로 확인한다
- [ ] `OPENAI_MODEL`의 실제 모델 ID(GPT-5.6 Terra)와 토큰 단가(`PRICES`)
- [ ] 단독다가구 실거래가의 면적 필드 이름과 연립다세대 건물명 필드(`mhouseNm`)를 실제 응답으로 확인한다
- [ ] HUG 명단 페이지 URL·쪽 넘김 인자·열 이름 — 고정본을 받아 확인한다([[JSD-MS-006]] 미결)
- [ ] 업스테이지 `ocr` 값 — 인터넷등기소 PDF는 글자가 들어 있어 `auto`로 충분한지, 사진 업로드는 `force`가 필요한지
