---
doc_id: JSD-MS-006
type: MS
title: 보증금지킴 — 미니스펙 LookupService
status: draft
upstream: [JSD-DOM-002, JSD-DOM-003, JSD-SEQ-001, JSD-API-002, JSD-UC-001]
---

# MINISPEC — LookupService

## 0. 이 문서가 다루는 것

`lookup/service.py`의 함수 7개. 클래스 명세 [[JSD-DOM-002#LookupService]](4.6)의 시그니처를 함수 안쪽까지 내린 것이다. 실거래가·건축물대장 조회와 HUG 명단 대조, 그리고 그 뒤의 법정동코드·캐시·스냅샷 관리다. 바깥 호출은 포트(`TradeSource` `LedgerSource` `DefaulterSource`)가 하고, 그 안쪽은 [[JSD-MS-013]]이다.

형식은 [[JSD-MS-001]]과 같다. 타입(`Property` `PriceLookup` `BuildingLedger` `DefaulterMatch` `Trade` `LedgerRow` `DefaulterRow` `RegionCodeRow`)은 [[JSD-DOM-002]] 2.8, 테이블은 [[JSD-DOM-003#lookup_caches]]·[[JSD-DOM-003#region_codes]]·[[JSD-DOM-003#defaulter_records]]이다.

**표기** — `→` 반환·결과, `!` 예외, `DB:` 자기 테이블 접근(`lookup/crud.py`), `if 조건 → 결과 · else → 결과` 분기. `hmac_hex(s)`는 `core/config.py`의 앱 비밀키로 만든 HMAC-SHA256 16진수다. `today()`는 생성자로 받은 시계다(테스트가 고정한다).

**이 파일이 지키는 것**
- 다른 서비스를 부르지 않는다. 주소·이름은 부른 쪽(`review`)이 넘긴다
- 지번·이름 원문을 로그·캐시 키·캐시 내용에 남기지 않는다. 결과(`DefaulterMatch`)에도 이름·공개 항목을 싣지 않는다
- 바깥 실패는 `AppError(api_failed)`로 올린다. 타임아웃 5초·재시도 1회는 어댑터 안이다
- 부를 때마다 자기 세션을 쓴다. 루프가 세 조회를 동시에 부른다([[JSD-MS-002#service_agent.fetch_lookup]])

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#LookupService.price]] | 최근 12개월 같은 단지·유사 면적 매매 평균 |
| [[#LookupService.building]] | 건축물대장 표제부 |
| [[#LookupService.defaulter]] | HUG 공개 명단 완전 일치 |
| [[#LookupService.region_code]] | 지번 주소 → 법정동코드 |
| [[#LookupService.refresh_defaulters]] | 명단 스냅샷 교체 |
| [[#LookupService.load_region_codes]] | 법정동코드 적재 |
| [[#LookupService.purge_cache]] | 만료 조회 캐시 삭제 |

---

## 2. 함수

#### LookupService.price 최근 12개월 같은 단지·유사 면적 매매 평균

**시그니처** `async price(target: Property, area_m2: float | None) -> PriceLookup`

근거: [[JSD-SEQ-001#SEQ-6]] · [[JSD-UC-001#UC-S4]] · [[JSD-API-002#lookup_price]] · [[JSD-RFQ-001#Q26]]

**처리**
1. `code = region_code(target.lot_address)` — `! no_region_code`. `lawd = code[:5]`
2. API 종류 — apartment → `apt` · multi_family_unit → `rh`(연립다세대) · officetel → `offi` · multi_household · other → `sh`(단독다가구)
3. 달 목록 — `today()`가 속한 달부터 거꾸로 12개월 `YYYYMM`
4. 달마다 동시에(최대 4개씩)
   1. `key = hmac_hex(f"trade|{종류}|{lawd}|{yyyymm}")` · `row = DB: lookup_caches where key and expires_at > now`
   2. if `row` → `trades = row.payload`
   3. else → `trades = await TradeSource.fetch(종류, lawd, yyyymm)` → `DB: lookup_caches upsert (kind trade, key, payload = trades, expires_at = now + 24시간)`. 지번 필드는 담지 않는다(`Trade`에 없다)
   4. 어댑터가 `api_failed`를 던지면 그 달은 실패로 표시
5. if 모든 달이 실패 → `! api_failed`
6. 거르기 — `area = area_m2 ?? target.exclusive_area_m2`
   - `sh`가 아니면 `norm(trade.building_name) == norm(target.building_name)`(건물명이 없으면 이 조건을 뺀다)
   - if `area` → `|trade.area_m2 − area| ≤ area × 0.03`
7. if 걸러진 거래 0건 → `! no_trades`
8. `price_manwon = round(평균 amount_manwon)` · `count` · `period = "{가장 이른 YYYY.MM}~{가장 늦은 YYYY.MM}"` · `samples` = 최근 5건 `{date, amount_manwon, area_m2}`
9. `→ PriceLookup(price_manwon, count, period, source trade_api, samples)`

**예외**

| 조건 | 에러 |
|---|---|
| 주소로 법정동을 못 찾음 | `no_region_code` |
| 12개월이 모두 실패 | `api_failed` |
| 걸러진 거래 없음 | `no_trades` |

**호출하는 것** [[#LookupService.region_code]] · `TradeSource.fetch`

**테스트 관점** 가짜 소스가 상계행복아파트 84.97㎡ 3건 → 평균·건수·기간 · 같은 달 두 번째 조회 → 소스 호출 0 · 아파트와 연립다세대가 같은 지역·달이어도 캐시가 섞이지 않는다 · 한 달만 실패하면 나머지로 낸다 · `lookup_caches.key`에 지역 코드·건물명이 보이지 않는다 · 면적 87.5(±3% 밖) 거래는 빠진다

---

#### LookupService.building 건축물대장 표제부

**시그니처** `async building(target: Property) -> BuildingLedger`

근거: [[JSD-SEQ-001#SEQ-6]] · [[JSD-UC-001#UC-S5]] · [[JSD-API-002#lookup_building]]

**처리**
1. `code = region_code(target.lot_address)` — `! no_region_code`. `sigungu = code[:5]` · `bjdong = code[5:]`
2. 지번 — `lot_address`의 마지막 낱말 `N` 또는 `N-M` → `bun = N을 4자리 0채움` · `ji = M 또는 0을 4자리 0채움`. 산 번지(`산` 접두)는 포트 인자에 대지 구분이 없어 다루지 않는다 → `! not_found`
3. `key = hmac_hex(f"building|{code}|{bun}|{ji}")` · 캐시 확인(price 4와 같다)
4. 없으면 `rows = await LedgerSource.fetch(code, bun, ji)` → `DB: lookup_caches upsert (kind building, payload = rows)` — `LedgerRow`에는 대지위치·도로명주소가 없다
5. if `rows` 비었음 → `! not_found`
6. 고르기 — 주건축물만 · if 한 건 → 그것 · else → `dong_name`이나 이름에 `target.building_name`이 들어간 것, 없으면 `main_use`가 주택(공동주택·단독주택·오피스텔)인 첫 행 · `multiple_candidates = 행이 둘 이상`
7. `→ BuildingLedger(main_use, ledger_kind, households, families, approved_at, multiple_candidates)`

**예외** `no_region_code` · `not_found` 대장 없음 · `api_failed`

**호출하는 것** [[#LookupService.region_code]] · `LedgerSource.fetch`

**테스트 관점** `심곡동 55-1` → `bun 0055`, `ji 0001` · 동 둘인 단지 → 건물명 맞는 동, `multiple_candidates` true · 상가 동과 주택 동 → 주택 동 · 캐시 적중이면 소스 호출 0

---

#### LookupService.defaulter HUG 공개 명단 완전 일치

**시그니처** `defaulter(name: str | None) -> DefaulterMatch`

근거: [[JSD-SEQ-001#SEQ-6]] · [[JSD-UC-001#UC-S6]] 2~3 · [[JSD-API-002#match_defaulter]]

**처리**
1. `snap = DB: max(snapshot_date) from defaulter_records` · if 없음 → `! no_snapshot`
2. if `name` 비었음 → `! no_name`
3. `n = DB: count where regexp_replace(name, '\s', '', 'g') = norm(name)`
4. `→ DefaulterMatch(matched = n > 0, match_count = n, snapshot_date = snap, note = "동명이인일 수 있습니다. 나이·주소로 직접 확인하세요")`. 일치한 행의 이름·나이·주소는 싣지 않는다

**테스트 관점** 스냅샷 없음 → no_snapshot · "홍 길동" → "홍길동" 행과 일치 · 결과 어디에도 이름이 없다 · 로그에 이름이 없다

---

#### LookupService.region_code 지번 주소 → 법정동코드

**시그니처** `region_code(lot_address: str | None) -> str`

근거: [[JSD-UC-001#UC-S4]] 1·1a

**처리**
1. if `lot_address` 비었음 → `! no_region_code`
2. `addr` = 지번 낱말(`^산?\d+(-\d+)?$`)을 뗀 앞부분 + 끝에 공백 하나
3. `DB: region_codes.code where is_active and addr LIKE name || ' %' order by length(name) desc limit 1` — 낱말 경계에서만 맞는다(`상계` ≠ `상계동`)
4. if 없음 → `! no_region_code` · else → code

**테스트 관점** `서울특별시 노원구 상계동 715` → 상계동 10자리 · `경기도 부천시 원미구 심곡동 55-1` → 심곡동 · 폐지된 코드만 맞으면 no_region_code · `서울특별시 노원구`까지만 맞는 주소 → 구 코드(동이 없으면 뒤 5자리 00000)

---

#### LookupService.refresh_defaulters 명단 스냅샷 교체

**시그니처** `async refresh_defaulters() -> int`

근거: [[JSD-SEQ-001#SEQ-17]] · [[JSD-UC-001#UC-S6]] 1·1a · [[JSD-INFRA-001]] 7장

**처리**
1. `rows = await DefaulterSource.fetch_all()` — 실패하면 예외 그대로 올린다(jobs가 실패로 기록)
2. if `rows` 0건 → 로그 `defaulter_refresh_empty` → `→ 0`(교체하지 않는다)
3. 트랜잭션 하나 — `DB: defaulter_records delete all` → 행마다 insert(`snapshot_date = today()`)
4. `→ len(rows)`. 로그에는 건수만

**테스트 관점** 소스가 중간 페이지에서 실패 → 이전 스냅샷 그대로 · 0건 → 이전 스냅샷 그대로, 0 반환 · 성공 → 모든 행의 `snapshot_date`가 오늘

---

#### LookupService.load_region_codes 법정동코드 적재

**시그니처** `load_region_codes(rows: list[RegionCodeRow]) -> int`

근거: [[JSD-UC-001#UC-S4]] 1 · 클래스 명세 4.15

**처리** 트랜잭션 하나에 `DB: region_codes upsert on conflict (code) do update set name, is_active` → 적재 행 수. 행을 지우지 않는다(폐지 코드는 `is_active false`로 남긴다)

**테스트 관점** 같은 파일 두 번 → 행 수 그대로 · 폐지 표시가 바뀌면 갱신

---

#### LookupService.purge_cache 만료 조회 캐시 삭제

**시그니처** `purge_cache(now: datetime) -> int`

근거: [[JSD-SEQ-001#SEQ-16]] · [[JSD-INFRA-001]] 8장

**처리** `DB: delete lookup_caches where expires_at < now` → 지운 행 수

**테스트 관점** 25시간 된 행만 지워진다

---

## 3. 미결사항

- [ ] 단독다가구 실거래가는 건물명·면적으로 거르지 않는다 — 같은 법정동의 모든 단독·다가구 거래 평균이 되어 이 집 가격과 멀다. 거래가 있어도 no_trades로 둘지(갑구 거래가액·질문으로 넘어가게)
- [ ] HUG 명단 페이지의 실제 열과 페이지 넘김 — 저장해 둔 파일은 상품 안내 페이지였다. 어댑터를 쓸 때 실제 명단 URL로 확인한다
- [ ] 건축물대장에서 주택 동을 고르는 규칙(주용도 이름 목록)은 예시 3건 주소로 실제 응답을 받아 확인한다
- [ ] 12개월 동시 조회 4개 — 공공데이터포털 초당 호출 제한에 걸리는지 확인한다
