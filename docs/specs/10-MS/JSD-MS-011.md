---
doc_id: JSD-MS-011
type: MS
title: 보증금지킴 — 미니스펙 요청 관문
status: draft
upstream: [JSD-DOM-002, JSD-DOM-003, JSD-SEQ-001, JSD-UC-001, JSD-INFRA-001]
---

# MINISPEC — 요청 관문 gate

## 0. 이 문서가 다루는 것

`gate/service.py`의 함수 6개. 클래스 명세 [[JSD-DOM-002]] 4.11의 함수 열을 함수 안쪽까지 내린 것이다. 검토가 생기기 전에 막을 것(파일 형식·크기·쪽수, IP 하루 한도)과 파싱 캐시를 맡는다([[JSD-UC-001#UC-S10]]).

형식은 [[JSD-MS-001]]과 같다. 타입(`Upload` `FileCheck` `ParsedDocument`)은 [[JSD-DOM-002]] 2.8, 테이블은 [[JSD-DOM-003#file_caches]]·[[JSD-DOM-003#ip_quotas]]이다.

**표기** — `→` 반환·결과, `!` 예외, `DB:` 자기 테이블 접근(`gate/crud.py`), `if 조건 → 결과 · else → 결과` 분기. `hmac_hex(s)`는 앱 비밀키 HMAC-SHA256 16진수다.

**이 파일이 지키는 것**
- 아무 도메인도 부르지 않는다
- 파일 바이트를 디스크에 쓰지 않는다. 쪽수는 메모리에서 센다
- IP 원문을 저장·로그하지 않는다. `ip_hash`만 둔다
- 한도는 한 SQL 문장으로 원자적으로 센다. 동시에 온 두 요청이 마지막 자리를 함께 받지 못한다

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#gate.check_file]] | 형식·크기·쪽수·암호 검사와 해시 |
| [[#gate.take_quota]] | IP 하루 한도 세기 |
| [[#gate.cached_html]] | 파싱 캐시 찾기 |
| [[#gate.remember_html]] | 파싱 캐시 넣기 |
| [[#gate.forget]] | 검토 삭제 때 캐시 지우기 |
| [[#gate.purge]] | 만료 캐시·지난 한도 행 지우기 |

---

## 2. 함수

#### gate.check_file 형식·크기·쪽수·암호 검사와 해시

**시그니처** `check_file(upload: Upload) -> FileCheck`

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-UC-001#UC-A1]] 2a · [[JSD-PRD-001#R1]]

**처리**
1. if `len(data) > LIMITS.file_mb × 1024 × 1024` → `! invalid_file(field file)`
2. 형식은 바이트 머리로 — `%PDF-` → `application/pdf` · `FF D8 FF` → `image/jpeg` · `89 50 4E 47 0D 0A 1A 0A` → `image/png` · 그 밖 → `! invalid_file`. 요청의 `media_type`·파일 이름은 믿지 않는다
3. PDF — `pypdf.PdfReader(BytesIO(data))` · 읽다 실패 → `! invalid_file` · if `is_encrypted` → `! invalid_file` · `pages = len(reader.pages)` · if `pages > LIMITS.pages` → `! invalid_file`
4. 이미지 → `pages = 1`
5. `→ FileCheck(file_sha256 = sha256(data) 16진수, media_type, page_count = pages)`

**예외** `invalid_file` 크기·형식·쪽수·암호·깨진 PDF. `detail`은 "PDF·JPG·PNG, 10MB·20쪽 이하만 올릴 수 있습니다"

**테스트 관점** 확장자만 pdf인 텍스트 파일 → invalid_file · 21쪽 → invalid_file · 암호 PDF → invalid_file · 예시 PDF → 쪽수와 해시 · 임시 파일이 생기지 않는다

---

#### gate.take_quota IP 하루 한도 세기

**시그니처** `take_quota(client_ip: str, file_sha256: str, is_sample: bool, today: date) -> None`

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-UC-001#UC-A1]] 2b · [[JSD-INFRA-001]] 5장 · [[JSD-DOM-002]] 6장 IP 한도

**처리** — 자기 짧은 트랜잭션
1. if `is_sample` → 끝
2. if `DB: exists file_caches where file_sha256 and is_sample` → 끝(예시 파일을 직접 올림)
3. `h = hmac_hex(client_ip)`
4. `DB: INSERT INTO ip_quotas (ip_hash, day, used) VALUES (h, today, 1) ON CONFLICT (ip_hash, day) DO UPDATE SET used = ip_quotas.used + 1 WHERE ip_quotas.used < LIMITS.ip_daily RETURNING used`
5. if 돌아온 행 없음 → `! rate_limited`
6. 커밋

**예외** `rate_limited` 그날 `LIMITS.ip_daily`(5)건 사용

**테스트 관점** 여섯 번째 → 429 · 동시 10요청 → 정확히 5개만 통과 · 예시는 행이 늘지 않는다 · 다음 날은 다시 1 · DB에 IP 원문이 없다

---

#### gate.cached_html 파싱 캐시 찾기

**시그니처** `cached_html(file_sha256: str) -> ParsedDocument | None`

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-UC-001#UC-A1]] 2c · [[JSD-UC-001#UC-S10]] 3·3a

**처리** `DB: file_caches where file_sha256 and (expires_at is null or expires_at > now)` · if 있음 → `ParsedDocument(html, page_count, billed_pages 0)` · else → None

**테스트 관점** 25시간 된 일반 캐시 → None · 예시 캐시는 오래돼도 있다

---

#### gate.remember_html 파싱 캐시 넣기

**시그니처** `remember_html(file_sha256: str, html: str, page_count: int, is_sample: bool) -> None`

근거: [[JSD-SEQ-001#SEQ-1]] · [[JSD-SEQ-001#SEQ-18]] · [[JSD-MS-001#ReviewService.create]]

**처리** — 부른 쪽 트랜잭션 안
`DB: INSERT file_caches (file_sha256, html, page_count, is_sample, created_at now, expires_at = null if is_sample else now + LIMITS.retention_hours) ON CONFLICT (file_sha256) DO UPDATE SET html, page_count, is_sample = file_caches.is_sample OR excluded.is_sample, expires_at = CASE WHEN file_caches.is_sample OR excluded.is_sample THEN null ELSE excluded.expires_at END, created_at = now`

**테스트 관점** 일반 캐시 위에 예시로 넣으면 만료 없음 · 예시 캐시 위에 일반으로 넣어도 예시 그대로

---

#### gate.forget 검토 삭제 때 캐시 지우기

**시그니처** `forget(file_sha256: str) -> None`

근거: [[JSD-SEQ-001#SEQ-15]] · [[JSD-DOM-002]] 5장 결정 3

**처리** `DB: delete file_caches where file_sha256 and is_sample = false` — 부른 쪽 트랜잭션 안

**테스트 관점** 예시 캐시는 남는다 · 없는 해시 → 아무 일 없음

---

#### gate.purge 만료 캐시·지난 한도 행 지우기

**시그니처** `purge(now: datetime) -> int`

근거: [[JSD-SEQ-001#SEQ-16]] · [[JSD-INFRA-001]] 8장

**처리** `a = DB: delete file_caches where expires_at < now` · `b = DB: delete ip_quotas where day < now의 날짜(Asia/Seoul)` → `a + b`

**테스트 관점** 어제 한도 행은 지워지고 오늘 행은 남는다 · 예시 캐시(`expires_at` null)는 남는다

---

## 3. 미결사항

- [ ] PDF 쪽수 세기에 `pypdf`를 쓴다 — [[JSD-INFRA-001]] 3장 기술 스택에 없다. 순수 파이썬이라 컨테이너에 더하기 쉽다
- [ ] 하루 경계를 한국 시간으로 둔다 — `today`는 부른 쪽(`ReviewService.create`)이 Asia/Seoul로 넘긴다
- [ ] 이미지 한 장 업로드는 등기부 전체가 아닐 가능성이 크다 — 형식은 받되 등기부 판정(갑구·을구)에서 걸린다
