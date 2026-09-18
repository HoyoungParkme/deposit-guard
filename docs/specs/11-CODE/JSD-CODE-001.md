---
doc_id: JSD-CODE-001
type: CODE
title: 보증금지킴 — 구현 계획
status: draft
upstream: [JSD-SCN-001, JSD-INFRA-001, JSD-DOM-002, JSD-DOM-003, JSD-API-001, JSD-API-002, JSD-UI-001, JSD-SEQ-001, JSD-MS-001, JSD-MS-002, JSD-MS-003, JSD-MS-004, JSD-MS-005, JSD-MS-006, JSD-MS-007, JSD-MS-008, JSD-MS-009, JSD-MS-010, JSD-MS-011, JSD-MS-012, JSD-MS-013, JSD-MS-014, JSD-MS-015]
---

# 구현 계획

## 0. 이 문서가 다루는 것

11단계 CODE. 미니스펙 15개의 함수 114개를 슬라이스 카드 6장으로 자르고, 카드마다 커밋을 기록한다. **에이전트는 카드 하나를 받아 카드 안 참조만 따라간다.** `구현 함수`에 없는 함수를 짜게 되면 카드가 틀린 것이다 — 카드와 미니스펙을 먼저 고친다.

**순서.** 시나리오([[JSD-SCN-001]]) 순서가 곧 카드 순서다. B1에서 등기부가 읽히고, B2에서 에이전트가 S1~S3의 의견서를 낸다. 대회 제출에는 B2까지가 핵심이고, B3·B4가 S4와 운영을 채운다. 일정은 제출일 2026-09-20 기준이다.

**카드는 호출 그래프로 닫혀 있다.** 카드의 함수가 부르는 함수는 같은 카드에 있거나, 선행 카드에서 끝났거나, 카드의 `스텁` 줄에 적혀 있다. 스텁은 둘뿐이다 — 빈 결과를 돌려주거나 `not_implemented`(501)를 낸다. 스텁을 푼 카드는 완료란에 적는다.

**작업 순서(카드 하나)** — 1. 선행 카드가 완료인지 본다 · 2. 참조를 연다(시나리오·유스케이스 → 시퀀스 → 미니스펙 → API·화면) · 3. 미니스펙 순서대로, 함수 하나에 커밋 하나. docstring에 항목 ID · 4. 미니스펙의 테스트 관점을 테스트로 · 5. 카드 E2E · 6. 완료란에 커밋 범위·테스트 수·되먹임을 적는다.

**화면은 미니스펙이 없다.** 화면의 명세는 [[JSD-UI-001]]의 배치·요소·규칙·시나리오이고, 요소 번호를 컴포넌트의 `data-el`로 남긴다. 파일 자리는 [[JSD-DOM-002]] 1장 `frontend/`다.

**진행 상황**: 카드 6장. 완료 1.

---

## 1. 슬라이스

