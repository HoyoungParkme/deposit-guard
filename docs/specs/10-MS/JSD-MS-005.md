---
doc_id: JSD-MS-005
type: MS
title: 보증금지킴 — 미니스펙 RulesService
status: draft
upstream: [JSD-DOM-002, JSD-PRD-001, JSD-RFQ-001, JSD-API-001, JSD-API-002]
---

# MINISPEC — RulesService

## 0. 이 문서가 다루는 것

`rules/service.py`의 함수 8개와 상수 파일 `rules/criteria.py`. 클래스 명세 [[JSD-DOM-002#RulesService]](4.5)의 시그니처를 함수 안쪽까지 내린 것이다. 합산·신호·등급이 여기서 정해지고, 에이전트와 문장 생성은 이 값을 바꾸지 못한다([[JSD-PRD-001#R6]]).

**순수 함수다.** DB·네트워크·모델·시계를 쓰지 않는다. 오늘 날짜도 입력(`today`)으로 받는다. 같은 입력이면 같은 출력이다. 예외를 던지지 않고, 모르는 것은 `UnknownItem`으로 남긴다([[JSD-PRD-001#R4]] · [[JSD-PRD-001#N3]]). `shared` 말고 아무것도 import하지 않는다.

형식은 [[JSD-MS-001]]과 같다. 타입(`RightsInput` `SignalInput` `EntryFact` `PropertyFact` `RightsSummary` `SignalCheck` `RiskSignal` `Grade` `UnknownItem` `ChecklistItem` `SeniorClaim` `OtherTenants` `PriceEstimate` `Criteria`)은 [[JSD-DOM-002]] 2.8이다. 상수 이름은 3장이다.

**표기** — `→` 반환·결과, `if 조건 → 결과 · else → 결과` 분기. **살아 있는 항목**은 `cancelled`가 false인 항목이다. **건물 항목**은 `entry_id`가 `land-`로 시작하지 않는 항목이다. 비율은 소수 넷째 자리에서 반올림한다.

---

## 1. 함수 목록

| 함수 | 한 줄 |
|---|---|
| [[#RulesService.summarize]] | 선순위 합산과 부채비율 |
| [[#RulesService.senior_claims]] | 등기 항목에서 선순위 권리 |
| [[#RulesService.other_tenants]] | 다가구 기존 세입자 가산 |
| [[#RulesService.price]] | 주택 가격 후보 고르기 |
| [[#RulesService.check]] | 신호 12개·확인 못 함·검토 항목·등급 |
| [[#RulesService.grade]] | 등급과 결정 항목 |
| [[#RulesService.criteria]] | 판정 기준 공개 |
| [[#RulesService.required_steps]] | 건물 종류별 필수 검토 항목 |

---

## 2. 함수

#### RulesService.summarize 선순위 합산과 부채비율

**시그니처** `summarize(inp: RightsInput) -> RightsSummary`

근거: [[JSD-PRD-001#R4]] · [[JSD-UC-001#UC-S2]] · [[JSD-DOM-001#RightsSummary]] · [[JSD-API-002#summarize_rights]]

**처리**
1. `claims = senior_claims(inp.entries, inp.amount_overrides)`
2. `mortgage = Σ amount where kind mortgage` · `lease = Σ amount where kind in (jeonse_right, lease_right)`
3. `tenants = other_tenants(inp)`
4. `total = mortgage + lease + tenants.added_manwon`
5. `est = price(inp)`
6. if `est` 있음 → `debt_ratio = round((total + inp.deposit_manwon) / est.amount_manwon, 4)` · `senior_ratio = round(total / est.amount_manwon, 4)` · else → 둘 다 None
7. `based_on` = `claims`의 `entry_id` + (가격 출처가 registry_sale이면 그 거래가액 항목) — 중복 없이, 등기부 순서
8. `→ RightsSummary(senior_mortgage_manwon = mortgage, senior_lease_manwon = lease, other_tenants_manwon = tenants.added_manwon, senior_total_manwon = total, deposit_manwon, price_manwon = est.amount_manwon, price_source = est.source, debt_ratio, senior_ratio, multi_household_unknown = (다가구이고 inp.other_tenants_manwon is None), based_on)`

**테스트 관점** 다세대 예시(을구 2.1억, 보증금 1.8억, 검토일 2026-09-17) → 합계 21000, 갑구 거래가액 50000(registry_sale), 부채비율 0.78, `based_on` [eul-1, gap-2] · 같은 예시에 직접 입력 30000 → 1.3 · 아파트 예시 → 말소된 `eul-1` 제외, 합계 12000 · 다가구 예시(부천, 건물 등기부만) → 근저당 30000 + 임차권 8000 + 가산 · 토지 등기부를 더하면 근저당 40000 · 같은 입력 두 번 → 같은 결과 · 가격 0 → None으로 본다(나누지 않는다)

---

#### RulesService.senior_claims 등기 항목에서 선순위 권리

**시그니처** `senior_claims(entries: list[EntryFact], amount_overrides: dict[str, int]) -> list[SeniorClaim]`

근거: [[JSD-DOM-001#SeniorClaim]] · [[JSD-RFQ-001#Q37]] 을구 합산

**처리**
1. 살아 있는 항목만 본다(건물·토지 모두)
2. 근저당 — `purpose_code == mortgage` 항목마다 `amount = amount_overrides.get(entry_id) ?? amount_manwon`
   - 이 항목을 부모로 둔 살아 있는 `mortgage_change` 부기가 있고 금액이 있으면 → 가장 뒤의 부기 금액을 쓴다(감액·증액 모두 변경 후 금액)
   - 부기에 직접 입력(`amount_overrides[부기 id]`)이 있으면 그것이 앞선다
   - `amount`가 None → 합산하지 않는다(확인 못 함은 `check`가 낸다)
3. 전세권 — `jeonse_right` · 기존 주택임차권 — `lease_right`. 금액 규칙은 같다(덮어쓰기 우선)
4. `→ SeniorClaim(kind, amount_manwon, entry_id, holder)` 목록, 등기부 순서

**테스트 관점** 말소된 근저당 → 없음 · 근저당 24000에 부기 변경 18000 → 18000 · 직접 입력 20000 → 20000 · 금액 None인 근저당 → 목록에 없음 · 토지 등기부 근저당도 들어간다

---

#### RulesService.other_tenants 다가구 기존 세입자 가산

**시그니처** `other_tenants(inp: RightsInput) -> OtherTenants`

근거: [[JSD-PRD-001#R4]] · [[JSD-DOM-001#OtherTenants]] · [[JSD-UC-001#UC-S2]] 3·3a

**처리**
1. if `inp.building_type != multi_household` → `OtherTenants(None, None, None, added_manwon 0)`
2. `known = inp.other_tenants_manwon ?? 0` · `vacant = inp.vacant_rooms ?? 0`
3. `per_room = PRIORITY_REPAYMENT`에서 `inp.region`에 맞는 금액(3장 지역 구분)
4. `→ OtherTenants(households None, known_deposit_manwon = inp.other_tenants_manwon, vacant_rooms = inp.vacant_rooms, added_manwon = known + vacant × per_room)`

**테스트 관점** 서울 다가구, 보증금 합 12000, 빈 방 2 → 12000 + 11000 · 부천 → 방당 4800 · 답이 없으면 가산 0(미확인 신호는 `check`가 낸다) · 다세대 → 0

---

#### RulesService.price 주택 가격 후보 고르기

**시그니처** `price(inp: RightsInput) -> PriceEstimate | None`

근거: [[JSD-DOM-001#PriceEstimate]] · [[JSD-API-001#GET/api/criteria]] price_order · [[JSD-RFQ-001#Q37]] 주택 가격

**처리** — 위에서부터 처음 있는 것(값이 1 이상)
1. `inp.override_price_manwon` → `PriceEstimate(amount, user_input)` — 화면 직접 입력
2. `inp.trade_price_manwon` → `PriceEstimate(amount, trade_api)` — 기간·건수는 루프가 `facts.price`에 둔 값이 의견서에 쓰인다
3. 갑구 거래가액 — 살아 있는 건물 항목 중 `ownership_transfer`이고 `price_manwon`이 있고 `today − received_at ≤ 365일`인 것 중 가장 뒤 → `PriceEstimate(price_manwon, registry_sale)`
4. `inp.user_price_manwon` → `PriceEstimate(amount, user_input)` — 대화에서 말한 값
5. 없으면 None

**테스트 관점** 직접 입력과 실거래가가 둘 다 있으면 직접 입력 · 다세대 예시(2026-02-10 거래가액 50000, 검토일 2026-09-17) → registry_sale 50000 · 같은 거래가 400일 전이면 사용하지 않는다 · 아무것도 없으면 None

---

#### RulesService.check 신호 12개·확인 못 함·검토 항목·등급

**시그니처** `check(inp: SignalInput) -> SignalCheck`

근거: [[JSD-PRD-001#R5]] · [[JSD-PRD-001#R11]] · [[JSD-UC-001#UC-S3]] · [[JSD-API-002#check_signals]]

**처리**
1. `owner` = 살아 있는 건물 항목 중 `section gap`이고 `ownership_preserve`·`ownership_transfer`인 가장 뒤 항목(없으면 None). 답변·조회에서 나온 신호의 근거 항목은 `owner.entry_id`다 — 신호마다 `entry_ids`가 비지 않는다
2. 신호 — 아래 **신호 규칙** 표를 위에서부터 적용해 `RiskSignal(code, severity, label, source, entry_ids, source_date)` 목록. `label`·`source`·`source_date`는 `SIGNALS` 상수
3. 확인 못 함 — 아래 **확인 못 함 규칙**으로 `UnknownItem(code, reason, how_to_check)`. `how_to_check`는 `CHECKLIST` 상수. 같은 code는 한 번만
4. `inp.untried`의 code마다 아직 없으면 `UnknownItem(code, no_data)`
5. 검토 항목 — `required_steps(inp.property.building_type)`의 code마다 `ChecklistItem(code, label, result, entry_ids)` · `result` = if 확인 못 함에 있음 → unknown · if 이 건에 해당 없음(아래 표의 "해당 없음") → n_a · else → ok · `entry_ids`는 그 항목을 본 등기 항목(없으면 owner)
6. `g = grade(signals, inp.rights, unknowns)`
7. `→ SignalCheck(grade = g, signals, checked, unknowns)`

**신호 규칙**

| code | 조건 | 심각도 | entry_ids |
|---|---|---|---|
| rights_infringement | 살아 있는 건물 갑구 항목에 seizure · provisional_seizure · injunction · provisional_registration · auction · notice_registration | danger | 그 항목들 |
| trust | 살아 있는 건물 갑구 항목의 `purpose_code == trust` 또는 `cause`에 `신탁` | danger | 그 항목들 |
| lease_registration | 살아 있는 을구 `lease_right`(건물·토지) | danger | 그 항목들 |
| owner_mismatch | `owner_matches_counterparty is False` · `proxy_status == proxy_with_poa`면 caution, 그 밖이면 danger | danger 또는 caution | owner |
| defaulter_listed | `defaulter_matched is True` | danger | owner |
| illegal_or_commercial | 건물 종류가 apartment가 아니고, `illegal_building == yes` 또는 `ledger_main_use`에 `근린생활시설` | danger | owner |
| land_right_issue | `property.land_right_unregistered` 또는 `property.separate_land_registry` | caution | owner |
| recent_mortgage | 살아 있는 `mortgage`(건물·토지) 중 `today − received_at ≤ 90일` | caution | 그 항목들 |
| frequent_transfer | 건물 `ownership_preserve`가 `today − received_at ≤ 365일`, 또는 최근 730일 안 `ownership_transfer`가 2개 이상 | caution | 해당 보존·이전 항목들 |
| corporate_landlord | `owner.holder_is_corporation is True` 또는 `owner_type == corporation` | caution | owner |
| senior_excess | `rights.senior_ratio > 0.54` | caution | `rights.based_on` |
| multi_household_unknown | 건물 종류 multi_household이고 `tenants_answered`가 false | caution | owner |

owner가 None이면 owner를 근거로 삼는 신호는 내지 않는다. 대신 `owner_match`가 확인 못 함이 된다.

**확인 못 함 규칙**

| code | 조건 | reason |
|---|---|---|
| trade_price | `rights.price_manwon is None` | `failures`에 lookup_price → lookup_failed · else → no_data |
| owner_match | `owner_matches_counterparty is None` 또는 owner None | no_data |
| defaulter_list | `defaulter_matched is None` | `failures`에 match_defaulter → lookup_failed · else → no_data |
| ledger_main_use | 건물 종류가 apartment가 아니고 `ledger_main_use is None` | `failures`에 lookup_building → lookup_failed · else → no_data |
| illegal_building | 건물 종류가 apartment가 아니고 `illegal_building == unknown` | no_answer |
| tenants | multi_household이고 `tenants_answered`가 false | no_answer |
| eul_sum | 살아 있는 mortgage · jeonse_right · lease_right 중 `amount_manwon`이 None인 것이 있음 | no_data |

**해당 없음** — `illegal_building`은 apartment면 n_a · `land_right`는 집합건물이 아니면 n_a · `tenants`·`land_registry`·`ledger_households`는 multi_household가 아니면 n_a.

**테스트 관점** 신호 12개마다 켜지는 입력과 꺼지는 입력 한 쌍씩(24건) · 소유자 불일치 + 위임장 있는 대리 → caution · 가압류가 말소됐으면 신호 없음 · 다가구 예시(검토일 2026-09-17) → lease_registration(danger), corporate_landlord(caution), 등급 danger · 모든 신호의 `entry_ids`가 비지 않는다 · untried에 ledger_main_use → 확인 못 함 no_data

---

#### RulesService.grade 등급과 결정 항목

**시그니처** `grade(signals: list[RiskSignal], rights: RightsSummary, unknowns: list[UnknownItem]) -> Grade`

근거: [[JSD-PRD-001#R6]] · [[JSD-DOM-001#Grade]] · [[JSD-UC-001#UC-S3]] 2·3·2a

**처리**
1. `danger_by` = severity danger 신호 code들 + (if `debt_ratio > 0.90` → `debt_ratio`)
2. if `danger_by` → `level danger`, `deciders = danger_by`
3. else → `caution_by` = severity caution 신호 code들 + (if `0.70 < debt_ratio ≤ 0.90` → `debt_ratio`) + (확인 못 함 중 `trade_price`·`owner_match`의 code)
4. if `caution_by` → `level caution`, `deciders = caution_by`
5. else → `level safe`, `deciders = []` — 확인 못 한 핵심 항목이 있으면 3에서 걸려 안전으로 가지 않는다
6. `→ Grade(level, deciders, unknowns = 모든 확인 못 함 code, rule_version = RULE_VERSION)`

경계는 `DEBT_RATIO`의 `danger 0.90`·`caution 0.70`이다. 90%는 초과해야 위험, 70%는 초과해야 주의다.

**테스트 관점** 비율 0.90 → caution · 0.9001 → danger · 0.70 → 안전(다른 조건 없을 때) · 가격 없음 → caution, deciders에 trade_price · 즉시 위험과 주의가 함께면 deciders는 즉시 위험 쪽만

---

#### RulesService.criteria 판정 기준 공개

**시그니처** `criteria(limits: Limits, topic: CriteriaTopic | None = None, signal_code: str | None = None) -> Criteria`

근거: [[JSD-API-001#GET/api/criteria]] · [[JSD-API-002#get_criteria]] · [[JSD-UI-001#UI-4]] · [[JSD-RFQ-001#Q38]]

**처리**
1. `full = Criteria(rule_version = RULE_VERSION, grades = GRADES, signals = SIGNALS 목록, debt_ratio = DEBT_RATIO, required_checks = REQUIRED_CHECKS, price_order = PRICE_ORDER, priority_repayment = PRIORITY_REPAYMENT, checklist = CHECKLIST, limits = limits의 공개 필드, sources = SOURCES)`
2. if `topic is None` → `→ full`
3. else → `topic`에 해당하는 필드만 남기고 나머지는 빈 값(빈 목록·None). `rule_version`은 늘 싣는다 · if `topic == signals` and `signal_code` → 그 code 하나만
4. 상수를 복사해 돌려준다. 돌려준 값을 고쳐도 상수가 바뀌지 않는다

**테스트 관점** 판정 기준 페이지 응답과 get_criteria(topic 없음)가 같다 · topic debt_ratio → `debt_ratio`와 `rule_version`만 · 없는 signal_code → 빈 목록 · 내부 한도(`ip_daily` `cost_krw` 등)가 응답에 없다

---

#### RulesService.required_steps 건물 종류별 필수 검토 항목

**시그니처** `required_steps(building_type: BuildingType) -> list[str]`

근거: [[JSD-PRD-001#R11]] · [[JSD-UC-001#UC-S9]] 4a

**처리** `→ REQUIRED_CHECKS["common"] + REQUIRED_CHECKS[building_type]`(순서 유지, 중복 없음). 도구 이름을 모른다 — 어느 호출이 시도인지는 루프의 `STEP_TOOLS`가 정한다([[JSD-MS-002#service_agent.dispatch]])

| 건물 종류 | 공통 뒤에 더하는 code |
|---|---|
| (공통) | owner_match · gap_infringement · trust · history · eul_sum · lease_jeonse · debt_ratio · defaulter_list |
| apartment | trade_price |
| multi_family_unit | trade_price · land_right · ledger_main_use · illegal_building |
| multi_household | trade_price · land_registry · ledger_households · illegal_building · tenants |
| officetel | trade_price · residential_use · illegal_building |
| other | trade_price · illegal_building |

**테스트 관점** 다가구 → 13개, `tenants` 포함 · 아파트에 `illegal_building` 없음 · 결과의 모든 code가 `CHECKLIST`와 `STEP_TOOLS`에 있다

---

## 3. criteria.py 상수

코드가 곧 공개 기준이다. 판정 기준 페이지와 get_criteria가 이 값을 그대로 내려보낸다. 값을 바꾸면 `RULE_VERSION`을 올린다.

| 이름 | 내용 |
|---|---|
| `RULE_VERSION` | `"2026-09-15"` |
| `DEBT_RATIO` | `formula` 문장, `danger 0.90`, `caution 0.70`, `senior 0.54` — 90%는 LH 권리분석·HUG 보증 불가 경계, 70%는 서울시 권장선, 54%는 HUG 선순위 기준 |
| `GRADES` | 위험·주의·안전의 조건 문장 3개([[JSD-PRD-001#R6]] 표) |
| `SIGNALS` | code → `severity` · `label`(쉬운 말 제목) · `source` · `source_date`. 2장 신호 규칙 12개 |
| `PRICE_ORDER` | `[trade_api, registry_sale, user_input]` — 직접 입력은 user_input이고 맨 앞에서 먼저 본다 |
| `PRIORITY_REPAYMENT` | 지역 구분 → 방당 금액(만원)·시행일. 서울 5500 · 과밀억제권역(인천 대부분, 경기 의정부·구리·하남·고양·수원·성남·안양·부천·광명·과천·의왕·군포, 남양주·시흥 일부)·세종·용인·화성·김포 4800 · 광역시(부산·대구·광주·대전·울산)·안산·광주(경기)·파주·이천·평택 2800 · 그 외 2500. 지역 이름은 `region` 앞부분과 가장 긴 일치 |
| `REQUIRED_CHECKS` | 2장 `required_steps` 표 |
| `CHECKLIST` | code → `label` · 단계 · 방식(A·B·C·D) · `how_to_check` 한 줄. [[JSD-RFQ-001#Q37]] 표 전체와 2장의 code 18개(owner_match · gap_infringement · trust · history · eul_sum · lease_jeonse · debt_ratio · defaulter_list · trade_price · land_right · ledger_main_use · ledger_households · residential_use · land_registry · illegal_building · tenants · landlord_type · tax_arrears) |
| `SOURCES` | 출처 기관·문서명·무엇을 정하는지·기준일 — LH 전세임대 권리분석, HUG 전세보증금반환보증 가입 요건, 주택임대차표준계약서(2023-10-06), 주택임대차보호법 시행령 최우선변제금, 서울시 전세 체크리스트 |

---

## 4. 미결사항

- [ ] 최우선변제금 지역 구분 — 과밀억제권역의 시 일부(남양주·시흥 등) 경계를 `region`의 동 이름까지 볼지. 지금은 시 단위로 4800을 준다(보수적으로 크게 잡는 쪽)
- [ ] 공시가격 × 140%([[JSD-RFQ-001#Q37]] 주택 가격 순서)는 조회 수단(V-World)이 없어 빠졌다
- [ ] 건물 종류 other의 필수 항목 — 단독주택을 여기로 볼지 multi_household로 볼지. 표 읽기가 `단독주택`을 other로 둔다([[JSD-MS-004#service_parse.read_property]])
- [ ] 소유자 판단에 쓰는 신호(`corporate_landlord` 등)의 근거 항목이 소유권 항목뿐이라 "이 줄이 쓰인 곳"에 답변·조회가 드러나지 않는다
- [ ] `recent_mortgage` 90일·`frequent_transfer` 1년·2년의 기준일이 검토일이다. 계약일 기준이어야 하는지
- [ ] 금액을 읽지 못한 근저당을 합산에서 빼고 `eul_sum` 확인 못 함으로만 알린다 — 부채비율이 실제보다 낮게 나올 수 있다. 등급을 주의 이상으로 올릴지
