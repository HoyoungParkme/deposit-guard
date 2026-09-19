"""Report 도메인 서비스 (ReportService).

항목 ID: JSD-MS-008
근거: JSD-DOM-002 4.8, JSD-DOM-003 opinions, JSD-SEQ-001, JSD-API-001, JSD-PRD-001, JSD-RFQ-001
"""

from __future__ import annotations
from contextlib import asynccontextmanager
import copy
from datetime import datetime, timezone
import re
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.core.errors import AppError
from app.domains.citation.service import CitationService
from app.domains.report import catalog, crud
from app.domains.report.ports import SentenceWriter
from app.shared import factcheck, money, privacy
from app.shared.types import (
    BuildingType,
    CheckResult,
    Citation,
    CitationUse,
    Grade,
    GradeLevel,
    PriceSource,
    PurposeCode,
    Report,
    ReportCheckedItem,
    ReportConclusion,
    ReportInput,
    ReportResult,
    ReportSignalItem,
    RightsSummary,
    Section,
    SentenceRequest,
    Sentences,
    Shareable,
    SpecialClause,
    Todo,
    TodoStage,
)


class ReportService:
    """의견서 조립, 생성 요청, 후검증 서비스."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        citation_service: CitationService | None = None,
        sentence_writer: SentenceWriter | None = None,
    ):
        self._session = session
        self._citation_service = citation_service or CitationService(session=session)
        self._sentence_writer = sentence_writer

    @asynccontextmanager
    async def _session_ctx(self, session: AsyncSession | None = None):
        if session is not None:
            yield session
        elif self._session is not None:
            yield self._session
        else:
            async with async_session_factory() as sess:
                async with sess.begin():
                    yield sess

    def pick_todos(self, inp: ReportInput) -> list[Todo]:
        """단계별 할 일 고르기.

        항목 ID: JSD-MS-008#ReportService.pick_todos
        근거: JSD-RFQ-001#Q22, JSD-RFQ-001#Q37, JSD-DOM-001#Todo, JSD-UC-001#UC-S8 1
        """
        signals = {s.code if hasattr(s, "code") else s["code"] for s in inp.check.signals}
        unknowns = {u.code if hasattr(u, "code") else u["code"] for u in inp.check.unknowns}
        mortgages = [
            e
            for e in inp.entries
            if e.purpose_code == PurposeCode.mortgage and not e.cancelled
        ]
        is_multi = (
            inp.property.building_type == BuildingType.multi_household
            or inp.rights.multi_household_unknown
        )

        # 신호/미확인 항목의 label 매핑 준비
        signal_labels = {
            s.code if hasattr(s, "code") else s["code"]: s.label if hasattr(s, "label") else s.get("label", "")
            for s in inp.check.signals
        }
        unknown_labels = {
            u.code if hasattr(u, "code") else u["code"]: u.how_to_check if hasattr(u, "how_to_check") else u.get("how_to_check", "")
            for u in inp.check.unknowns
        }

        selected: list[tuple[int, int, int, Todo]] = []
        # (stage_priority, unknown_priority, original_idx, Todo)

        stage_order = {
            TodoStage.before: 1,
            TodoStage.signing: 2,
            TodoStage.balance: 3,
            TodoStage.after: 4,
        }

        for idx, item in enumerate(catalog.TODOS):
            when = item["when"]
            matched = False
            from_unknown = False
            because_text = item["because"]

            if when == "unknown_trade_price":
                if "trade_price" in unknowns:
                    matched = True
                    from_unknown = True
                    because_text = unknown_labels.get("trade_price", item["because"])
            elif when == "unknown_illegal_building":
                if "illegal_building" in unknowns:
                    matched = True
                    from_unknown = True
                    because_text = unknown_labels.get("illegal_building", item["because"])
            elif when == "unknown_land_registry":
                if "land_registry" in unknowns:
                    matched = True
                    from_unknown = True
                    because_text = unknown_labels.get("land_registry", item["because"])
            elif when == "unknown_defaulter_list":
                if "defaulter_list" in unknowns:
                    matched = True
                    from_unknown = True
                    because_text = unknown_labels.get("defaulter_list", item["because"])
            elif when == "signal_owner_mismatch":
                if "owner_mismatch" in signals:
                    matched = True
                    because_text = signal_labels.get("owner_mismatch", item["because"])
            elif when == "signal_trust":
                if "trust" in signals:
                    matched = True
                    because_text = signal_labels.get("trust", item["because"])
            elif when == "multi_household":
                if is_multi:
                    matched = True
            elif when == "always":
                matched = True
            elif when == "deposit_over_1000":
                if inp.deposit_manwon > 1000:
                    matched = True
            elif when == "deposit_over_6000":
                if inp.deposit_manwon > 6000:
                    matched = True
            elif when == "has_mortgage":
                if mortgages:
                    matched = True
                    because_text = "근저당이 있습니다"

            if matched:
                todo = Todo(
                    stage=item["stage"],
                    title=item["title"],
                    how=item["how"],
                    cost=item["cost"],
                    because=[because_text],
                )
                p_stage = stage_order.get(item["stage"], 99)
                p_unknown = 0 if from_unknown else 1
                selected.append((p_stage, p_unknown, idx, todo))

        # 정렬: 단계 순서 -> 미확인 항목 우선 -> 원래 순서
        selected.sort(key=lambda t: (t[0], t[1], t[2]))
        return [t[3] for t in selected]

    def _pick_clauses_with_entries(
        self, inp: ReportInput
    ) -> tuple[list[SpecialClause], list[list[str]]]:
        """특약 고르고 빈칸 채우기 (근거 entry_ids 포함).

        항목 ID: JSD-MS-008#ReportService.pick_clauses
        근거: JSD-RFQ-001#Q23, JSD-UC-001#UC-S8 2, JSD-PRD-001#R9
        """
        mortgages = [
            e
            for e in inp.entries
            if e.purpose_code == PurposeCode.mortgage and not e.cancelled
        ]
        top_mortgage = (
            max(mortgages, key=lambda e: e.amount_manwon or 0) if mortgages else None
        )

        transfers = [
            e
            for e in inp.entries
            if e.section == Section.gap
            and e.purpose_code == PurposeCode.ownership_transfer
            and not e.cancelled
        ]
        latest_transfer = transfers[-1] if transfers else None

        signals = {s.code for s in inp.check.signals}
        is_multi = (
            inp.property.building_type == BuildingType.multi_household
            or inp.rights.multi_household_unknown
        )

        deposit_fmt = money.format_manwon(inp.deposit_manwon)

        if top_mortgage:
            if top_mortgage.holder_is_corporation and top_mortgage.holder:
                mortgagee = top_mortgage.holder
            else:
                mortgagee = "근저당권자"
            max_amount_fmt = money.format_manwon(top_mortgage.amount_manwon or 0)
        else:
            mortgagee = "근저당권자"
            max_amount_fmt = "0원"

        balance_date = "____년 __월 __일"

        clauses: list[SpecialClause] = []
        clause_entries: list[list[str]] = []

        for item in catalog.CLAUSES:
            no = item["no"]
            when = item["when"]
            matched = False
            entries_for_clause: list[str] = []
            filled: dict[str, Any] = {}

            if when == "always":
                matched = True
            elif when == "has_mortgage":
                if mortgages:
                    matched = True
                    filled = {
                        "balance_date": balance_date,
                        "mortgagee": mortgagee,
                        "max_amount": max_amount_fmt,
                    }
                    if top_mortgage:
                        entries_for_clause = [top_mortgage.entry_id]
            elif when == "unsafe_or_no_debt_ratio":
                if (
                    inp.check.grade.level != GradeLevel.safe
                    or inp.rights.debt_ratio is None
                ):
                    matched = True
                    filled = {"deposit": deposit_fmt}
            elif when == "ownership_risk":
                if "frequent_transfer" in signals or "corporate_landlord" in signals:
                    matched = True
                    if latest_transfer:
                        entries_for_clause = [latest_transfer.entry_id]
            elif when == "deposit_over_1000":
                if inp.deposit_manwon > 1000:
                    matched = True

            if matched:
                body = item["template"].format(
                    deposit=deposit_fmt,
                    mortgagee=mortgagee,
                    max_amount=max_amount_fmt,
                    balance_date=balance_date,
                )
                sc = SpecialClause(
                    title=item["title"],
                    body=body,
                    source=item["source"],
                    filled=filled,
                )
                clauses.append(sc)
                clause_entries.append(entries_for_clause)

        return clauses, clause_entries

    def pick_clauses(self, inp: ReportInput) -> list[SpecialClause]:
        """특약 고르고 빈칸 채우기 (공개 시그니처)."""
        clauses, _ = self._pick_clauses_with_entries(inp)
        return clauses

    def template_sentences(self, inp: ReportInput) -> Sentences:
        """모델 없이 만드는 문장.

        항목 ID: JSD-MS-008#ReportService.template_sentences
        근거: JSD-UC-001#UC-S8 3a, JSD-DOM-002 4.8
        """
        deposit_fmt = money.format_manwon(inp.deposit_manwon)
        pct_val = round((inp.rights.debt_ratio or 0) * 100)
        pct = f"{pct_val}%"
        grade = inp.check.grade.level

        # 1. 결론 문장 틀
        if grade == GradeLevel.danger:
            decider = (
                inp.check.grade.deciders[0] if inp.check.grade.deciders else "위험 신호"
            )
            marker = ""
            if decider == "debt_ratio":
                decider_text = f"선순위와 보증금이 주택 가격의 {pct}입니다"
            elif decider == "trade_price":
                decider_text = "주택 가격을 확인하지 못했습니다"
            else:
                sig = next(
                    (s for s in inp.check.signals if s.code == decider), None
                )
                if sig:
                    decider_text = sig.label
                    if sig.entry_ids:
                        marker = "".join(f"{{{{entry:{eid}}}}}" for eid in sig.entry_ids)
                else:
                    decider_text = decider

            conclusion = (
                f"보증금 {deposit_fmt}을 넣기엔 위험합니다. {decider_text}."
                + (f" {marker}" if marker else "")
            ).strip()

        elif grade == GradeLevel.caution:
            deciders = inp.check.grade.deciders[:2]
            labels: list[str] = []
            markers: list[str] = []
            for d in deciders:
                if d == "debt_ratio":
                    labels.append(f"선순위와 보증금이 주택 가격의 {pct}입니다")
                elif d == "trade_price":
                    labels.append("주택 가격을 확인하지 못했습니다")
                else:
                    sig = next((s for s in inp.check.signals if s.code == d), None)
                    if sig:
                        labels.append(sig.label)
                        if sig.entry_ids:
                            markers.extend(
                                [f"{{{{entry:{eid}}}}}" for eid in sig.entry_ids]
                            )
                    else:
                        labels.append(d)

            decider_text = ", ".join(labels) if labels else "확인할 사항이 있습니다"
            marker = "".join(markers)
            conclusion = (
                f"보증금 {deposit_fmt}을 넣기 전에 확인할 것이 있습니다. {decider_text}."
                + (f" {marker}" if marker else "")
            ).strip()

        else:  # SAFE
            conclusion = (
                f"등기부와 조회 결과로는 큰 위험이 보이지 않습니다. 부채비율 {pct}입니다."
            )

        # 2. 설명
        explanations: dict[str, str] = {}
        for s in inp.check.signals:
            explanations[s.code] = catalog.SIGNAL_EXPLANATIONS.get(s.code, s.label)

        # 3. 물어볼 것
        questions: list[str] = []
        codes_to_ask = [s.code for s in inp.check.signals] + [
            u.code for u in inp.check.unknowns
        ]
        for c in codes_to_ask:
            q_val = catalog.QUESTIONS.get(c)
            if isinstance(q_val, str) and q_val not in questions:
                questions.append(q_val)
            elif isinstance(q_val, list):
                for q in q_val:
                    if q not in questions:
                        questions.append(q)

        # 3개 미만이면 common으로 채운다
        common_list = catalog.QUESTIONS.get("common", [])
        if isinstance(common_list, list):
            for cq in common_list:
                if len(questions) >= 3:
                    break
                if cq not in questions:
                    questions.append(cq)

        questions = questions[:5]

        return Sentences(
            conclusion=conclusion,
            explanations=explanations,
            questions=questions,
            tokens_in=0,
            tokens_out=0,
        )

    def _prepare_allowed_for_factcheck(
        self, inp: ReportInput
    ) -> tuple[set[int], set[float], str]:
        """후검증용 허용 금액, 비율, 등급 문자열을 수집한다."""
        allowed_manwon: set[int] = set()
        for amt in [
            inp.rights.senior_mortgage_manwon,
            inp.rights.senior_lease_manwon,
            inp.rights.other_tenants_manwon,
            inp.rights.senior_total_manwon,
            inp.rights.deposit_manwon,
            inp.rights.price_manwon,
            inp.deposit_manwon,
        ]:
            if amt is not None:
                allowed_manwon.add(amt)

        for e in inp.entries:
            if e.amount_manwon is not None:
                allowed_manwon.add(e.amount_manwon)
            if e.price_manwon is not None:
                allowed_manwon.add(e.price_manwon)

        allowed_ratios: set[float] = set()
        if inp.rights.debt_ratio is not None:
            allowed_ratios.add(inp.rights.debt_ratio)
        if inp.rights.senior_ratio is not None:
            allowed_ratios.add(inp.rights.senior_ratio)

        grade_level = inp.check.grade.level
        grade_str = grade_level.value if hasattr(grade_level, "value") else str(grade_level)
        return allowed_manwon, allowed_ratios, grade_str

    async def write(
        self,
        review_id: str,
        inp: ReportInput,
        agent_notes: str | None = None,
        revision_reason: str | None = None,
        session: AsyncSession | None = None,
    ) -> ReportResult:
        """의견서를 만들어 덮는다.

        항목 ID: JSD-MS-008#ReportService.write
        근거: JSD-SEQ-001#SEQ-8, JSD-UC-001#UC-S8 1~5·3a, JSD-API-002#write_report, JSD-PRD-001#R9
        """
        # 1. 할 일, 특약, 기본 템플릿 문장 생성
        todos = self.pick_todos(inp)
        clauses, clause_entries = self._pick_clauses_with_entries(inp)
        base = self.template_sentences(inp)

        # 2. 문장 생성 (트랜잭션 밖)
        llm_fallback = False
        tokens_in = 0
        tokens_out = 0

        if inp.use_model and self._sentence_writer is not None:
            req = SentenceRequest(
                grade=inp.check.grade,
                rights=inp.rights,
                signals=inp.check.signals,
                agent_notes=agent_notes,
                revision_reason=revision_reason,
            )
            try:
                s = await self._sentence_writer.write(req)
                tokens_in = s.tokens_in
                tokens_out = s.tokens_out
            except Exception:
                s = base
                llm_fallback = True
        else:
            s = base
            llm_fallback = True

        # 모자란 곳 base로 채우기
        explanations = dict(s.explanations)
        for sig in inp.check.signals:
            if sig.code not in explanations:
                explanations[sig.code] = base.explanations.get(
                    sig.code, f"{sig.label} 신호가 확인되었습니다."
                )

        conclusion = s.conclusion if s.conclusion else base.conclusion
        questions = list(s.questions) if s.questions else list(base.questions)

        # 3. 후검증 (트랜잭션 밖)
        corrections = 0
        allowed_manwon, allowed_ratios, grade_str = (
            self._prepare_allowed_for_factcheck(inp)
        )

        # 결론 문장 검증
        if factcheck.contradicts(
            conclusion, allowed_manwon, allowed_ratios, grade_str
        ):
            conclusion = base.conclusion
            corrections += 1

        # 신호 설명 검증
        for code, exp in list(explanations.items()):
            if factcheck.contradicts(exp, allowed_manwon, allowed_ratios, grade_str):
                explanations[code] = base.explanations.get(
                    code, f"{code} 신호가 확인되었습니다."
                )
                corrections += 1

        # 질문 문장 검증
        valid_questions: list[str] = []
        for q in questions:
            if factcheck.contradicts(q, allowed_manwon, allowed_ratios, grade_str):
                corrections += 1
            else:
                valid_questions.append(q)

        if len(valid_questions) < 3:
            for bq in base.questions:
                if bq not in valid_questions:
                    valid_questions.append(bq)
                if len(valid_questions) >= 3:
                    break
        questions = valid_questions[:5]

        # 4. DB 트랜잭션 (인용 지우기부터 의견서 덮기까지)
        now = datetime.now(timezone.utc)

        async with self._session_ctx(session) as sess:
            # 1) 인용 지우기
            await self._citation_service.clear_report(review_id, session=sess)

            # 2) 결론 표식 치환
            cited = await self._citation_service.resolve_markers(
                review_id, conclusion, CitationUse.conclusion, "", session=sess
            )
            corrections += cited.dropped

            # 3) 선순위 합산 인용
            senior_tot_fmt = money.format_manwon(inp.rights.senior_total_manwon)
            pct_str = (
                f" (부채비율 {round(inp.rights.debt_ratio * 100)}%)"
                if inp.rights.debt_ratio is not None
                else ""
            )
            rights_label = f"선순위 합산 {senior_tot_fmt}{pct_str}"
            await self._citation_service.cite(
                review_id, CitationUse.rights, "", rights_label, inp.rights.based_on, session=sess
            )

            # 4) 신호, 확인항목, 특약 인용
            for sig in inp.check.signals:
                if sig.entry_ids:
                    await self._citation_service.cite(
                        review_id, CitationUse.signal, sig.code, sig.label, sig.entry_ids, session=sess
                    )

            for chk in inp.check.checked:
                if chk.entry_ids:
                    await self._citation_service.cite(
                        review_id, CitationUse.checked, chk.code, chk.label, chk.entry_ids, session=sess
                    )

            for idx, (cl, c_entries) in enumerate(zip(clauses, clause_entries)):
                if c_entries:
                    await self._citation_service.cite(
                        review_id, CitationUse.clause, str(idx + 1), cl.title, c_entries, session=sess
                    )

            # 5) 판 번호 계산
            prev_rev = await crud.get_revision_no(sess, review_id)
            revision_no = (prev_rev or 0) + 1

            # 6) body 조립 (citations는 빈 목록)
            signals_body: list[dict[str, Any]] = []
            for sig in inp.check.signals:
                s_date = (
                    sig.source_date.isoformat()
                    if hasattr(sig, "source_date") and sig.source_date
                    else None
                )
                signals_body.append(
                    {
                        "code": sig.code,
                        "severity": sig.severity.value
                        if hasattr(sig.severity, "value")
                        else str(sig.severity),
                        "label": sig.label,
                        "explanation": explanations.get(sig.code, sig.label),
                        "source": sig.source,
                        "source_date": s_date,
                        "citations": [],
                    }
                )

            checked_body: list[dict[str, Any]] = []
            for chk in inp.check.checked:
                checked_body.append(
                    {
                        "code": chk.code,
                        "label": chk.label,
                        "result": chk.result.value
                        if hasattr(chk.result, "value")
                        else str(chk.result),
                        "citations": [],
                    }
                )

            todos_body = [
                {
                    "stage": t.stage.value if hasattr(t.stage, "value") else str(t.stage),
                    "title": t.title,
                    "how": t.how,
                    "cost": t.cost,
                    "because": t.because,
                }
                for t in todos
            ]

            clauses_body = [
                {
                    "title": c.title,
                    "body": c.body,
                    "source": c.source,
                    "filled": c.filled,
                }
                for c in clauses
            ]

            notices = list(catalog.NOTICES) + [
                f"판정 규칙 버전: {inp.check.grade.rule_version}"
            ]

            rights_dict = {
                "senior_mortgage_manwon": inp.rights.senior_mortgage_manwon,
                "senior_lease_manwon": inp.rights.senior_lease_manwon,
                "other_tenants_manwon": inp.rights.other_tenants_manwon,
                "senior_total_manwon": inp.rights.senior_total_manwon,
                "deposit_manwon": inp.rights.deposit_manwon,
                "price_manwon": inp.rights.price_manwon,
                "price_source": inp.rights.price_source.value
                if inp.rights.price_source and hasattr(inp.rights.price_source, "value")
                else (str(inp.rights.price_source) if inp.rights.price_source else None),
                "debt_ratio": inp.rights.debt_ratio,
                "senior_ratio": inp.rights.senior_ratio,
                "multi_household_unknown": inp.rights.multi_household_unknown,
                "based_on": inp.rights.based_on,
            }

            grade_dict = {
                "level": grade_str,
                "deciders": inp.check.grade.deciders,
                "unknowns": inp.check.grade.unknowns,
                "rule_version": inp.check.grade.rule_version,
            }

            body_dict: dict[str, Any] = {
                "grade": grade_dict,
                "conclusion": {
                    "text": cited.text,
                    "citations": [],
                },
                "rights": rights_dict,
                "signals": signals_body,
                "checked": checked_body,
                "todos": todos_body,
                "clauses": clauses_body,
                "questions_to_ask": questions,
                "notices": notices,
                "corrections": corrections,
                "llm_fallback": llm_fallback,
                "revision_no": revision_no,
                "revision_reason": revision_reason,
            }

            subject_dict = {
                "region_short": inp.property.region,
                "building_type": inp.property.building_type.value
                if hasattr(inp.property.building_type, "value")
                else str(inp.property.building_type),
                "deposit_manwon": inp.deposit_manwon,
                "contract_type": inp.contract_type.value
                if hasattr(inp.contract_type, "value")
                else str(inp.contract_type),
                "reviewed_at": now.isoformat(),
            }

            await crud.upsert_opinion(
                session=sess,
                review_id=review_id,
                body=body_dict,
                subject=subject_dict,
                revision_no=revision_no,
                revision_reason=revision_reason,
                written_at=now,
            )

        return ReportResult(
            grade=inp.check.grade.level,
            signal_count=len(inp.check.signals),
            unknown_count=len(inp.check.unknowns),
            corrections=corrections,
            rule_version=inp.check.grade.rule_version,
            revision_no=revision_no,
            revision_reason=revision_reason,
            llm_fallback=llm_fallback,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    async def get(
        self,
        review_id: str,
        session: AsyncSession | None = None,
    ) -> Report:
        """의견서와 인용을 조회한다.

        항목 ID: JSD-MS-008#ReportService.get
        근거: JSD-SEQ-001#SEQ-14, JSD-API-001#GET/api/reviews/{id}/report
        """
        async with self._session_ctx(session) as sess:
            op = await crud.get_opinion(sess, review_id)
            if not op:
                raise AppError("not_found", "의견서가 아직 작성되지 않았습니다.")

            refs = await self._citation_service.for_report(review_id, session=sess)
            body = dict(op.body)

            # 1. 결론 인용 매핑
            conclusion_citations = [
                r.citation for r in refs if r.used_in == CitationUse.conclusion
            ]
            conclusion = ReportConclusion(
                text=body["conclusion"]["text"],
                citations=conclusion_citations,
            )

            # 2. 신호 인용 매핑
            signals: list[ReportSignalItem] = []
            for s_data in body.get("signals", []):
                code = s_data["code"]
                cites = [
                    r.citation
                    for r in refs
                    if r.used_in == CitationUse.signal and r.ref == code
                ]
                s_date = None
                if s_data.get("source_date"):
                    try:
                        s_date = datetime.fromisoformat(s_data["source_date"]).date()
                    except Exception:
                        s_date = None

                signals.append(
                    ReportSignalItem(
                        code=code,
                        severity=s_data["severity"],
                        label=s_data["label"],
                        explanation=s_data["explanation"],
                        source=s_data["source"],
                        source_date=s_date,
                        citations=cites,
                    )
                )

            # 3. 확인 항목 인용 매핑
            checked: list[ReportCheckedItem] = []
            for c_data in body.get("checked", []):
                code = c_data["code"]
                cites = [
                    r.citation
                    for r in refs
                    if r.used_in == CitationUse.checked and r.ref == code
                ]
                checked.append(
                    ReportCheckedItem(
                        code=code,
                        label=c_data["label"],
                        result=c_data["result"],
                        citations=cites,
                    )
                )

            # 4. 할 일, 특약 재구성
            todos = [
                Todo(
                    stage=t["stage"],
                    title=t["title"],
                    how=t["how"],
                    cost=t["cost"],
                    because=t["because"],
                )
                for t in body.get("todos", [])
            ]

            clauses = [
                SpecialClause(
                    title=c["title"],
                    body=c["body"],
                    source=c["source"],
                    filled=c.get("filled", {}),
                )
                for c in body.get("clauses", [])
            ]

            # 5. 등급 및 권리합산 재구성
            g_data = body["grade"]
            grade = Grade(
                level=g_data["level"],
                deciders=g_data["deciders"],
                unknowns=g_data["unknowns"],
                rule_version=g_data["rule_version"],
            )

            r_data = body.get("rights", {})
            rights = RightsSummary(
                senior_mortgage_manwon=r_data.get("senior_mortgage_manwon", 0),
                senior_lease_manwon=r_data.get("senior_lease_manwon", 0),
                other_tenants_manwon=r_data.get("other_tenants_manwon", 0),
                senior_total_manwon=r_data.get("senior_total_manwon", 0),
                deposit_manwon=r_data.get("deposit_manwon", 0),
                price_manwon=r_data.get("price_manwon"),
                price_source=r_data.get("price_source"),
                debt_ratio=r_data.get("debt_ratio"),
                senior_ratio=r_data.get("senior_ratio"),
                multi_household_unknown=r_data.get("multi_household_unknown", False),
                based_on=r_data.get("based_on", []),
            )

            return Report(
                grade=grade,
                conclusion=conclusion,
                rights=rights,
                signals=signals,
                checked=checked,
                todos=todos,
                clauses=clauses,
                questions_to_ask=body.get("questions_to_ask", []),
                notices=body.get("notices", []),
                corrections=body.get("corrections", 0),
                llm_fallback=body.get("llm_fallback", False),
                revision_no=body.get("revision_no", 1),
                revision_reason=body.get("revision_reason"),
            )

    async def exists(
        self,
        review_id: str,
        session: AsyncSession | None = None,
    ) -> bool:
        """의견서가 있는지 확인한다.

        항목 ID: JSD-MS-008#ReportService.exists
        """
        async with self._session_ctx(session) as sess:
            return await crud.exists_opinion(sess, review_id)

    async def shareable(
        self,
        review_id: str,
        session: AsyncSession | None = None,
    ) -> Shareable:
        """공유본에 담을 사본을 만든다.

        항목 ID: JSD-MS-008#ReportService.shareable
        근거: JSD-SEQ-001#SEQ-14, JSD-UC-001#UC-A4 4, JSD-PRD-001#R14
        """
        async with self._session_ctx(session) as sess:
            op = await crud.get_opinion(sess, review_id)
            if not op:
                raise AppError("not_found", "의견서가 아직 작성되지 않았습니다.")

            # 의견서 로드
            report = await self.get(review_id, session=sess)

            # 1. clauses = [], questions_to_ask = [], citations 전부 빈 목록
            # 2. 결론의 {{cN}} 표식 제거
            clean_conclusion_text = re.sub(r"\{\{c\d+\}\}", "", report.conclusion.text).strip()
            clean_conclusion_text = re.sub(r" +", " ", clean_conclusion_text)

            # 3. privacy.mask_text 로 마스킹 (결론, 신호 설명, 할 일, revision_reason)
            masked_conclusion_text = privacy.mask_text(clean_conclusion_text, names=[])

            masked_signals: list[ReportSignalItem] = []
            for s in report.signals:
                masked_exp = privacy.mask_text(s.explanation, names=[])
                masked_signals.append(
                    ReportSignalItem(
                        code=s.code,
                        severity=s.severity,
                        label=s.label,
                        explanation=masked_exp,
                        source=s.source,
                        source_date=s.source_date,
                        citations=[],
                    )
                )

            masked_checked: list[ReportCheckedItem] = [
                ReportCheckedItem(
                    code=c.code,
                    label=c.label,
                    result=c.result,
                    citations=[],
                )
                for c in report.checked
            ]

            masked_todos: list[Todo] = []
            for t in report.todos:
                m_title = privacy.mask_text(t.title, names=[])
                m_how = privacy.mask_text(t.how, names=[])
                m_because = [privacy.mask_text(b, names=[]) for b in t.because]
                masked_todos.append(
                    Todo(
                        stage=t.stage,
                        title=m_title,
                        how=m_how,
                        cost=t.cost,
                        because=m_because,
                    )
                )

            masked_revision_reason = (
                privacy.mask_text(report.revision_reason, names=[])
                if report.revision_reason
                else None
            )

            share_report = Report(
                grade=report.grade,
                conclusion=ReportConclusion(
                    text=masked_conclusion_text,
                    citations=[],
                ),
                rights=report.rights,
                signals=masked_signals,
                checked=masked_checked,
                todos=masked_todos,
                clauses=[],
                questions_to_ask=[],
                notices=report.notices,
                corrections=report.corrections,
                llm_fallback=report.llm_fallback,
                revision_no=report.revision_no,
                revision_reason=masked_revision_reason,
            )

            return Shareable(
                report=share_report,
                subject=op.subject,
            )

    async def delete_for_review(
        self,
        review_id: str,
        session: AsyncSession | None = None,
    ) -> None:
        """의견서를 삭제한다.

        항목 ID: JSD-MS-008#ReportService.delete_for_review
        """
        async with self._session_ctx(session) as sess:
            await crud.delete_opinion(sess, review_id)
