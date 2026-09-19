"""RulesService 순수 계산·판정 도메인 서비스.

항목 ID: JSD-MS-005
근거: JSD-DOM-002 4.5, JSD-PRD-001 R4, R5, R6, R11, JSD-API-002
규칙: 순수 함수. DB·네트워크·시계 금지. today를 인자로 받음. shared 말고 import 금지.
"""

from __future__ import annotations
from datetime import date, timedelta
import copy

from app.shared.types import (
    BuildingType,
    ChecklistItem,
    CheckResult,
    Criteria,
    CriteriaTopic,
    EntryFact,
    Grade,
    GradeLevel,
    IllegalBuilding,
    Limits,
    OtherTenants,
    OwnerType,
    PriceEstimate,
    PriceSource,
    PropertyFact,
    ProxyStatus,
    PurposeCode,
    RightsInput,
    RightsSummary,
    RiskSignal,
    Section,
    SeniorClaim,
    SeniorKind,
    Severity,
    SignalCheck,
    SignalInput,
    UnknownItem,
    UnknownReason,
)
from app.domains.rules.criteria import (
    CHECKLIST,
    DEBT_RATIO,
    DEFAULT_PRIORITY_REPAYMENT,
    GRADES,
    PRICE_ORDER,
    PRIORITY_REPAYMENT_TIERS,
    REQUIRED_CHECKS,
    RULE_VERSION,
    SIGNALS,
    SOURCES,
    get_priority_repayment,
)


