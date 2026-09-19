"""에이전트 루프 서비스 (service_agent).

근거: JSD-DOM-002 4.2, JSD-MS-002, JSD-SEQ-001, JSD-API-002
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
import re
import sys
import time
from typing import Any
import uuid

logger = logging.getLogger(__name__)

from app.core.config import LIMITS
from app.core.db import async_session_factory
from app.core.errors import AppError
from app.domains.citation.service import CitationService
from app.domains.lookup.service import LookupService
from app.domains.registry.service import RegistryService
from app.domains.report.service import ReportService
from app.domains.review import crud
from app.domains.review.ports import AgentModel
from app.domains.review.prompts import (
    ANSWER_WITHOUT_TOOLS,
    FIRST_TURN,
    FOLLOW_UP_SYSTEM,
    NUMBERS_FROM_TOOLS,
    PICK_A_TOOL,
    REVIEW_SYSTEM,
)
from app.domains.review.schemas import (
    AskArgs,
    LoopState,
    ReviewFacts,
    ToolCard,
    ToolResult,
    TOOL_ARG_MODELS,
    REVIEW_TOOLS,
)
from app.domains.rules.service import RulesService
from app.infra.openai import usage_krw
from app.shared import factcheck, money, privacy
from app.shared.types import (
    BuildingLedger,
    BuildingType,
    CitationUse,
    DefaulterMatch,
    GradeLevel,
    InputType,
    MessageKind,
    Phase,
    PriceLookup,
    QuestionKind,
    ReviewStatus,
    Role,
    ToolCall,
    ToolName,
    ToolStatus,
)

# 필수 항목 코드 -> 시도로 보는 호출 이름/패턴
STEP_TOOLS: dict[str, list[Any]] = {
    "owner_match": ["read_registry", "check_signals"],
    "gap_infringement": ["read_registry", "check_signals"],
    "trust": ["read_registry", "check_signals"],
    "history": ["read_registry", "check_signals"],
    "eul_sum": ["summarize_rights"],
    "lease_jeonse": ["summarize_rights"],
    "debt_ratio": ["summarize_rights", "lookup_price"],
    "defaulter_list": ["match_defaulter"],
    "trade_price": ["lookup_price"],
    "land_right": ["read_registry"],
    "ledger_main_use": ["lookup_building"],
    "ledger_households": ["lookup_building"],
    "residential_use": ["lookup_building"],
    "illegal_building": ["ask_user:illegal_building"],
    "land_registry": [["ask_user:land_registry", "read_registry:land"]],  # 둘 중 하나
    "tenants": ["ask_user:tenants"],
}

TOOL_KOREAN_NAMES: dict[str, str] = {
    "read_registry": "등기부 읽기",
    "summarize_rights": "권리 합산",
    "check_signals": "위험 신호 확인",
    "lookup_price": "실거래가 조회",
    "lookup_building": "건축물대장 조회",
    "match_defaulter": "임대인 명단 대조",
    "ask_user": "사용자 질문",
    "get_criteria": "판정 기준 확인",
    "write_report": "의견서 작성",
}

ERROR_CODE_MEANINGS: dict[str, str] = {
    "read_registry_first": "등기부 먼저 읽기 필요",
    "no_region_code": "법정동을 찾지 못함",
    "no_trades": "같은 단지 거래 없음",
    "api_failed": "공공 API 실패 (재시도 후)",
    "not_found": "대장에 건물이 없음",
    "no_snapshot": "명단 스냅샷이 없음",
    "no_name": "대조할 이름이 없음",
    "question_limit": "질문 5회 초과",
    "required_unchecked": "필수 검토 항목을 시도하지 않음",
    "unknown_tool": "목록 밖 도구",
    "tool_failed": "예상 밖 예외",
    "tool_limit": "되묻기 한 차례에 도구 5회 초과",
}

ALLOWED_FOLLOW_UP_TOOLS = {
    "get_criteria",
    "summarize_rights",
    "check_signals",
    "write_report",
    "lookup_price",
}


def _is_step_tried(required_step: str, tried: list[str]) -> bool:
    """필수 검토 항목이 tried 목록에 있는지 검사한다."""
    conditions = STEP_TOOLS.get(required_step)
    if not conditions:
        return True

    for cond in conditions:
        if isinstance(cond, list):
            # 또는 조건 (예: ask_user:land_registry 또는 read_registry:land)
            matched = any(
                any(t == opt or (opt == "read_registry" and t.startswith("read_registry")) for t in tried)
                for opt in cond
            )
            if not matched:
                return False
        else:
            if cond == "read_registry":
                matched = any(t == "read_registry" or t.startswith("read_registry") for t in tried)
            else:
                matched = cond in tried
            if not matched:
                return False
    return True


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    return val if isinstance(val, uuid.UUID) else uuid.UUID(str(val))


class AgentService:
    """에이전트 루프 및 도구 디스패치 관리 서비스."""

    def __init__(
        self,
        registry_service: RegistryService | None = None,
        lookup_service: LookupService | None = None,
        rules_service: RulesService | None = None,
        citation_service: CitationService | None = None,
        report_service: ReportService | None = None,
    ) -> None:
        self.registry_service = registry_service or RegistryService()
        self.lookup_service = lookup_service or LookupService()
        self.rules_service = rules_service or RulesService()
        self.citation_service = citation_service or CitationService()
        self.report_service = report_service or ReportService()

    def review_service(self):
        from app.domains.review.service import ReviewService
        return ReviewService(
            registry_service=self.registry_service,
            citation_service=self.citation_service,
            rules_service=self.rules_service,
            report_service=self.report_service,
        )


# 싱글톤 유사 헬퍼 인스턴스
_agent_service = AgentService()


def get_agent_service() -> AgentService:
    return _agent_service


def tool_summary(call: ToolCall, result: object | str) -> str:
    """도구 카드 한 줄 요약을 생성한다 (JSD-MS-002#service_agent.tool_summary)."""
    # 1. 실패 코드 문자열 처리
    if isinstance(result, str):
        tool_kr = TOOL_KOREAN_NAMES.get(call.name, call.name)
        reason = ERROR_CODE_MEANINGS.get(result, result)
        return f"{tool_kr} 실패: {reason}"

    # 2. 성공 도구별 요약
    name = call.name
    data = result if isinstance(result, dict) else (asdict(result) if hasattr(result, "__dataclass_fields__") else {})

    if name == "read_registry":
        building = data.get("building") or {}
        btype = building.get("building_type", "부동산")
        gap_count = len(data.get("gap") or [])
        eul_list = data.get("eul") or []
        eul_count = len(eul_list)
        cancelled_count = sum(1 for e in eul_list if e.get("cancelled"))
        return f"등기부 읽음: {btype} · 갑구 {gap_count}건 · 을구 {eul_count}건(말소 {cancelled_count})"

    elif name == "summarize_rights":
        total = data.get("senior_total_manwon", 0)
        formatted_total = money.format_manwon(total)
        ratio = data.get("debt_ratio")
        if ratio is not None:
            return f"선순위 {formatted_total} · 부채비율 {ratio:.1f}%"
        return f"선순위 {formatted_total} · 가격 필요"

    elif name == "check_signals":
        grade_info = data.get("grade") or {}
        level = grade_info.get("level", "안전")
        level_kr = "안전" if level == "safe" else ("주의" if level == "caution" else "위험")
        signals = data.get("signals") or []
        unknowns = grade_info.get("unknowns") or []
        return f"등급 {level_kr} · 신호 {len(signals)}개 · 확인 못 함 {len(unknowns)}개"

    elif name == "lookup_price":
        price = data.get("price_manwon", 0)
        count = data.get("count", 0)
        period = data.get("period", "")
        return f"실거래가 {money.format_manwon(price)} ({count}건, {period})"

    elif name == "lookup_building":
        main_use = data.get("main_use", "")
        households = data.get("households") or data.get("families") or 0
        multi = data.get("multiple_candidates", False)
        suffix = " (후보 여럿)" if multi else ""
        return f"건축물대장: {main_use} · {households}가구{suffix}"

    elif name == "match_defaulter":
        matched = data.get("matched", False)
        if matched:
            count = data.get("match_count", 1)
            return f"명단 대조: {count}건 일치, 동명이인일 수 있음"
        snap = data.get("snapshot_date", "")
        return f"명단 대조: 일치 없음 (기준 {snap})"

    elif name == "ask_user":
        ans = data.get("answer", "")
        return f"질문 답: {ans}"

    elif name == "get_criteria":
        topic = call.arguments.get("topic", "")
        return f"판정 기준 확인: {topic}"

    elif name == "write_report":
        level = data.get("grade", "safe")
        level_kr = "안전" if level == "safe" else ("주의" if level == "caution" else "위험")
        sig_cnt = data.get("signal_count", 0)
        return f"의견서 작성: 등급 {level_kr} · 신호 {sig_cnt}개"

    return f"{call.name} 완료"


async def mask_for_model(
    review_id: str | uuid.UUID,
    data: dict[str, Any] | None,
    service: AgentService | None = None,
) -> dict[str, Any] | None:
    """모델로 가는 도구 응답을 가린다 (JSD-MS-002#service_agent.mask_for_model)."""
    if data is None:
        return None

    svc = service or _agent_service
    r_id = _to_uuid(review_id)
    holder_names = await svc.registry_service.holder_names(r_id)
    labels = privacy.person_labels(holder_names)

    def _mask_val(val: Any) -> Any:
        if isinstance(val, str):
            # 주민번호 형태 숫자 삭제
            return privacy.mask_text(val, [])
        elif isinstance(val, dict):
            new_dict = {}
            for k, v in val.items():
                # 제외할 내부 키들
                if k in (
                    "lot_address",
                    "exclusive_area_m2",
                    "building_name",
                    "section",
                    "parent_entry_id",
                    "cause",
                    "cancelled_by_entry_id",
                    "llm_fallback",
                    "tokens_in",
                    "tokens_out",
                    "source_date",
                ):
                    continue
                if k == "region" and isinstance(v, str):
                    new_dict[k] = privacy.short_region(v)
                elif k == "holder" and isinstance(v, str):
                    # 법인이면 그대로, 개인이면 labels
                    is_corp = val.get("holder_is_corporation", False)
                    if is_corp:
                        new_dict[k] = v
                    else:
                        new_dict[k] = labels.get(v, "개인")
                else:
                    new_dict[k] = _mask_val(v)
            return new_dict
        elif isinstance(val, list):
            return [_mask_val(item) for item in val]
        return val

    return _mask_val(data)


async def check_stated(
    review_id: str | uuid.UUID,
    args: dict[str, Any],
) -> dict[str, Any]:
    """모델이 넘긴 사실 인자를 사용자 말과 대조 (JSD-MS-002#service_agent.check_stated)."""
    r_id = _to_uuid(review_id)

    async with async_session_factory() as session:
        records = await crud.list_review_records(session, r_id, after_seq=0, limit=200)
        user_texts = [
            r.text
            for r in records
            if r.role == "user" and r.kind in ("say", "answer") and r.text
        ]

        allowed_amounts: set[int] = set()
        allowed_ints: set[int] = set()
        for t in user_texts:
            for amt in factcheck.amounts(t):
                allowed_amounts.add(amt)
            # 모든 정수 추출
            for num_str in re.findall(r"\b\d+\b", t):
                allowed_ints.add(int(num_str))

        clean_args = dict(args)
        stated_updates: dict[str, Any] = {}
        corrections_inc = 0

        # price_manwon 대조
        if "price_manwon" in args and args["price_manwon"] is not None:
            val = args["price_manwon"]
            if val in allowed_amounts:
                stated_updates["price_manwon"] = val
            else:
                clean_args.pop("price_manwon", None)
                corrections_inc += 1

        # other_tenants_manwon 대조
        if "other_tenants_manwon" in args and args["other_tenants_manwon"] is not None:
            val = args["other_tenants_manwon"]
            if val in allowed_amounts:
                stated_updates["other_tenants_manwon"] = val
            else:
                clean_args.pop("other_tenants_manwon", None)
                corrections_inc += 1

        # vacant_rooms 대조
        if "vacant_rooms" in args and args["vacant_rooms"] is not None:
            val = args["vacant_rooms"]
            if val in allowed_ints:
                stated_updates["vacant_rooms"] = val
            else:
                clean_args.pop("vacant_rooms", None)
                corrections_inc += 1

        if stated_updates:
            review = await crud.get_review_for_update(session, r_id)
            if review:
                facts = ReviewFacts(review.facts)
                facts.stated.update(stated_updates)
                await crud.update_review_facts(session, r_id, facts.to_dict())

        if corrections_inc > 0:
            await crud.increment_review_corrections(session, r_id, corrections_inc)

        await session.commit()
        return clean_args


async def say(
    state: LoopState,
    text: str,
    service: AgentService | None = None,
) -> None:
    """말풍선 후검증·인용·저장 (JSD-MS-002#service_agent.say)."""
    svc = service or _agent_service
    r_id = _to_uuid(state.review_id)

    # 1. 문장으로 나눈다 (다., 요., ?, ! 뒤 공백 기준, 문장 끝의 {{entry:...}} 표식은 앞 문장에 붙임)
    pattern = r"(.*?(?:[다요\?!][.?!]*\s*\{\{entry:[^}]+\}\}[.?!]*|[다요\?!][.?!]*))(?:\s+|$)"
    matches = list(re.finditer(pattern, text.strip()))
    if not matches:
        sentences = [text.strip()] if text.strip() else []
    else:
        sentences = [m.group(1).strip() for m in matches if m.group(1).strip()]

    # 2. allowed 모으기
    rev_svc = svc.review_service()

    async with async_session_factory() as session:
        review = await crud.get_review(session, r_id)
        if not review:
            return

        facts = ReviewFacts(review.facts)
        allowed_amounts: set[int] = set()
        allowed_ratios: set[float] = set()

        if facts.rights:
            r = facts.rights
            if isinstance(r, dict):
                for k in ("senior_mortgage_manwon", "senior_lease_manwon", "other_tenants_manwon", "senior_total_manwon", "deposit_manwon", "price_manwon"):
                    if r.get(k) is not None:
                        allowed_amounts.add(r[k])
                if r.get("debt_ratio") is not None:
                    allowed_ratios.add(float(r["debt_ratio"]))
                if r.get("senior_ratio") is not None:
                    allowed_ratios.add(float(r["senior_ratio"]))

        if facts.price and isinstance(facts.price, dict):
            if facts.price.get("price_manwon") is not None:
                allowed_amounts.add(facts.price["price_manwon"])

        for st_val in facts.stated.values():
            if isinstance(st_val, int):
                allowed_amounts.add(st_val)

        allowed_amounts.add(review.deposit_manwon)

        entries = await svc.registry_service.entries(r_id, session=session)
        for e in entries:
            if e.amount_manwon is not None:
                allowed_amounts.add(e.amount_manwon)
            if e.price_manwon is not None:
                allowed_amounts.add(e.price_manwon)

        grade_level: GradeLevel | None = None
        if facts.check and isinstance(facts.check, dict):
            grade_obj = facts.check.get("grade")
            if grade_obj and isinstance(grade_obj, dict):
                lvl = grade_obj.get("level")
                if lvl:
                    grade_level = GradeLevel(lvl)

    # 3. 문장마다 factcheck.contradicts
    dropped_sentences = 0
    kept_sentences: list[str] = []
    for s in sentences:
        if factcheck.contradicts(s, allowed_amounts, allowed_ratios, grade_level):
            dropped_sentences += 1
        else:
            kept_sentences.append(s)

    # 4. 버린 문장이 있으면 안내 문장 붙이기
    if dropped_sentences > 0:
        kept_sentences.append(NUMBERS_FROM_TOOLS)

    if not kept_sentences:
        return

    processed_text = " ".join(kept_sentences)

    # 5. 인용 표식 해결
    message_id = str(uuid.uuid4())
    cited = await svc.citation_service.resolve_markers(
        r_id, processed_text, CitationUse.message, message_id
    )

    # 6. 교정 수 누적
    async with async_session_factory() as session:
        async with session.begin():
            await crud.increment_review_corrections(
                session, r_id, dropped_sentences + cited.dropped
            )

    # 7. 대화 메시지 기록
    await rev_svc.record(
        review_id=r_id,
        role=Role.agent,
        kind=MessageKind.say,
        text=cited.text,
        turn_id=state.turn_id,
        message_id=message_id,
    )


async def fetch_lookup(
    state: LoopState,
    call: ToolCall,
    service: AgentService | None = None,
) -> PriceLookup | BuildingLedger | DefaulterMatch | AppError:
    """조회 도구의 바깥 호출만 독립 세션으로 수행 (JSD-MS-002#service_agent.fetch_lookup)."""
    svc = service or _agent_service
    r_id = _to_uuid(state.review_id)

    try:
        model_cls = TOOL_ARG_MODELS.get(call.name)
        if not model_cls:
            return AppError("unknown_tool")
        args_obj = model_cls(**call.arguments)

        async with async_session_factory() as session:
            prop = await svc.registry_service.property(r_id, session=session)

        if call.name == "lookup_price":
            area = getattr(args_obj, "area_m2", None)
            return await svc.lookup_service.price(prop, area)

        elif call.name == "lookup_building":
            return await svc.lookup_service.building(prop)

        elif call.name == "match_defaulter":
            target = getattr(args_obj, "target", None)
            async with async_session_factory() as session:
                rev = await crud.get_review(session, r_id)
                owner = await svc.registry_service.owner(r_id, session=session)

            if target == "owner":
                name = owner.name if owner else None
            elif target == "counterparty":
                name = rev.counterparty_name if rev else None
            else:
                name = (rev.counterparty_name if rev else None) or (owner.name if owner else None)

            if not name:
                return AppError("no_name")
            return await svc.lookup_service.defaulter(name)

        return AppError("unknown_tool")

    except AppError as e:
        return e
    except Exception:
        return AppError("tool_failed")


async def dispatch(
    state: LoopState,
    call: ToolCall,
    fetched: object | None = None,
    service: AgentService | None = None,
) -> ToolResult:
    """도구 하나를 서비스로 보내고 봉투를 만든다 (JSD-MS-002#service_agent.dispatch)."""
    svc = service or _agent_service
    r_id = _to_uuid(state.review_id)
    name = call.name

    # 1. 관문 검사
    if name not in TOOL_ARG_MODELS:
        if state.phase == Phase.review:
            state.strikes += 1
        return ToolResult(ok=False, data=None, error="unknown_tool", summary=tool_summary(call, "unknown_tool"))

    if state.phase == Phase.follow_up and name not in ALLOWED_FOLLOW_UP_TOOLS:
        if name != "read_registry":
            return ToolResult(ok=False, data=None, error="unknown_tool", summary=tool_summary(call, "unknown_tool"))

    if not state.read_ok and name != "read_registry" and not state.forced:
        return ToolResult(ok=False, data=None, error="read_registry_first", summary=tool_summary(call, "read_registry_first"))

    try:
        arg_model = TOOL_ARG_MODELS[name](**call.arguments)
        args_dict = arg_model.model_dump()
    except Exception:
        if state.phase == Phase.review:
            state.strikes += 1
        return ToolResult(ok=False, data=None, error="unknown_tool", summary=tool_summary(call, "unknown_tool"))

    if name == "summarize_rights":
        args_dict = await check_stated(r_id, args_dict)

    # 2. 도구별 실행
    data: Any = None
    error_code: str | None = None
    tried_name = name

    rev_svc = svc.review_service()

    try:
        if name == "read_registry":
            doc_id = args_dict.get("document_id")
            reg = await svc.registry_service.read(r_id, doc_id)
            owner_matches = await rev_svc.owner_matches(r_id)
            reg_dict = asdict(reg)
            reg_dict["owner_matches_counterparty"] = owner_matches
            state.read_ok = True
            tried_name = f"read_registry:{reg.doc_kind.value}"
            data = reg_dict

        elif name == "summarize_rights":
            rights = await rev_svc.summarize_and_store(r_id)
            rights_dict = asdict(rights)
            await rev_svc.record(
                review_id=r_id,
                role=Role.agent,
                kind=MessageKind.numbers,
                text="",
                data=rights_dict,
                turn_id=state.turn_id,
            )
            data = rights_dict

        elif name == "check_signals":
            check = await rev_svc.check_and_store(r_id)
            data = {
                "grade": asdict(check.grade),
                "signals": [asdict(s) for s in check.signals],
            }

        elif name in ("lookup_price", "lookup_building", "match_defaulter"):
            if fetched is None:
                fetched = await fetch_lookup(state, call, svc)
            if isinstance(fetched, AppError):
                error_code = fetched.code
                async with async_session_factory() as session:
                    async with session.begin():
                        rev = await crud.get_review_for_update(session, r_id)
                        if rev:
                            facts = ReviewFacts(rev.facts)
                            facts.failures[name] = error_code
                            await crud.update_review_facts(session, r_id, facts.to_dict())
            else:
                data = asdict(fetched) if hasattr(fetched, "__dataclass_fields__") else fetched
                async with async_session_factory() as session:
                    async with session.begin():
                        rev = await crud.get_review_for_update(session, r_id)
                        if rev:
                            facts = ReviewFacts(rev.facts)
                            if name == "lookup_price":
                                facts.price = data
                            elif name == "lookup_building":
                                facts.building = data
                            elif name == "match_defaulter":
                                facts.defaulter = data
                            await crud.update_review_facts(session, r_id, facts.to_dict())

        elif name == "ask_user":
            ask_args = AskArgs(
                kind=QuestionKind(args_dict["kind"]),
                text=args_dict["text"],
                why=args_dict["why"],
                input_type=InputType(args_dict["input_type"]),
                options=args_dict.get("options"),
                help_url=args_dict.get("help_url"),
            )
            ans = await rev_svc.ask(r_id, ask_args)
            tried_name = f"ask_user:{args_dict['kind']}"
            data = asdict(ans)
            async with async_session_factory() as session:
                async with session.begin():
                    rev = await crud.get_review_for_update(session, r_id)
                    if rev:
                        facts = ReviewFacts(rev.facts)
                        facts.answers[args_dict["kind"]] = ans.answer
                        await crud.update_review_facts(session, r_id, facts.to_dict())

        elif name == "get_criteria":
            limits_obj = asdict(LIMITS)
            data = svc.rules_service.criteria(
                limits_obj, args_dict["topic"], args_dict.get("signal_code")
            )

        elif name == "write_report":
            async with async_session_factory() as session:
                prop = await svc.registry_service.property(r_id, session=session)
                rev = await crud.get_review(session, r_id)
                facts = ReviewFacts(rev.facts if rev else {})

            if state.phase == Phase.review and not state.forced and not state.required_returned:
                required_steps = svc.rules_service.required_steps(prop.building_type)
                missing = [s for s in required_steps if not _is_step_tried(s, facts.tried)]
                if missing:
                    state.required_returned = True
                    return ToolResult(
                        ok=False,
                        data={"missing": missing},
                        error="required_unchecked",
                        summary=tool_summary(call, "required_unchecked"),
                    )

            if state.phase == Phase.review:
                required_steps = svc.rules_service.required_steps(prop.building_type)
                rem = [s for s in required_steps if not _is_step_tried(s, facts.tried)]
                async with async_session_factory() as session:
                    async with session.begin():
                        rev = await crud.get_review_for_update(session, r_id)
                        if rev:
                            f = ReviewFacts(rev.facts)
                            f.raw["untried"] = rem
                            await crud.update_review_facts(session, r_id, f.to_dict())

            result = await rev_svc.write_report(
                review_id=r_id,
                agent_notes=args_dict.get("agent_notes"),
                revision_reason=args_dict.get("revision_reason"),
            )
            data = {
                "grade": result.grade.value if hasattr(result.grade, "value") else str(result.grade),
                "signal_count": result.signal_count,
                "unknown_count": result.unknown_count,
                "corrections": result.corrections,
                "rule_version": result.rule_version,
            }

    except AppError as e:
        logger.warning("dispatch %s AppError: %s", name, e.code)
        error_code = e.code
    except Exception as exc:
        logger.exception("dispatch %s unexpected error: %s", name, exc)
        error_code = "tool_failed"

    # 3. tried 기록 (required_unchecked 되돌림은 위에서 바로 return)
    async with async_session_factory() as session:
        async with session.begin():
            rev = await crud.get_review_for_update(session, r_id)
            if rev:
                facts = ReviewFacts(rev.facts)
                if tried_name not in facts.tried:
                    facts.tried.append(tried_name)
                    await crud.update_review_facts(session, r_id, facts.to_dict())

    # 4. 결과 반환
    ok = error_code is None
    masked_data = await mask_for_model(r_id, data, svc) if ok else None
    summary_text = tool_summary(call, data if ok else error_code)  # type: ignore

    return ToolResult(
        ok=ok,
        data=masked_data,
        error=error_code,
        summary=summary_text,
    )


async def force_report(
    state: LoopState,
    notice_code: str,
    service: AgentService | None = None,
) -> None:
    """한도에 닿으면 의견서를 강제로 쓴다 (JSD-MS-002#service_agent.force_report)."""
    svc = service or _agent_service
    r_id = _to_uuid(state.review_id)
    rev_svc = svc.review_service()

    # 1. notice 메시지
    await rev_svc.record(
        review_id=r_id,
        role=Role.system,
        kind=MessageKind.notice,
        text="",
        data={"code": notice_code},
        turn_id=state.turn_id,
    )

    # 2. dispatch write_report
    state.forced = True
    call = ToolCall(id="forced", name="write_report", arguments={})
    started = time.time()
    result = await dispatch(state, call, service=svc)

    # 3. tool 메시지 기록
    tool_card = ToolCard(
        tool=ToolName.write_report,
        status=ToolStatus.ok if result.ok else ToolStatus.failed,
        error_code=result.error,
        elapsed_ms=int((time.time() - started) * 1000),
        summary=result.summary,
        detail=result.data,
    )
    await rev_svc.record(
        review_id=r_id,
        role=Role.agent,
        kind=MessageKind.tool,
        text=result.summary,
        data=asdict(tool_card),
        turn_id=state.turn_id,
    )

    # 4. 검토 상태 종료
    status = ReviewStatus.done if result.ok else ReviewStatus.failed
    await rev_svc.finish(r_id, status)


async def run_tools(
    state: LoopState,
    calls: list[ToolCall],
    service: AgentService | None = None,
) -> bool:
    """한 차례의 도구 호출을 돈다 (JSD-MS-002#service_agent.run_tools)."""
    svc = service or _agent_service
    r_id = _to_uuid(state.review_id)
    rev_svc = svc.review_service()

    # 1. 잔여 도구 수 계산
    async with async_session_factory() as session:
        if state.phase == Phase.review:
            rev = await crud.get_review(session, r_id)
            current_calls = rev.tool_calls if rev else 0
            left = max(0, LIMITS.tool_calls - current_calls)
        else:
            assert state.turn_id is not None
            turn = await crud.get_follow_up_turn(session, state.turn_id)
            current_calls = turn.tool_calls if turn else 0
            left = max(0, LIMITS.follow_up_tools - current_calls)

    run = calls[:left]
    over = calls[left:]

    # 2. 동시 조회 대상 추출 및 병렬 호출
    lookups = [
        c for c in run
        if c.name in ("lookup_price", "lookup_building", "match_defaulter")
        and state.read_ok
    ]
    fetched_map: dict[str, Any] = {}
    if lookups:
        results = await asyncio.gather(*(fetch_lookup(state, c, svc) for c in lookups))
        for c, res in zip(lookups, results):
            fetched_map[c.id] = res

    # 3. 순차 디스패치
    for call in run:
        started = time.time()
        result = await dispatch(state, call, fetched=fetched_map.get(call.id), service=svc)

        # 카운터 증가
        async with async_session_factory() as session:
            async with session.begin():
                if state.phase == Phase.review:
                    await crud.increment_review_tool_calls(session, r_id)
                else:
                    assert state.turn_id is not None
                    await crud.increment_follow_up_tool_calls(session, state.turn_id)

        # ToolCard 기록
        tool_card = ToolCard(
            tool=ToolName(call.name),
            status=ToolStatus.ok if result.ok else ToolStatus.failed,
            error_code=result.error,
            elapsed_ms=int((time.time() - started) * 1000),
            summary=result.summary,
            detail=result.data,
        )
        await rev_svc.record(
            review_id=r_id,
            role=Role.agent,
            kind=MessageKind.tool,
            text=result.summary,
            data=asdict(tool_card),
            turn_id=state.turn_id,
        )

        # history에 tool 응답 봉투 추가
        envelope = {
            "ok": result.ok,
            "data": result.data,
            "error": result.error,
            "summary": result.summary,
        }
        state.history.append({
            "role": "tool",
            "call_id": call.id,
            "content": json.dumps(envelope, ensure_ascii=False, default=str),
        })

        if call.name == "write_report" and result.ok and state.phase == Phase.review:
            return True

    # 4. 초과 호출 처리
    if over:
        if state.phase == Phase.review:
            await force_report(state, "tool_limit", svc)
        else:
            for c in over:
                state.history.append({
                    "role": "tool",
                    "call_id": c.id,
                    "content": json.dumps({"ok": False, "error": "tool_limit"}, ensure_ascii=False),
                })

    return False


async def run_review(
    review_id: str | uuid.UUID,
    model: AgentModel,
    service: AgentService | None = None,
) -> None:
    """검토 단계 에이전트 루프 (JSD-MS-002#service_agent.run_review)."""
    svc = service or _agent_service
    r_id = _to_uuid(review_id)
    rev_svc = svc.review_service()

    # 1. 상태 running 갱신
    async with async_session_factory() as session:
        async with session.begin():
            updated = await crud.update_review_status_if_created(session, r_id)
            if updated == 0:
                return

    try:
        state = LoopState(
            review_id=str(r_id),
            phase=Phase.review,
            turn_id=None,
            model=model,
            history=[],
            strikes=0,
            required_returned=False,
            read_ok=False,
            forced=False,
        )

        # 첫 차례 사용자 메시지 구성
        async with async_session_factory() as session:
            rev = await crud.get_review(session, r_id)
            prop = await svc.registry_service.property(r_id, session=session)
            docs = await svc.registry_service.list(r_id, session=session)

        doc_summary = ", ".join(f"{d.kind.value}({d.label})" for d in docs)
        has_counterparty = "입력함" if (rev and rev.counterparty_name) else "입력 안 함"
        btype = prop.building_type.value if prop else "other"
        region_str = privacy.short_region(prop.region) if prop else ""
        deposit_str = money.format_manwon(rev.deposit_manwon) if rev else ""
        contract_str = rev.contract_type if rev else "jeonse"
        btype_label = {
            "apartment": "아파트",
            "officetel": "오피스텔",
            "multi_unit": "다세대/연립",
            "single_family": "단독/다가구",
        }.get(btype, btype)
        contract_label = {"jeonse": "전세", "monthly": "월세"}.get(contract_str, contract_str)

        first_turn_text = FIRST_TURN.format(
            deposit_fmt=deposit_str,
            contract_type_label=contract_label,
            has_counterparty=has_counterparty,
            building_type_label=btype_label,
            region=region_str,
            documents_summary=doc_summary,
        )

        state.history = [
            {"role": "system", "content": REVIEW_SYSTEM},
            {"role": "user", "content": first_turn_text},
        ]

        while True:
            async with async_session_factory() as session:
                rev = await crud.get_review(session, r_id)
                if not rev:
                    return

            if rev.tool_calls >= LIMITS.tool_calls:
                await force_report(state, "tool_limit", svc)
                break
            if rev.llm_cost_krw >= LIMITS.cost_krw:
                await force_report(state, "cost_limit", svc)
                break

            turn = await model.complete(state.history, REVIEW_TOOLS)

            # 비용 누적
            krw = usage_krw(turn.tokens_in, turn.tokens_out)
            async with async_session_factory() as session:
                async with session.begin():
                    await crud.increment_review_tokens_and_cost(
                        session, r_id, turn.tokens_in, turn.tokens_out, krw
                    )

            state.history.append({
                "role": "assistant",
                "content": turn.text or "",
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in turn.tool_calls
                ],
            })

            if turn.text:
                await say(state, turn.text, svc)

            if not turn.tool_calls:
                state.strikes += 1
                if state.strikes >= LIMITS.text_only_strikes:
                    await force_report(state, "text_only", svc)
                    break
                else:
                    state.history.append({"role": "user", "content": PICK_A_TOOL})
                    continue
            else:
                done = await run_tools(state, turn.tool_calls, svc)
                if done:
                    await rev_svc.finish(r_id, ReviewStatus.done)
                    break
                if state.forced:
                    break

    except Exception as exc:
        logger.exception("run_review failed: %s", exc)
        async with async_session_factory() as session:
            rev = await crud.get_review(session, r_id)
            if rev:
                await rev_svc.record(
                    review_id=r_id,
                    role=Role.system,
                    kind=MessageKind.error,
                    text="",
                    data={"code": "internal", "detail": "내부 오류가 발생했습니다."},
                )
                await rev_svc.finish(r_id, ReviewStatus.failed)


