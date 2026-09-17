---
doc_id: JSD-MS-012
type: MS
title: 보증금지킴 — 미니스펙 HealthService
status: draft
upstream: [JSD-DOM-002, JSD-API-001, JSD-INFRA-001]
---

# MINISPEC — HealthService

## 0. 이 문서가 다루는 것

`core/health.py`의 함수 1개. 클래스 명세 [[JSD-DOM-002#HealthService]](4.12)를 함수 안쪽까지 내린 것이다. 외부 가동 감시가 1분마다 부른다([[JSD-INFRA-001#C1]]).

형식은 [[JSD-MS-001]]과 같다. 타입(`Health`)은 [[JSD-DOM-002]] 2.8이다.

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#HealthService.check]] | DB 연결 확인 |

---

## 2. 함수

#### HealthService.check DB 연결 확인

**시그니처** `async check() -> Health`

근거: [[JSD-API-001#GET/health]] · [[JSD-SEQ-001#SEQ-C1]]

**처리**
1. 새 세션으로 `SELECT 1`을 2초 제한으로 부른다
2. if 성공 → `Health(status "ok", db "ok", version = 환경 변수 APP_VERSION)` · else → `Health(status "degraded", db "fail", version)`
3. 예외 문자열을 싣지 않는다. 라우터가 degraded면 503을 낸다
4. 모델·외부 API는 부르지 않는다 — 1분마다 비용이 나기 때문이다

**테스트 관점** DB가 있으면 200 · DB를 끊으면 2초 안에 503 · 응답에 연결 문자열이 없다

---

## 3. 미결사항

- [ ] [[JSD-INFRA-001]] 8장은 헬스체크가 최근 에이전트 실패율도 본다고 적었다 — 지금은 DB만 본다([[JSD-DOM-002]] 7장 미결)
