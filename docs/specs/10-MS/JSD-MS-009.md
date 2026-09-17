---
doc_id: JSD-MS-009
type: MS
title: 보증금지킴 — 미니스펙 ShareService
status: draft
upstream: [JSD-DOM-002, JSD-DOM-003, JSD-SEQ-001, JSD-API-001, JSD-UI-001]
---

# MINISPEC — ShareService

## 0. 이 문서가 다루는 것

`share/service.py`의 함수 3개. 클래스 명세 [[JSD-DOM-002#ShareService]](4.9)의 시그니처를 함수 안쪽까지 내린 것이다. 가린 의견서 사본을 7일 링크로 내보낸다([[JSD-PRD-001#R14]]).

형식은 [[JSD-MS-001]]과 같다. 타입(`Shareable` `ShareLink` `SharedView`)은 [[JSD-DOM-002]] 2.8, 테이블은 [[JSD-DOM-003#shared_opinions]]이다.

**표기** — `→` 반환·결과, `!` 예외, `DB:` 자기 테이블 접근(`share/crud.py`), `if 조건 → 결과 · else → 결과` 분기.

**이 파일이 지키는 것**
- 원본 검토·대화·원문·인용에 닿지 않는다. 받는 것은 `ReportService.shareable`의 사본뿐이다([[JSD-DOM-002]] 3.2)
- 공유본은 원본과 따로 산다. 원본이 지워져도 `expires_at`까지 남고, 원본이 다시 쓰여도 바뀌지 않는다
- 토큰은 추측할 수 없어야 한다. 로그인 없이 토큰이 곧 열람 권한이다

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#ShareService.create]] | 공유 링크 만들기 |
| [[#ShareService.get]] | 공유본 보기 |
| [[#ShareService.purge_expired]] | 만료 공유본 비우기 |

---

## 2. 함수

#### ShareService.create 공유 링크 만들기

**시그니처** `create(review_id: str) -> ShareLink`

근거: [[JSD-SEQ-001#SEQ-14]] · [[JSD-API-001#POST/api/reviews/{id}/shares]] · [[JSD-UC-001#UC-A4]] 3~5

**처리**
1. `s = ReportService.shareable(review_id)` — 의견서가 없으면 `! not_found`
2. `token = secrets.token_urlsafe(24)`(32자)
3. `expires_at = now + LIMITS.share_days일`
4. `DB: shared_opinions insert (token, report = s.report, subject = s.subject, expires_at)` — 토큰 충돌(UK 위반)이면 새 토큰으로 한 번 더
5. `→ ShareLink(token, url = "/s/" + token, expires_at)` — 화면이 자기 origin을 붙인다([[JSD-UI-001#UI-5]] 경로)

**예외** `not_found` 의견서 없음

**테스트 관점** 두 번 부르면 링크 둘 · `report`에 인용·특약·물어볼 것이 없다 · 원본을 다시 써도 공유본은 그대로 · 토큰 길이 32

---

#### ShareService.get 공유본 보기

**시그니처** `get(token: str) -> SharedView`

근거: [[JSD-SEQ-001#SEQ-14]] · [[JSD-API-001#GET/api/shares/{token}]] · [[JSD-UI-001#UI-5]]

**처리**
1. `row = DB: shared_opinions where token` · if 없음 → `! not_found`
2. if `row.expires_at ≤ now` or `row.report is null` → `! gone`
3. `→ SharedView(report, subject, expires_at)`

**예외** `not_found` 없는 토큰 · `gone` 만료

**테스트 관점** 원본 검토를 지운 뒤에도 200 · 7일 1초 뒤 410 · 비운 행 410 · 검토 경로 의존성(`require_live`)이 걸리지 않는다

---

#### ShareService.purge_expired 만료 공유본 비우기

**시그니처** `purge_expired(now: datetime) -> int`

근거: [[JSD-SEQ-001#SEQ-16]] · [[JSD-DOM-002]] 5장 결정 4

**처리** `DB: update shared_opinions set report = null, subject = null where expires_at < now and report is not null` → 비운 행 수. 행은 남긴다(410)

**테스트 관점** 만료 행만 비워진다 · 두 번 돌리면 두 번째는 0

---

## 3. 미결사항

- [ ] 비운 공유본 행을 언제 지울지 — [[JSD-DOM-002]] 7장 미결과 같다
- [ ] 한 검토에서 공유 링크를 몇 개까지 만들게 할지 — 지금은 제한이 없다