#### A 기반

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-INFRA-001]] 2·3·5·6장 · [[JSD-INFRA-001#C2]] · [[JSD-INFRA-001#C9]] · [[JSD-DOM-002]] 1장·6장 · [[JSD-DOM-003]] |
| 구현 | 폴더 구조(클래스 명세 1장 그대로) · `backend/pyproject.toml`(uv: FastAPI · SQLAlchemy 2 async · asyncpg · Alembic · httpx · openai · sse-starlette · pypdf · pytest) · `docker-compose.yml`(app + Postgres 16, 호스트 포트 55432) · `Dockerfile`(프런트 빌드 → `backend/app/static` 2단계) · `.env.example` · `core/config.py`(환경 변수 · `LIMITS` · `PRICES`) · `core/db.py`(`hide_parameters`) · `core/errors.py`(코드 → HTTP 표, 에러 봉투) · `core/logging.py`(JSON · 주민번호 필터 · httpx WARNING) · `main.py`(라우터 등록 자리 · 스풀 크기 · 정적 파일·SPA 폴백 · `/health`) · `frontend/` Vite + React + TS + Tailwind 빈 앱과 `styles.css` 토큰 |
| DB | 엔티티 15개 SQLAlchemy 모델(클래스 명세 2장, 이름 겹침은 `…Row`) · Alembic `0001_initial` — 테이블 15개 · CHECK · 외래키(on delete cascade) · 인덱스([[JSD-DOM-003]] 3장) 한 번에 |
| 구현 함수 | [[JSD-MS-014#privacy.person_labels]] · [[JSD-MS-014#privacy.mask_text]] · [[JSD-MS-014#privacy.short_region]] · [[JSD-MS-014#factcheck.amounts]] · [[JSD-MS-014#factcheck.contradicts]] · [[JSD-MS-014#money.format_manwon]] · [[JSD-MS-012#HealthService.check]] · [[JSD-MS-013#openai.client]] · [[JSD-MS-013#openai.usage_krw]] — 9개 |
| API | [[JSD-API-001#GET/health]] |
| 화면 | 없음. `App.tsx` 경로 다섯과 빈 페이지 |
| 테스트 | 구현 함수의 테스트 관점 전부 · 마이그레이션 up/down · 에러 봉투에 예외 문자열이 없다 · 로그 필터가 주민번호 형태를 지운다 · `docker compose up`으로 `/health` 200 |
| 선행 | 없음 |
| 완료 | 2026-09-18 · main · 커밋 c379453..f65eb7d (7개 커밋) · 단위 및 통합 테스트 28개 통과 · PostgreSQL 16 마이그레이션 up/down 성공 · Docker db 및 /health 200 검증 완료 |

#### B1 등기부를 올리면 읽힌다

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-SCN-001#S1]] 1 · [[JSD-SCN-001#S4]] 1~2 · [[JSD-UC-001#UC-A1]] 1~3 · [[JSD-UC-001#UC-A2]] · [[JSD-UC-001#UC-S1]] · [[JSD-UC-001#UC-S10]] · [[JSD-SEQ-001#SEQ-1]] · [[JSD-SEQ-001#SEQ-12]] · [[JSD-SEQ-001#SEQ-C1]] · [[JSD-SEQ-001#SEQ-C2]] |
| 구현 함수 | [[JSD-MS-011#gate.check_file]] · [[JSD-MS-011#gate.take_quota]] · [[JSD-MS-011#gate.cached_html]] · [[JSD-MS-011#gate.remember_html]] · [[JSD-MS-010#SampleService.list]] · [[JSD-MS-010#SampleService.file]] · [[JSD-MS-013#UpstageParser.parse]] · [[JSD-MS-004#service_parse.read_extract]] · [[JSD-MS-004#service_parse.split_blocks]] · [[JSD-MS-004#service_parse.read_property]] · [[JSD-MS-004#service_parse.read_rows]] · [[JSD-MS-004#service_parse.read_holder]] · [[JSD-MS-004#service_parse.apply_cancellations]] · [[JSD-MS-004#service_parse.purpose_code]] · [[JSD-MS-004#service_parse.won_to_manwon]] · [[JSD-MS-004#service_parse.clean_html]] · [[JSD-MS-003#RegistryService.parse]] · [[JSD-MS-003#RegistryService.create_extract]] · [[JSD-MS-003#RegistryService.list]] · [[JSD-MS-003#RegistryService.get_html]] · [[JSD-MS-003#RegistryService.property]] · [[JSD-MS-003#RegistryService.owner]] · [[JSD-MS-003#RegistryService.holder_names]] · [[JSD-MS-003#RegistryService.entries]] · [[JSD-MS-003#RegistryService.read]] · [[JSD-MS-003#RegistryService.block_excerpt]] · [[JSD-MS-001#ReviewService.create]] · [[JSD-MS-001#ReviewService.parse_upload]] · [[JSD-MS-001#ReviewService.get]] · [[JSD-MS-001#ReviewService.require_live]] · [[JSD-MS-001#ReviewService.record]] — 31개 |
| API | [[JSD-API-001#POST/api/reviews]] · [[JSD-API-001#GET/api/reviews/{id}]] · [[JSD-API-001#GET/api/reviews/{id}/documents]] · [[JSD-API-001#GET/api/reviews/{id}/documents/{documentId}]] · [[JSD-API-001#GET/api/samples]] |
| 화면 | [[JSD-UI-001#UI-1]] · [[JSD-UI-001#UI-2]]의 상단 바와 문서 패널(원문 표시·강조)만 |
| 테스트 | 구현 함수의 테스트 관점 전부 · [[JSD-MS-004]] 3장 정답표 4장 · **E2E**: 예시 카드 선택 → 검토 시작 201 → 검토 화면에 문서 탭과 원문 → 같은 예시 두 번째는 업스테이지 가짜 호출 0 · 등기부가 아닌 PDF → 400, 행 없음 · 여섯 번째 업로드 → 429 |
| 스텁 | 검토 시작 라우터가 루프를 띄우지 않는다(B2가 푼다) · `ReportService.exists → false`(B2가 푼다) |
| 선행 | A |
| 완료 | — |

#### B2 에이전트가 검토하고 의견서가 나온다

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-SCN-001#S1]] · [[JSD-SCN-001#S2]] · [[JSD-SCN-001#S3]] · [[JSD-UC-001#UC-A1]] 4~8 · [[JSD-UC-001#UC-A3]] · [[JSD-UC-001#UC-S2]]~[[JSD-UC-001#UC-S9]] · [[JSD-SEQ-001#SEQ-2]]~[[JSD-SEQ-001#SEQ-8]] · [[JSD-SEQ-001#SEQ-11]] · [[JSD-SEQ-001#SEQ-13]] · [[JSD-SEQ-001#SEQ-14]] 의견서 보기 |
| 구현 함수 | [[JSD-MS-005#RulesService.summarize]] · [[JSD-MS-005#RulesService.senior_claims]] · [[JSD-MS-005#RulesService.other_tenants]] · [[JSD-MS-005#RulesService.price]] · [[JSD-MS-005#RulesService.check]] · [[JSD-MS-005#RulesService.grade]] · [[JSD-MS-005#RulesService.criteria]] · [[JSD-MS-005#RulesService.required_steps]] · [[JSD-MS-006#LookupService.price]] · [[JSD-MS-006#LookupService.building]] · [[JSD-MS-006#LookupService.defaulter]] · [[JSD-MS-006#LookupService.region_code]] · [[JSD-MS-006#LookupService.load_region_codes]] · [[JSD-MS-013#DataGoKrTradeSource.fetch]] · [[JSD-MS-013#DataGoKrLedgerSource.fetch]] · [[JSD-MS-007#CitationService.resolve_markers]] · [[JSD-MS-007#CitationService.cite]] · [[JSD-MS-007#CitationService.for_messages]] · [[JSD-MS-007#CitationService.for_report]] · [[JSD-MS-007#CitationService.usages]] · [[JSD-MS-007#CitationService.clear_report]] · [[JSD-MS-008#ReportService.write]] · [[JSD-MS-008#ReportService.pick_todos]] · [[JSD-MS-008#ReportService.pick_clauses]] · [[JSD-MS-008#ReportService.template_sentences]] · [[JSD-MS-008#ReportService.get]] · [[JSD-MS-008#ReportService.exists]] · [[JSD-MS-013#OpenAIAgentModel.complete]] · [[JSD-MS-013#OpenAISentenceWriter.write]] · [[JSD-MS-002#service_agent.run_review]] · [[JSD-MS-002#service_agent.run_tools]] · [[JSD-MS-002#service_agent.fetch_lookup]] · [[JSD-MS-002#service_agent.dispatch]] · [[JSD-MS-002#service_agent.check_stated]] · [[JSD-MS-002#service_agent.say]] · [[JSD-MS-002#service_agent.force_report]] · [[JSD-MS-002#service_agent.mask_for_model]] · [[JSD-MS-002#service_agent.tool_summary]] · [[JSD-MS-001#ReviewService.list_messages]] · [[JSD-MS-001#ReviewService.stream]] · [[JSD-MS-001#ReviewService.receive]] · [[JSD-MS-001#ReviewService.ask]] · [[JSD-MS-001#ReviewService.owner_matches]] · [[JSD-MS-001#ReviewService.summarize_and_store]] · [[JSD-MS-001#ReviewService.check_and_store]] · [[JSD-MS-001#ReviewService.write_report]] · [[JSD-MS-001#ReviewService.finish]] · [[JSD-MS-001#ReviewService.rights_input]] · [[JSD-MS-001#ReviewService.signal_input]] · [[JSD-MS-001#ReviewService.report_input]] — 50개 |
| API | [[JSD-API-001#GET/api/reviews/{id}/messages]] · [[JSD-API-001#GET/api/reviews/{id}/stream]] · [[JSD-API-001#POST/api/reviews/{id}/messages]](kind answer) · [[JSD-API-001#GET/api/reviews/{id}/blocks/{blockId}]] · [[JSD-API-001#GET/api/reviews/{id}/report]] · [[JSD-API-001#GET/api/criteria]] · 도구 9종 [[JSD-API-002#read_registry]] · [[JSD-API-002#summarize_rights]] · [[JSD-API-002#check_signals]] · [[JSD-API-002#lookup_price]] · [[JSD-API-002#lookup_building]] · [[JSD-API-002#match_defaulter]] · [[JSD-API-002#ask_user]] · [[JSD-API-002#get_criteria]] · [[JSD-API-002#write_report]] |
| 화면 | [[JSD-UI-001#UI-2]] 대화 전체(말풍선·도구 카드·질문 카드·숫자 요약·의견서 카드·인용 칩·이 줄이 쓰인 곳) · [[JSD-UI-001#UI-3]](패널 탭·단독 페이지, 직접 입력 제외) · [[JSD-UI-001#UI-4]] |
| 테스트 | 구현 함수의 테스트 관점 전부 · [[JSD-MS-005]] 신호 12개 켜짐·꺼짐 24건 · **E2E**(가짜 모델이 시나리오 순서로 도구를 부른다, 공공 API·HUG는 고정본, 명단 스냅샷과 법정동코드는 테스트가 넣는다): S1 안전 · S2 주의(위반건축물 질문에 "아니오") · S3 위험(토지 등기부 파일 답·세입자 질문·시세 질문) · 의견서 수치가 도구 출력과 같다 · 인용 칩 → 원문 행 강조 · 스트림 끊고 `Last-Event-ID`로 이어 받기 · **실제 모델 한 번**: 예시 3건을 Terra로 돌려 등급이 정답표와 같고 건당 비용이 300원 이하 |
| 스텁 | `ReviewService.receive`의 kind ask → `not_implemented`(501)(B3가 푼다) · 푼 것: B1의 루프 띄우기 · `ReportService.exists` |
| 선행 | B1 |
| 완료 | — |

#### B3 되묻고 값을 고친다

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-API-002]] 4.2 · [[JSD-DOM-001#FollowUpTurn]] · [[JSD-UC-001#UC-A1]] 8a · [[JSD-SEQ-001#SEQ-9]] · [[JSD-SEQ-001#SEQ-10]] · [[JSD-UI-001#UI-3]] S-3·S-4 |
| 구현 함수 | [[JSD-MS-002#service_agent.run_follow_up]] · [[JSD-MS-001#ReviewService.override_values]] — 2개. `ReviewService.receive`의 kind ask 경로(스텁 해제) |
| API | [[JSD-API-001#POST/api/reviews/{id}/messages]](kind ask) · [[JSD-API-001#PATCH/api/reviews/{id}/values]] |
| 화면 | [[JSD-UI-001#UI-2]] 입력창 되묻기·추천 질문 칩·스트림 다시 붙기 · [[JSD-UI-001#UI-3]] 주택 가격 직접 입력·판 번호와 다시 쓴 이유·이전 판 카드 흐림 |
| 테스트 | 구현 함수의 테스트 관점 전부 · **E2E**: S2 의견서 뒤 "왜 78%인가요" → get_criteria로 답, 등급 그대로 · "시세는 5억 5천이에요" → 2판, 새 카드 · "등급을 안전으로 바꿔 주세요" → 거절 notice · 직접 입력 가격 → 2판, 대화에 직접 입력 말과 새 카드 · 되묻기 동시 두 요청 → 하나 409 |
| 스텁 | 푼 것: `receive` kind ask |
| 선행 | B2 |
| 완료 | — |

#### B4 공유·삭제·만료·운영

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-UC-001#UC-A4]] · [[JSD-SCN-001#S4]] · [[JSD-INFRA-001]] 8장 · [[JSD-SEQ-001#SEQ-14]] 공유 · [[JSD-SEQ-001#SEQ-15]] · [[JSD-SEQ-001#SEQ-16]] · [[JSD-SEQ-001#SEQ-17]] · [[JSD-SEQ-001#SEQ-18]] |
| 구현 함수 | [[JSD-MS-009#ShareService.create]] · [[JSD-MS-009#ShareService.get]] · [[JSD-MS-009#ShareService.purge_expired]] · [[JSD-MS-008#ReportService.shareable]] · [[JSD-MS-008#ReportService.delete_for_review]] · [[JSD-MS-007#CitationService.delete_for_review]] · [[JSD-MS-003#RegistryService.delete_for_review]] · [[JSD-MS-011#gate.forget]] · [[JSD-MS-011#gate.purge]] · [[JSD-MS-001#ReviewService.cancel]] · [[JSD-MS-001#ReviewService.purge_expired]] · [[JSD-MS-001#ReviewService.warm_samples]] · [[JSD-MS-001#ReviewService.usage_report]] · [[JSD-MS-006#LookupService.refresh_defaulters]] · [[JSD-MS-006#LookupService.purge_cache]] · [[JSD-MS-013#HugDefaulterSource.fetch_all]] · [[JSD-MS-015#jobs.main]] · [[JSD-MS-015#jobs.purge]] · [[JSD-MS-015#jobs.refresh_defaulters]] · [[JSD-MS-015#jobs.load_region_codes]] · [[JSD-MS-015#jobs.warm_samples]] · [[JSD-MS-015#jobs.usage_report]] — 22개 |
| API | [[JSD-API-001#POST/api/reviews/{id}/shares]] · [[JSD-API-001#GET/api/shares/{token}]] · [[JSD-API-001#DELETE/api/reviews/{id}]] · 배치 명령 다섯 |
| 화면 | [[JSD-UI-001#UI-5]] · [[JSD-UI-001#UI-3]] 링크 공유·인쇄 · [[JSD-UI-001#UI-2]] 삭제·만료 안내 |
| 테스트 | 구현 함수의 테스트 관점 전부 · **E2E**: 공유 링크 → 가린 의견서, 원본 삭제 뒤에도 열림, 7일 뒤 410 · DELETE → 원문·대화·의견서·파싱 캐시 0행, 사용량은 남음, 도는 루프가 조용히 멈춤 · 시각을 25시간 옮기고 `jobs purge` → 410 · `jobs warm_samples` 뒤 예시 업로드가 한도에 안 세어짐 · `jobs refresh_defaulters` 0건 → 종료 코드 1, 스냅샷 유지 |
| 선행 | B3 |
| 완료 | — |

#### C 통합·배포

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-INFRA-001#C1]] · [[JSD-INFRA-001#C3]] · [[JSD-INFRA-001#C10]] · [[JSD-INFRA-001#C11]] · [[JSD-INFRA-001]] 8장 |
| 구현 | Azure 배포(컴퓨트 결정 뒤) · 환경 변수·비밀 · 배포 절차: 마이그레이션 → `jobs load_region_codes` → `jobs refresh_defaulters` → `jobs warm_samples` · 주기 실행(purge 시간 1회, refresh·usage_report 일 1회) · 외부 가동 감시 `/health` 1분 · `pg_dump` 백업(기한 있는 테이블은 데이터 제외) · `CLAUDE.md`·`README.md` · 제출 문구(사용한 AI 도구와 방식) |
| 테스트 | 공개 URL에서 S1~S4를 사람이 직접 · 휴대폰에서 가로 스크롤 없음 · S4 링크 → 의견서 3분 이내 · 일일 비용 점검 로그 · 컨테이너 재시작 뒤 데이터 유지 |
| 선행 | B4 |
| 완료 | — |

---

## 2. 통합 테스트

| 시나리오 | 슬라이스 | 검증하는 것 |
|---|---|---|
| [[JSD-SCN-001#S1]] 아파트·안전 | B2 | 질문 0개 · 부채비율·선순위비율이 도구 값 · 근거 보기 3곳 하이라이트 · 90초 이내(실제 모델) |
| [[JSD-SCN-001#S2]] 다세대·주의 | B2 · B3 | 건축물대장 뒤 위반건축물 질문 1개 · 시세 대체 문장 · 주의 · 되묻기로 2판 |
| [[JSD-SCN-001#S3]] 다가구·위험 | B2 | 질문 3개 순서 · 답 없이도 의견서 · 결론 첫 문장이 임차권등기 · 을구 3번 행 강조 |
| [[JSD-SCN-001#S4]] 3분 체험 | B1 · B2 · B4 · C | 예시 카드 → 의견서 3분 · 두 번째는 파싱만 캐시 · 판정 기준 페이지 · 폰 가로 스크롤 없음 |
| 개인정보 | B2 · B4 | 모델 입력·로그·공유본에 이름·지번·주민번호 형태가 없다([[JSD-PRD-001#N1]]) · 삭제 뒤 원문·캐시가 없다 |
| 비용·한도 | B1 · B2 · C | IP 5건 · 도구 20회 · 질문 5회 · 건당 300원 이하([[JSD-INFRA-001#C3]]) |

---

## 3. 커밋·PR 목록

슬라이스 카드의 `완료` 행에 기록한다 — 날짜 · 브랜치 · 커밋 범위(code·spec 수) · PR · 테스트 수 · 되먹임(고친 명세). 커밋 메시지는 한국어, 첫 줄 요약·둘째 줄부터 이유. 함수 커밋은 본문에 미니스펙 항목 ID를 적는다.

---

## 4. 미결사항

- [ ] 일정 — 참가 접수 2026-09-18, 제출 2026-09-20. B2까지가 제출의 최소선이다. B3·B4를 제출 전에 넣을지, 심사 기간(09-21~10-17) 중 배포 갱신으로 넣을지
- [ ] Azure 컴퓨트 종류([[JSD-INFRA-001#C10]]) — C 카드의 배포와 주기 실행 방식이 여기에 달렸다
- [ ] 화면 컴포넌트는 미니스펙이 없다 — [[JSD-UI-001]] 요소 번호와 `data-el` 대조로 확인한다. 대조 도구를 둘지
- [ ] 실제 모델 E2E(B2)의 비용 — 예시 3건 × 여러 번. 한도 안에서 몇 번 돌릴지
- [ ] 미니스펙 미결 중 구현 전에 정할 것 — HUG 명단 페이지 구조([[JSD-MS-013]]), Responses API 형식([[JSD-MS-013]]), 업스테이지 단가([[JSD-MS-001]])