async def run_follow_up(
    review_id: str | uuid.UUID,
    turn_id: int,
    model: AgentModel,
    service: AgentService | None = None,
) -> None:
    """되묻기 한 차례 에이전트 루프 (JSD-MS-002#service_agent.run_follow_up)."""
    svc = service or _agent_service
    r_id = _to_uuid(review_id)
    rev_svc = svc.review_service()

    async with async_session_factory() as session:
        turn_row = await crud.get_follow_up_turn(session, turn_id, r_id)
        if not turn_row or turn_row.status != "running":
            return

    try:
        state = LoopState(
            review_id=str(r_id),
            phase=Phase.follow_up,
            turn_id=turn_id,
            model=model,
            history=[],
            strikes=0,
            required_returned=True,
            read_ok=True,
            forced=False,
        )

        allowed_tools = set(ALLOWED_FOLLOW_UP_TOOLS)
        if turn_row.document_id:
            allowed_tools.add("read_registry")
        tools_schema = [t for t in REVIEW_TOOLS if t["name"] in allowed_tools]

        # history 재구성
        async with async_session_factory() as session:
            records = await crud.list_review_records(session, r_id, after_seq=0, limit=200)

        history: list[dict[str, Any]] = [{"role": "system", "content": FOLLOW_UP_SYSTEM}]
        cites_map = await svc.citation_service.for_messages(r_id, [r.id for r in records])

        for r in records:
            if r.role == "user" and r.kind in ("say", "answer"):
                history.append({"role": "user", "content": r.text})
            elif r.role == "agent" and r.kind == "say":
                # {{c1}}을 {{entry:...}}로 되돌림
                restored_text = r.text
                rec_cites = cites_map.get(r.id, [])
                for cite in rec_cites:
                    if cite.entry_ids:
                        restored_text = restored_text.replace(
                            f"{{{{{cite.key}}}}}",
                            f"{{{{entry:{','.join(cite.entry_ids)}}}}}"
                        )
                history.append({"role": "assistant", "content": restored_text})
            elif r.kind == "tool":
                history.append({"role": "user", "content": f"[도구] {r.text} {json.dumps(r.data, ensure_ascii=False, default=str)}"})
            elif r.kind == "report":
                history.append({"role": "user", "content": f"[의견서] {json.dumps(r.data, ensure_ascii=False, default=str)}"})

        state.history = history
        asked_without_tools = False

        while True:
            async with async_session_factory() as session:
                rev = await crud.get_review(session, r_id)
                if not rev:
                    return
                if rev.llm_cost_krw >= LIMITS.cost_krw:
                    await rev_svc.record(
                        review_id=r_id,
                        role=Role.system,
                        kind=MessageKind.notice,
                        text="",
                        data={"code": "cost_limit"},
                        turn_id=turn_id,
                    )
                    break

                turn_row = await crud.get_follow_up_turn(session, turn_id)
                left = max(0, LIMITS.follow_up_tools - (turn_row.tool_calls if turn_row else 0))

            if left == 0 and not asked_without_tools:
                state.history.append({"role": "user", "content": ANSWER_WITHOUT_TOOLS})
                asked_without_tools = True

            current_tools = tools_schema if left > 0 else []
            turn = await model.complete(state.history, current_tools)

            krw = usage_krw(turn.tokens_in, turn.tokens_out)
            async with async_session_factory() as session:
                async with session.begin():
                    await crud.increment_review_tokens_and_cost(
                        session, r_id, turn.tokens_in, turn.tokens_out, krw
                    )

            state.history.append({
                "role": "assistant",
                "content": turn.text or "",
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in turn.tool_calls
                ],
            })

            if not turn.tool_calls:
                if turn.text:
                    await say(state, turn.text, svc)
                if turn.refused:
                    await rev_svc.record(
                        review_id=r_id,
                        role=Role.system,
                        kind=MessageKind.notice,
                        text="",
                        data={"code": "out_of_scope"},
                        turn_id=turn_id,
                    )
                break

            if left == 0:
                if turn.text:
                    await say(state, turn.text, svc)
                await rev_svc.record(
                    review_id=r_id,
                    role=Role.system,
                    kind=MessageKind.notice,
                    text="",
                    data={"code": "tool_limit"},
                    turn_id=turn_id,
                )
                break
            else:
                if turn.text:
                    await say(state, turn.text, svc)
                await run_tools(state, turn.tool_calls, svc)

        async with async_session_factory() as session:
            async with session.begin():
                await crud.update_follow_up_turn_status(
                    session, turn_id, "done", ended_at=datetime.now(timezone.utc)
                )
        await rev_svc.finish(r_id, ReviewStatus.done)

    except Exception as exc:
        logger.exception("run_follow_up failed: %s", exc)
        async with async_session_factory() as session:
            async with session.begin():
                turn_row = await crud.get_follow_up_turn(session, turn_id)
                if turn_row and turn_row.status == "running":
                    await crud.update_follow_up_turn_status(
                        session, turn_id, "failed", ended_at=datetime.now(timezone.utc)
                    )