class RulesService:
    """순수 계산 및 위험 판정 서비스."""

    def summarize(self, inp: RightsInput) -> RightsSummary:
        """선순위 권리 합산과 부채비율을 계산한다.

        항목 ID: JSD-MS-005#RulesService.summarize
        근거: JSD-PRD-001#R4, JSD-UC-001#UC-S2, JSD-DOM-001#RightsSummary, JSD-API-002#summarize_rights
        """
        claims = self.senior_claims(inp.entries, inp.amount_overrides)
        mortgage = sum(c.amount_manwon for c in claims if c.kind == SeniorKind.mortgage)
        lease = sum(
            c.amount_manwon
            for c in claims
            if c.kind in (SeniorKind.jeonse_right, SeniorKind.lease_right)
        )
        tenants = self.other_tenants(inp)
        total = mortgage + lease + tenants.added_manwon

        est = self.price(inp)
        debt_ratio: float | None = None
        senior_ratio: float | None = None
        price_manwon: int | None = None
        price_source: PriceSource | None = None

        if est is not None and est.amount_manwon > 0:
            price_manwon = est.amount_manwon
            price_source = est.source
            debt_ratio = round((total + inp.deposit_manwon) / est.amount_manwon, 4)
            senior_ratio = round(total / est.amount_manwon, 4)

        # based_on: claims entry_id + (거래가액 항목 if registry_sale)
        based_on_list: list[str] = [c.entry_id for c in claims]
        if price_source == PriceSource.registry_sale:
            for e in inp.entries:
                if (
                    not e.entry_id.startswith("land-")
                    and not e.cancelled
                    and e.section == Section.gap
                    and e.purpose_code == PurposeCode.ownership_transfer
                    and e.price_manwon == price_manwon
                ):
                    if e.entry_id not in based_on_list:
                        based_on_list.append(e.entry_id)
                    break

        multi_household_unknown = (
            inp.building_type == BuildingType.multi_household
            and inp.other_tenants_manwon is None
        )

        return RightsSummary(
            senior_mortgage_manwon=mortgage,
            senior_lease_manwon=lease,
            other_tenants_manwon=tenants.added_manwon,
            senior_total_manwon=total,
            deposit_manwon=inp.deposit_manwon,
            price_manwon=price_manwon,
            price_source=price_source,
            debt_ratio=debt_ratio,
            senior_ratio=senior_ratio,
            multi_household_unknown=multi_household_unknown,
            based_on=based_on_list,
        )

    def senior_claims(
        self, entries: list[EntryFact], amount_overrides: dict[str, int]
    ) -> list[SeniorClaim]:
        """등기 항목에서 살아 있는 선순위 권리 목록을 추출한다.

        항목 ID: JSD-MS-005#RulesService.senior_claims
        근거: JSD-DOM-001#SeniorClaim, JSD-RFQ-001#Q37
        """
        claims: list[SeniorClaim] = []

        # 부기등기 맵 구축 (부모 entry_id -> 살아 있는 부기 항목들)
        sub_entries: dict[str, list[EntryFact]] = {}
        for e in entries:
            if not e.cancelled and e.parent_entry_id:
                sub_entries.setdefault(e.parent_entry_id, []).append(e)

        for e in entries:
            if e.cancelled:
                continue

            if e.purpose_code == PurposeCode.mortgage:
                # 1. 부기등기 변경 확인
                amount = amount_overrides.get(e.entry_id)
                if amount is None:
                    # 살아 있는 mortgage_change 부기등기가 있는지 확인
                    subs = sub_entries.get(e.entry_id, [])
                    change_subs = [
                        s
                        for s in subs
                        if s.purpose_code == PurposeCode.mortgage_change
                    ]
                    if change_subs:
                        # 가장 뒤의 부기등기
                        last_sub = change_subs[-1]
                        if last_sub.entry_id in amount_overrides:
                            amount = amount_overrides[last_sub.entry_id]
                        elif last_sub.amount_manwon is not None:
                            amount = last_sub.amount_manwon

                    if amount is None:
                        amount = e.amount_manwon

                if amount is not None:
                    claims.append(
                        SeniorClaim(
                            kind=SeniorKind.mortgage,
                            amount_manwon=amount,
                            entry_id=e.entry_id,
                            holder=e.holder,
                        )
                    )

            elif e.purpose_code == PurposeCode.jeonse_right:
                amount = amount_overrides.get(e.entry_id, e.amount_manwon)
                if amount is not None:
                    claims.append(
                        SeniorClaim(
                            kind=SeniorKind.jeonse_right,
                            amount_manwon=amount,
                            entry_id=e.entry_id,
                            holder=e.holder,
                        )
                    )

            elif e.purpose_code == PurposeCode.lease_right:
                amount = amount_overrides.get(e.entry_id, e.amount_manwon)
                if amount is not None:
                    claims.append(
                        SeniorClaim(
                            kind=SeniorKind.lease_right,
                            amount_manwon=amount,
                            entry_id=e.entry_id,
                            holder=e.holder,
                        )
                    )

        return claims

    def other_tenants(self, inp: RightsInput) -> OtherTenants:
        """다가구주택 기존 세입자 보증금 및 공실 최우선변제금을 합산한다.

        항목 ID: JSD-MS-005#RulesService.other_tenants
        근거: JSD-PRD-001#R4, JSD-DOM-001#OtherTenants, JSD-UC-001#UC-S2
        """
        if inp.building_type != BuildingType.multi_household:
            return OtherTenants(
                households=None,
                known_deposit_manwon=None,
                vacant_rooms=None,
                added_manwon=0,
            )

        known = inp.other_tenants_manwon if inp.other_tenants_manwon is not None else 0
        vacant = inp.vacant_rooms if inp.vacant_rooms is not None else 0
        per_room = get_priority_repayment(inp.region)

        return OtherTenants(
            households=None,
            known_deposit_manwon=inp.other_tenants_manwon,
            vacant_rooms=inp.vacant_rooms,
            added_manwon=known + vacant * per_room,
        )

    def price(self, inp: RightsInput) -> PriceEstimate | None:
        """우선순위에 따라 주택 가격 후보를 결정한다.

        항목 ID: JSD-MS-005#RulesService.price
        근거: JSD-DOM-001#PriceEstimate, JSD-API-001#GET/api/criteria price_order, JSD-RFQ-001#Q37
        """
        # 1. 화면 직접 입력
        if inp.override_price_manwon is not None and inp.override_price_manwon >= 1:
            return PriceEstimate(
                amount_manwon=inp.override_price_manwon,
                source=PriceSource.user_input,
            )

        # 2. 국토부 실거래가
        if inp.trade_price_manwon is not None and inp.trade_price_manwon >= 1:
            return PriceEstimate(
                amount_manwon=inp.trade_price_manwon,
                source=PriceSource.trade_api,
            )

        # 3. 갑구 최근 1년(365일) 실거래가액
        transfer_candidates: list[EntryFact] = []
        for e in inp.entries:
            if (
                not e.entry_id.startswith("land-")
                and not e.cancelled
                and e.section == Section.gap
                and e.purpose_code == PurposeCode.ownership_transfer
                and e.price_manwon is not None
                and e.price_manwon >= 1
                and e.received_at is not None
            ):
                diff = (inp.today - e.received_at).days
                if 0 <= diff <= 365:
                    transfer_candidates.append(e)

        if transfer_candidates:
            latest_transfer = transfer_candidates[-1]
            return PriceEstimate(
                amount_manwon=latest_transfer.price_manwon,  # type: ignore
                source=PriceSource.registry_sale,
            )

        # 4. 대화에서 말한 값
        if inp.user_price_manwon is not None and inp.user_price_manwon >= 1:
            return PriceEstimate(
                amount_manwon=inp.user_price_manwon,
                source=PriceSource.user_input,
            )

        return None

    def check(self, inp: SignalInput) -> SignalCheck:
        """12개 위험 신호, 미확인 항목, 필수 점검표, 등급을 종합 판정한다.

        항목 ID: JSD-MS-005#RulesService.check
        근거: JSD-PRD-001#R5, JSD-PRD-001#R11, JSD-UC-001#UC-S3, JSD-API-002#check_signals
        """
        # 1. 소유자 항목 식별 (살아 있는 건물 갑구 소유권보존/이전 중 가장 뒤 항목)
        owner_entry: EntryFact | None = None
        for e in inp.entries:
            if (
                not e.entry_id.startswith("land-")
                and not e.cancelled
                and e.section == Section.gap
                and e.purpose_code
                in (PurposeCode.ownership_preserve, PurposeCode.ownership_transfer)
            ):
                owner_entry = e

        owner_entry_ids = [owner_entry.entry_id] if owner_entry else []

        signals: list[RiskSignal] = []

        # 2. 신호 12개 판정
        # rights_infringement: 살아 있는 건물 갑구 항목에 압류, 가압류, 가처분, 가등기, 경매, 예고등기
        infringement_codes = (
            PurposeCode.seizure,
            PurposeCode.provisional_seizure,
            PurposeCode.injunction,
            PurposeCode.provisional_registration,
            PurposeCode.auction,
            PurposeCode.notice_registration,
        )
        infringement_entries = [
            e.entry_id
            for e in inp.entries
            if not e.entry_id.startswith("land-")
            and not e.cancelled
            and e.section == Section.gap
            and e.purpose_code in infringement_codes
        ]
        if infringement_entries:
            cfg = SIGNALS["rights_infringement"]
            signals.append(
                RiskSignal(
                    code="rights_infringement",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=infringement_entries,
                    source_date=cfg["source_date"],
                )
            )

        # trust: 신탁 등기
        trust_entries = [
            e.entry_id
            for e in inp.entries
            if not e.entry_id.startswith("land-")
            and not e.cancelled
            and e.section == Section.gap
            and (e.purpose_code == PurposeCode.trust or (e.cause and "신탁" in e.cause))
        ]
        if trust_entries:
            cfg = SIGNALS["trust"]
            signals.append(
                RiskSignal(
                    code="trust",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=trust_entries,
                    source_date=cfg["source_date"],
                )
            )

        # lease_registration: 임차권등기명령 (건물·토지 을구)
        lease_reg_entries = [
            e.entry_id
            for e in inp.entries
            if not e.cancelled
            and e.section == Section.eul
            and e.purpose_code == PurposeCode.lease_right
        ]
        if lease_reg_entries:
            cfg = SIGNALS["lease_registration"]
            signals.append(
                RiskSignal(
                    code="lease_registration",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=lease_reg_entries,
                    source_date=cfg["source_date"],
                )
            )

        # owner_mismatch: 소유자 불일치
        if inp.owner_matches_counterparty is False and owner_entry_ids:
            severity = (
                Severity.caution
                if inp.proxy_status == ProxyStatus.proxy_with_poa
                else Severity.danger
            )
            cfg = SIGNALS["owner_mismatch"]
            signals.append(
                RiskSignal(
                    code="owner_mismatch",
                    severity=severity,
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=owner_entry_ids,
                    source_date=cfg["source_date"],
                )
            )

        # defaulter_listed: 악성 임대인
        if inp.defaulter_matched is True and owner_entry_ids:
            cfg = SIGNALS["defaulter_listed"]
            signals.append(
                RiskSignal(
                    code="defaulter_listed",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=owner_entry_ids,
                    source_date=cfg["source_date"],
                )
            )

        # illegal_or_commercial: 위반건축물 또는 근린생활시설
        if (
            inp.property.building_type != BuildingType.apartment
            and (
                inp.illegal_building == IllegalBuilding.yes
                or (inp.ledger_main_use and "근린생활시설" in inp.ledger_main_use)
            )
            and owner_entry_ids
        ):
            cfg = SIGNALS["illegal_or_commercial"]
            signals.append(
                RiskSignal(
                    code="illegal_or_commercial",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=owner_entry_ids,
                    source_date=cfg["source_date"],
                )
            )

        # land_right_issue: 대지권 미등기 또는 별도등기
        if (
            inp.property.land_right_unregistered
            or inp.property.separate_land_registry
        ) and owner_entry_ids:
            cfg = SIGNALS["land_right_issue"]
            signals.append(
                RiskSignal(
                    code="land_right_issue",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=owner_entry_ids,
                    source_date=cfg["source_date"],
                )
            )

        # recent_mortgage: 최근 90일 내 근저당
        recent_mortgage_entries = [
            e.entry_id
            for e in inp.entries
            if not e.cancelled
            and e.purpose_code == PurposeCode.mortgage
            and e.received_at is not None
            and 0 <= (inp.today - e.received_at).days <= 90
        ]
        if recent_mortgage_entries:
            cfg = SIGNALS["recent_mortgage"]
            signals.append(
                RiskSignal(
                    code="recent_mortgage",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=recent_mortgage_entries,
                    source_date=cfg["source_date"],
                )
            )

        # frequent_transfer: 잦은 소유권 변동 (1년 내 보존 또는 2년 내 2회 이상 이전)
        frequent_transfer_entries: list[str] = []
        # 건물 보존등기 <= 365일
        for e in inp.entries:
            if (
                not e.entry_id.startswith("land-")
                and not e.cancelled
                and e.purpose_code == PurposeCode.ownership_preserve
                and e.received_at is not None
                and 0 <= (inp.today - e.received_at).days <= 365
            ):
                frequent_transfer_entries.append(e.entry_id)

        # 건물 이전등기 <= 730일
        recent_transfers = [
            e.entry_id
            for e in inp.entries
            if not e.entry_id.startswith("land-")
            and not e.cancelled
            and e.purpose_code == PurposeCode.ownership_transfer
            and e.received_at is not None
            and 0 <= (inp.today - e.received_at).days <= 730
        ]
        if len(recent_transfers) >= 2:
            for tid in recent_transfers:
                if tid not in frequent_transfer_entries:
                    frequent_transfer_entries.append(tid)

        if frequent_transfer_entries:
            cfg = SIGNALS["frequent_transfer"]
            signals.append(
                RiskSignal(
                    code="frequent_transfer",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=frequent_transfer_entries,
                    source_date=cfg["source_date"],
                )
            )

        # corporate_landlord: 법인 임대인
        is_corp = False
        if owner_entry and owner_entry.holder_is_corporation is True:
            is_corp = True
        elif inp.owner_type == OwnerType.corporation:
            is_corp = True

        if is_corp and owner_entry_ids:
            cfg = SIGNALS["corporate_landlord"]
            signals.append(
                RiskSignal(
                    code="corporate_landlord",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=owner_entry_ids,
                    source_date=cfg["source_date"],
                )
            )

        # senior_excess: 선순위 채권 54% 초과
        if inp.rights.senior_ratio is not None and inp.rights.senior_ratio > 0.54:
            cfg = SIGNALS["senior_excess"]
            signals.append(
                RiskSignal(
                    code="senior_excess",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=inp.rights.based_on,
                    source_date=cfg["source_date"],
                )
            )

        # multi_household_unknown: 다가구 세입자 미확인
        if (
            inp.property.building_type == BuildingType.multi_household
            and not inp.tenants_answered
            and owner_entry_ids
        ):
            cfg = SIGNALS["multi_household_unknown"]
            signals.append(
                RiskSignal(
                    code="multi_household_unknown",
                    severity=cfg["severity"],
                    label=cfg["label"],
                    source=cfg["source"],
                    entry_ids=owner_entry_ids,
                    source_date=cfg["source_date"],
                )
            )

        # 3. 확인 못 함 (unknowns)
        unknowns_map: dict[str, UnknownItem] = {}

        def add_unknown(code: str, reason: UnknownReason) -> None:
            if code not in unknowns_map:
                item_cfg = CHECKLIST.get(code, {})
                unknowns_map[code] = UnknownItem(
                    code=code,
                    reason=reason,
                    how_to_check=item_cfg.get("how_to_check", ""),
                )

        if inp.rights.price_manwon is None:
            r = (
                UnknownReason.lookup_failed
                if "lookup_price" in inp.failures
                else UnknownReason.no_data
            )
            add_unknown("trade_price", r)

        if inp.owner_matches_counterparty is None or owner_entry is None:
            add_unknown("owner_match", UnknownReason.no_data)

        if inp.defaulter_matched is None:
            r = (
                UnknownReason.lookup_failed
                if "match_defaulter" in inp.failures
                else UnknownReason.no_data
            )
            add_unknown("defaulter_list", r)

        if (
            inp.property.building_type != BuildingType.apartment
            and inp.ledger_main_use is None
        ):
            r = (
                UnknownReason.lookup_failed
                if "lookup_building" in inp.failures
                else UnknownReason.no_data
            )
            add_unknown("ledger_main_use", r)

        if (
            inp.property.building_type != BuildingType.apartment
            and inp.illegal_building == IllegalBuilding.unknown
        ):
            add_unknown("illegal_building", UnknownReason.no_answer)

        if (
            inp.property.building_type == BuildingType.multi_household
            and not inp.tenants_answered
        ):
            add_unknown("tenants", UnknownReason.no_answer)

        # eul_sum: 살아 있는 mortgage, jeonse_right, lease_right 중 금액 누락 여부
        has_missing_eul = any(
            not e.cancelled
            and e.purpose_code
            in (
                PurposeCode.mortgage,
                PurposeCode.jeonse_right,
                PurposeCode.lease_right,
            )
            and e.amount_manwon is None
            for e in inp.entries
        )
        if has_missing_eul:
            add_unknown("eul_sum", UnknownReason.no_data)

        for untried_code in inp.untried:
            add_unknown(untried_code, UnknownReason.no_data)

        unknowns = list(unknowns_map.values())

        # 4. 검토 항목 (checked)
        req_codes = self.required_steps(inp.property.building_type)
        checked: list[ChecklistItem] = []
        for code in req_codes:
            item_cfg = CHECKLIST.get(code, {})
            label = item_cfg.get("label", code)

            # 해당 없음(n_a) 판단
            is_na = False
            if code == "illegal_building" and inp.property.building_type == BuildingType.apartment:
                is_na = True
            elif code == "land_right" and not inp.property.is_collective:
                is_na = True
            elif (
                code in ("tenants", "land_registry", "ledger_households")
                and inp.property.building_type != BuildingType.multi_household
            ):
                is_na = True

            if code in unknowns_map:
                res = CheckResult.unknown
            elif is_na:
                res = CheckResult.n_a
            else:
                res = CheckResult.ok

            # entry_ids 결정
            c_entry_ids: list[str] = []
            if code == "eul_sum":
                c_entry_ids = [
                    e.entry_id
                    for e in inp.entries
                    if not e.cancelled
                    and e.purpose_code
                    in (
                        PurposeCode.mortgage,
                        PurposeCode.jeonse_right,
                        PurposeCode.lease_right,
                    )
                ]
            elif code == "gap_infringement":
                c_entry_ids = infringement_entries
            elif code == "trust":
                c_entry_ids = trust_entries
            elif code == "history":
                c_entry_ids = frequent_transfer_entries
            elif code in ("owner_match", "landlord_type"):
                c_entry_ids = owner_entry_ids
            elif code == "debt_ratio":
                c_entry_ids = inp.rights.based_on

            if not c_entry_ids:
                c_entry_ids = owner_entry_ids

            checked.append(
                ChecklistItem(
                    code=code,
                    label=label,
                    result=res,
                    entry_ids=c_entry_ids,
                )
            )

        # 5. 등급 판정
        g = self.grade(signals, inp.rights, unknowns)

        return SignalCheck(
            grade=g,
            signals=signals,
            checked=checked,
            unknowns=unknowns,
        )

    def grade(
        self,
        signals: list[RiskSignal],
        rights: RightsSummary,
        unknowns: list[UnknownItem],
    ) -> Grade:
        """위험 신호, 부채비율, 미확인 항목을 종합해 최종 등급을 결정한다.

        항목 ID: JSD-MS-005#RulesService.grade
        근거: JSD-PRD-001#R6, JSD-DOM-001#Grade, JSD-UC-001#UC-S3
        """
        danger_by: list[str] = [
            s.code for s in signals if s.severity == Severity.danger
        ]
        if rights.debt_ratio is not None and rights.debt_ratio > DEBT_RATIO["danger"]:
            danger_by.append("debt_ratio")

        if danger_by:
            return Grade(
                level=GradeLevel.danger,
                deciders=danger_by,
                unknowns=[u.code for u in unknowns],
                rule_version=RULE_VERSION,
            )

        caution_by: list[str] = [
            s.code for s in signals if s.severity == Severity.caution
        ]
        if (
            rights.debt_ratio is not None
            and DEBT_RATIO["caution"] < rights.debt_ratio <= DEBT_RATIO["danger"]
        ):
            caution_by.append("debt_ratio")

        # 확인 못 한 핵심 항목(trade_price, owner_match)이 있으면 주의
        for u in unknowns:
            if u.code in ("trade_price", "owner_match"):
                if u.code not in caution_by:
                    caution_by.append(u.code)

        if caution_by:
            return Grade(
                level=GradeLevel.caution,
                deciders=caution_by,
                unknowns=[u.code for u in unknowns],
                rule_version=RULE_VERSION,
            )

        return Grade(
            level=GradeLevel.safe,
            deciders=[],
            unknowns=[u.code for u in unknowns],
            rule_version=RULE_VERSION,
        )

    def criteria(
        self,
        limits: Limits,
        topic: CriteriaTopic | None = None,
        signal_code: str | None = None,
    ) -> Criteria:
        """판정 기준 및 공식 규칙 데이터를 공개한다.

        항목 ID: JSD-MS-005#RulesService.criteria
        근거: JSD-API-001#GET/api/criteria, JSD-API-002#get_criteria, JSD-UI-001#UI-4
        """
        public_limits = {
            "tool_calls": getattr(limits, "tool_calls", None) if not isinstance(limits, dict) else limits.get("tool_calls"),
            "questions": getattr(limits, "questions", None) if not isinstance(limits, dict) else limits.get("questions"),
            "file_mb": getattr(limits, "file_mb", None) if not isinstance(limits, dict) else limits.get("file_mb"),
            "pages": getattr(limits, "pages", None) if not isinstance(limits, dict) else limits.get("pages"),
            "retention_hours": getattr(limits, "retention_hours", None) if not isinstance(limits, dict) else limits.get("retention_hours"),
        }

        signals_list = [
            {
                "code": s["code"],
                "severity": s["severity"].value,
                "label": s["label"],
                "source": s["source"],
                "source_date": s["source_date"].isoformat(),
            }
            for s in SIGNALS.values()
        ]

        full = Criteria(
            rule_version=RULE_VERSION,
            grades=copy.deepcopy(GRADES),
            signals=signals_list,
            debt_ratio=copy.deepcopy(DEBT_RATIO),
            required_checks={k: list(v) for k, v in REQUIRED_CHECKS.items()},
            price_order=list(PRICE_ORDER),
            priority_repayment={
                "tiers": list(PRIORITY_REPAYMENT_TIERS),
                "default": DEFAULT_PRIORITY_REPAYMENT,
            },
            checklist=copy.deepcopy(CHECKLIST),
            limits=public_limits,
            sources=copy.deepcopy(SOURCES),
        )

        if topic is None:
            return full

        if topic == CriteriaTopic.grade:
            return Criteria(rule_version=RULE_VERSION, grades=copy.deepcopy(GRADES))
        elif topic == CriteriaTopic.signals:
            if signal_code:
                sig = next((s for s in signals_list if s["code"] == signal_code), None)
                return Criteria(rule_version=RULE_VERSION, signals=[sig] if sig else [])
            return Criteria(rule_version=RULE_VERSION, signals=signals_list)
        elif topic == CriteriaTopic.debt_ratio:
            return Criteria(rule_version=RULE_VERSION, debt_ratio=copy.deepcopy(DEBT_RATIO))
        elif topic == CriteriaTopic.required_checks:
            return Criteria(
                rule_version=RULE_VERSION,
                required_checks={k: list(v) for k, v in REQUIRED_CHECKS.items()},
            )
        elif topic == CriteriaTopic.price_order:
            return Criteria(rule_version=RULE_VERSION, price_order=list(PRICE_ORDER))
        elif topic == CriteriaTopic.priority_repayment:
            return Criteria(
                rule_version=RULE_VERSION,
                priority_repayment={
                    "tiers": list(PRIORITY_REPAYMENT_TIERS),
                    "default": DEFAULT_PRIORITY_REPAYMENT,
                },
            )
        elif topic == CriteriaTopic.limits:
            return Criteria(rule_version=RULE_VERSION, limits=public_limits)
        elif topic == CriteriaTopic.sources:
            return Criteria(rule_version=RULE_VERSION, sources=copy.deepcopy(SOURCES))

        return Criteria(rule_version=RULE_VERSION)

    def required_steps(self, building_type: BuildingType) -> list[str]:
        """건물 종류별 필수 검토 항목 코드를 반환한다.

        항목 ID: JSD-MS-005#RulesService.required_steps
        근거: JSD-PRD-001#R11, JSD-UC-001#UC-S9 4a
        """
        common = REQUIRED_CHECKS["common"]
        extra = REQUIRED_CHECKS.get(building_type, [])
        return list(dict.fromkeys(common + extra))
