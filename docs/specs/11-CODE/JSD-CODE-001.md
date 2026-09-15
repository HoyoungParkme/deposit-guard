---
doc_id: JSD-CODE-001
type: CODE
title: 보증금지킴 — 구현 계획
status: draft
upstream: [JSD-MS-001, JSD-API-001, JSD-API-002, JSD-UI-001, JSD-SCN-001, JSD-INFRA-001]
---

# 구현 계획

## 0. 이 문서가 다루는 것

슬라이스 9개(A, B1~B8), 통합 테스트, 커밋 기록. 순서는 "규칙(순수) → 읽기 → 루프 → 조회 → 의견서 → 화면 → 운영"이다. 규칙을 먼저 만드는 이유는 외부 의존 없이 테스트로 굳힐 수 있고, 예시 파일 3건의 기대 등급이 여기서 확정되기 때문이다.

| 날짜 | 슬라이스 |
|---|---|
| 09-15 | A, B1, B2 |
| 09-16 | B3, B4 |
| 09-17 | B5, B6 |
| 09-18 | B7, B8, 실사용자 테스트 |
| 09-19 | 버그·모바일·제출 문구·데모 영상 |
| 09-20 | 제출 |

## 1. 슬라이스

#### A 기반

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-INFRA-001]] [[JSD-DOM-001]] [[JSD-DOM-002]] |
| 구현 | 저장소 구조(`app/` 도메인 6개, `web/` Vite), uv·pyproject, FastAPI 앱·설정(env), SQLAlchemy 모델 9개 + Alembic 초기 마이그레이션, Dockerfile(멀티스테이지: web 빌드 → app), docker-compose(app, db), `/health`, 구조화 로그 + PII 필터, OpenAI·업스테이지 클라이언트 래퍼(타임아웃·재시도·usage 기록) |
| 테스트 | `/health` 200, 마이그레이션 up/down, 로그 필터가 주민번호 패턴 제거 |
| 선행 | 없음 |
| 완료 | — |

