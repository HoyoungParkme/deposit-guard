---
doc_id: JSD-MS-015
type: MS
title: 보증금지킴 — 미니스펙 배치 명령
status: draft
upstream: [JSD-DOM-002, JSD-SEQ-001, JSD-INFRA-001]
---

# MINISPEC — 배치 명령 jobs

## 0. 이 문서가 다루는 것

`app/jobs.py`의 함수 6개. 클래스 명세 [[JSD-DOM-002]] 4.15의 명령 표를 함수 안쪽까지 내린 것이다. `python -m app.jobs <명령>`으로 돌리는 두 번째 입구다. 무엇이 주기를 돌릴지는 컴퓨트가 정해진 뒤 인프라 문서가 정한다([[JSD-INFRA-001#C10]]).

형식은 [[JSD-MS-001]]과 같다.

**표기** — `→` 반환·결과, `if 조건 → 결과 · else → 결과` 분기.

**이 파일이 지키는 것**
- 명령 하나가 서비스 메서드를 부르고 끝난다. 판단하지 않는다
- 로그는 JSON 한 줄 — `{job, ok, count, elapsed_ms}`. 이름·주소·예외 문자열을 남기지 않는다
- 실패하면 종료 코드 1이다. 주기 실행기가 실패를 감지한다
- 서비스는 앱과 같은 방식(같은 설정·엔진·포트 기본값)으로 만든다

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#jobs.main]] | 명령 이름으로 나눠 보내기 |
| [[#jobs.purge]] | 만료된 것 지우기 (시간 1회) |
| [[#jobs.refresh_defaulters]] | 명단 스냅샷 교체 (일 1회) |
| [[#jobs.load_region_codes]] | 법정동코드 적재 (배포 때) |
| [[#jobs.warm_samples]] | 예시 파싱 캐시 채우기 (배포 직후) |
| [[#jobs.usage_report]] | 어제 비용 점검 (일 1회) |

---

## 2. 함수

#### jobs.main 명령 이름으로 나눠 보내기

**시그니처** `main(argv: list[str]) -> int`

근거: [[JSD-DOM-002]] 4.15 · [[JSD-INFRA-001]] 8장

**처리**
1. `argv[0]`이 purge · refresh_defaulters · load_region_codes · warm_samples · usage_report 중 하나가 아니면 사용법을 출력 → `→ 2`
2. 엔진·세션·포트를 앱과 같게 만든다
3. `started` · 해당 함수를 `asyncio.run`으로 부른다
4. 성공 → 로그 `{job, ok true, count, elapsed_ms}` → `→ 0` · 예외 → 로그 `{job, ok false, error: 예외 종류, elapsed_ms}` → `→ 1`
5. 엔진을 닫는다

**테스트 관점** 모르는 명령 → 2 · 서비스가 예외 → 1, 로그에 예외 메시지가 없다

---

#### jobs.purge 만료된 것 지우기

**시그니처** `async purge() -> int`

근거: [[JSD-SEQ-001#SEQ-16]] · [[JSD-UC-001#UC-A1]] 9

**처리** `now = 지금` → `ReviewService.purge_expired(now)` → `ShareService.purge_expired(now)` → `LookupService.purge_cache(now)` → `gate.purge(now)` → 네 결과의 합. 하나가 실패해도 나머지는 돌리고, 끝에 실패가 있었으면 예외를 올린다

**테스트 관점** 공유본 비우기가 실패해도 조회 캐시는 지워지고 종료 코드 1

---

#### jobs.refresh_defaulters 명단 스냅샷 교체

**시그니처** `async refresh_defaulters() -> int`

근거: [[JSD-SEQ-001#SEQ-17]] · [[JSD-UC-001#UC-S6]] 1a

**처리** `n = LookupService.refresh_defaulters()` · if `n == 0` → 예외(빈 명단은 실패로 알린다 — 스냅샷은 그대로다) · else → n

**테스트 관점** 0건 → 종료 코드 1, 기존 스냅샷 유지

---

#### jobs.load_region_codes 법정동코드 적재

**시그니처** `async load_region_codes(path: str) -> int`

근거: [[JSD-MS-006#LookupService.load_region_codes]] · [[JSD-UC-001#UC-S4]] 1

**처리**
1. 파일은 행정표준코드관리시스템 법정동코드 전체자료(탭 구분, cp949). 머리글 `법정동코드` `법정동명` `폐지여부`
2. 행마다 `RegionCodeRow(code, name, is_active = 폐지여부 == "존재")` · 코드가 10자리 숫자가 아니면 건너뛴다
3. `→ LookupService.load_region_codes(rows)`

**테스트 관점** 고정본 5행(폐지 1) → 5, 하나는 `is_active false` · 머리글이 다르면 예외

---

#### jobs.warm_samples 예시 파싱 캐시 채우기

**시그니처** `async warm_samples() -> int`

근거: [[JSD-SEQ-001#SEQ-18]] · [[JSD-UC-001#UC-A2]] 4a

**처리** `→ ReviewService.warm_samples()` · if 결과가 예시 수보다 적으면 예외 — 배포 절차의 필수 단계라 빠지면 알려야 한다([[JSD-INFRA-001]] 8장)

**테스트 관점** 업스테이지 가짜가 한 건 실패 → 종료 코드 1

---

#### jobs.usage_report 어제 비용 점검

**시그니처** `async usage_report() -> int`

근거: [[JSD-INFRA-001#C3]] · [[JSD-INFRA-001]] 8장 비용 점검

**처리** `day = 어제(Asia/Seoul)` → `s = ReviewService.usage_report(day)` → 로그 `{job, day, reviews, failed, avg_cost_krw}` · if `s.avg_cost_krw > LIMITS.cost_krw` → 경고 로그 `cost_over_limit` → `→ s.reviews`

**테스트 관점** 평균 310원 → 경고 로그 한 줄 · 행 없는 날 → 0, 경고 없음

---

## 3. 미결사항

- [ ] 주기 실행기(Container Apps 작업·cron 컨테이너 등) — Azure 컴퓨트 결정 뒤([[JSD-INFRA-001#C10]])
- [ ] 비용 초과 경고를 로그 말고 어디로 알릴지(메일·메신저)