#### B1 규칙 도구

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-SCN-001#S1]] [[JSD-SCN-001#S2]] [[JSD-SCN-001#S3]] (기대 등급) |
| 구현 함수 | [[JSD-MS-001#RulesService.summarize]] · [[JSD-MS-001#RulesService.check]] · [[JSD-MS-001#RulesService.criteria]] |
| API | [[JSD-API-001#GET/api/criteria]] · 도구 [[JSD-API-002#summarize_rights]] [[JSD-API-002#check_signals]] |
| 화면 | — |
| 테스트 | 규칙 12개 양·음성, 경계 70/90/54, 다가구 가산, 말소 제외, 부기 감액, 예시 3건의 Registry 픽스처(JSON)로 안전·주의·위험이 나옴. criteria 스냅샷 = PRD R5·R6·R11 |
| 선행 | A |
| 완료 | — |

#### B2 등기부 읽기

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-SCN-001#S1]] 2 · [[JSD-UC-001#UC-S1]] |
| 구현 함수 | [[JSD-MS-001#RegistryService.read]] · [[JSD-MS-001#RegistryService.structure]] · [[JSD-MS-001#RegistryService.get_html]] · [[JSD-MS-001#GateService.validate_file]] |
| API | [[JSD-API-001#GET/api/reviews/{id}/document]] · 도구 [[JSD-API-002#read_registry]] |
| 화면 | — |
| 테스트 | 예시 PDF 3건 → 필수 필드 정답표 100% (B1 픽스처와 동일해야 함), 등기부 아닌 PDF → not_registry, 업스테이지 응답 녹화본으로 오프라인 테스트, block_id 전부 존재 |
| 선행 | A. **예시 등기부 PDF 3건 제작이 먼저** (HTML → PDF, 실제 등기부 레이아웃) |
| 완료 | — |

#### B3 에이전트 루프·SSE·질문

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-SEQ-001#SEQ-1]] [[JSD-SEQ-001#SEQ-2]] · [[JSD-UC-001#UC-S9]] [[JSD-UC-001#UC-S7]] |
| 구현 함수 | [[JSD-MS-001#AgentLoop.run]] · [[JSD-MS-001#AgentLoop.dispatch]] · [[JSD-MS-001#AgentLoop.emit]] · [[JSD-MS-001#AgentLoop.ask]] · [[JSD-MS-001#ReviewService.create]] · [[JSD-MS-001#ReviewService.get]] · [[JSD-MS-001#ReviewService.stream_events]] · [[JSD-MS-001#ReviewService.answer]] · [[JSD-MS-001#ReviewService.cancel]] |
| API | [[JSD-API-001#POST/api/reviews]] · [[JSD-API-001#GET/api/reviews/{id}]] · [[JSD-API-001#GET/api/reviews/{id}/events]] · [[JSD-API-001#POST/api/reviews/{id}/answers]] · [[JSD-API-001#DELETE/api/reviews/{id}]] · 도구 [[JSD-API-002#ask_user]] · 순서 규칙 [[JSD-API-002]] 4절 |
| 화면 | — (curl·pytest로 SSE 확인) |
| 테스트 | 가짜 LLM(스크립트된 tool_calls)으로 루프 단위 테스트: 첫 호출 강제, 텍스트 3회 → 강제 의견서, 20회 한도, 미시도 되돌림, 질문 한도·타임아웃, 병렬 tool_calls. 실제 Terra로 예시 1건 end-to-end 1회 (도구 호출 안정성 확인 → 불안정하면 Sol) |
| 선행 | B1, B2 |
| 완료 | — |

#### B4 외부 조회

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-SCN-001#S2]] 3~4 · [[JSD-UC-001#UC-S4]] [[JSD-UC-001#UC-S5]] [[JSD-UC-001#UC-S6]] |
| 구현 함수 | [[JSD-MS-001#LookupService.price]] · [[JSD-MS-001#LookupService.building]] · [[JSD-MS-001#LookupService.defaulter]] + HUG 스냅샷 스크립트 + 법정동코드 테이블 |
| API | 도구 [[JSD-API-002#lookup_price]] [[JSD-API-002#lookup_building]] [[JSD-API-002#match_defaulter]] |
| 화면 | — |
| 테스트 | 녹화된 API 응답으로 파싱·필터·캐시, 실패 사유 3종, 스냅샷 없음. 공공데이터 키 확보 후 실호출 1회 |
| 선행 | A. **공공데이터포털 키 발급 필요** — 미발급이면 도구가 항상 실패 사유를 돌려주고 사용자 입력으로 대체 |
| 완료 | — |

#### B5 의견서·특약·후검증

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-SCN-001#S1]] 6~8 · [[JSD-SCN-001#S3]] 8~10 · [[JSD-UC-001#UC-S8]] |
| 구현 함수 | [[JSD-MS-001#ReportService.write]] · [[JSD-MS-001#ReportService.verify_numbers]] · [[JSD-MS-001#ReviewService.override_values]] + 단계별 할 일 규칙표 상수(Q37) + 특약 템플릿(표준 1~3 원문 + 4종) |
| API | [[JSD-API-001#GET/api/reviews/{id}/report]] · [[JSD-API-001#PATCH/api/reviews/{id}/values]] · 도구 [[JSD-API-002#write_report]] |
| 화면 | — |
| 테스트 | todos 선택(다가구·근저당·unknown 조합), 특약 빈칸 채움, 후검증이 바뀐 숫자를 교체, LLM 실패 폴백, PATCH 후 등급 변화 |
| 선행 | B1, B3 |
| 완료 | — |

#### B6 화면 3개

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-UI-001#UI-1]] [[JSD-UI-001#UI-2]] [[JSD-UI-001#UI-3]] · [[JSD-SCN-001#S4]] |
| 구현 함수 | (프론트) 페이지 3개, SSE 훅(재접속·Last-Event-ID), 질문 카드 4종(choice·number·text·file), 원문 패널(HTML 렌더 + block_id 앵커 강조), 등급 배지, 숫자 카드, 할 일 탭, 복사 버튼, 디자인 토큰 CSS |
| API | [[JSD-API-001]] 3절 전부 (읽기) |
| 화면 | UI-1, UI-2, UI-3 |
| 테스트 | vitest: SSE 훅 재접속, 질문 카드 답변 전송. 수동: 390px 가로 스크롤 없음, 근거 보기 3초 내 강조 |
| 선행 | B3, B5 |
| 완료 | — |

#### B7 저장·공유·판정 기준·공유본 화면

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-UC-001#UC-A4]] · [[JSD-UI-001#UI-4]] [[JSD-UI-001#UI-5]] |
| 구현 함수 | [[JSD-MS-001#ShareService.create]] · PDF 렌더(브라우저 인쇄 CSS 우선, 안 되면 서버 HTML→PDF) |
| API | [[JSD-API-001#POST/api/reviews/{id}/shares]] · [[JSD-API-001#GET/api/shares/{token}]] · [[JSD-API-001#GET/api/reviews/{id}/report.pdf]] · [[JSD-API-001#GET/api/criteria]] |
| 화면 | UI-4, UI-5, UI-3 푸터 |
| 테스트 | 공유본에 이름·주민번호·동 이하 주소 없음, 만료 410, criteria 페이지가 코드 상수와 일치 |
| 선행 | B5, B6 |
| 완료 | — |

#### B8 예시 파일·한도·캐시·배포

| 항목 | 내용 |
|---|---|
| 근거 | [[JSD-UC-001#UC-A2]] [[JSD-UC-001#UC-S10]] · [[JSD-INFRA-001]] 8절 · [[JSD-SEQ-001#SEQ-3]] |
| 구현 함수 | [[JSD-MS-001#GateService.cache_key]] · [[JSD-MS-001#GateService.cache_lookup]] · [[JSD-MS-001#GateService.rate_check]] · [[JSD-MS-001#GateService.record_usage]] · 캐시 재생 스트림 · 만료 정리 배치 · 예시 워밍 스크립트 · Azure 배포 |
| API | [[JSD-API-001#GET/api/samples]] · [[JSD-API-001#GET/health]] |
| 화면 | UI-1 예시 카드 |
| 테스트 | 캐시 히트 시 LLM 호출 0, IP 6번째 거절, 예시 제외, 만료 정리 후 문서 없음. 배포 후 외부에서 예시 3건 실행·모니터 등록 |
| 선행 | B3, B6 |
| 완료 | — |

## 2. 통합 테스트

| 시나리오 | 슬라이스 | 검증하는 것 |
|---|---|---|
| [[JSD-SCN-001#S1]] 아파트 안전 | B1~B6 | 질문 0, 안전, 근거 3곳 강조, 90초 이내 |
| [[JSD-SCN-001#S2]] 다세대 주의 | B1~B6 | 시세 실패 → 등기부 매매가, 질문 1(위반건축물), 주의, 신호 2 |
| [[JSD-SCN-001#S3]] 다가구 위험 | B1~B6 | 토지 등기부 요청·세입자·시세 질문 3, 임차권등기 즉시 위험, 결론 첫 문장 |
| [[JSD-SCN-001#S4]] 심사위원 체험 | B6~B8 | 예시 카드 → 의견서 3분, 두 번째는 캐시 재생, 판정 기준·검토 기록 |
| 외부 API 전부 실패 | B3~B5 | 질문으로 대체, 의견서 나옴, 확인 못 함 표시 |
| LLM 텍스트만 응답 3회 | B3 | 강제 의견서, error 아님 |
| 실사용자 1건 (9/18) | 전부 | 실제 등기부, "도움 됐다" 한 줄 |

## 3. 커밋·PR 목록

슬라이스 카드의 `완료` 행에 기록. 브랜치는 `feat/a-foundation`, `feat/b1-rules` … 형식, dev로 squash 머지.

## 4. 미결사항

- [ ] 예시 등기부 PDF 3건 제작 방법·도구 (B2 선행). HTML 템플릿 → PDF 변환 예정
- [ ] 공공데이터포털·업스테이지 키 발급 시점 (B2·B4 실호출 테스트가 막힘)
- [ ] Azure 컴퓨트 확정 (B8)
- [ ] Terra 도구 호출 안정성 판정 기준 (예시 3건 × 3회 중 강제 의견서 발생 0회면 통과)
