"""두 도메인 이상이 쓰는 순수 열거형과 DTO.

근거: JSD-DOM-002 2.8, 2.9, 4.14
규칙: DB·네트워크 없음. 아무것도 import하지 않는다.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum



# --- 2.9 열거형 ---


class ReviewStatus(StrEnum):
    """JSD-DOM-002 ReviewStatus."""

    created = "created"
    running = "running"
    waiting_user = "waiting_user"
    done = "done"
    failed = "failed"
    expired = "expired"


class ContractType(StrEnum):
    """JSD-DOM-002 ContractType."""

    jeonse = "jeonse"
    monthly = "monthly"


class Role(StrEnum):
    """JSD-DOM-002 Role."""

    agent = "agent"
    user = "user"
    system = "system"


class MessageKind(StrEnum):
    """JSD-DOM-002 MessageKind."""

    say = "say"
    tool = "tool"
    question = "question"
    answer = "answer"
    numbers = "numbers"
    report = "report"
    notice = "notice"
    error = "error"


class QuestionKind(StrEnum):
    """JSD-DOM-002 QuestionKind."""

    illegal_building = "illegal_building"
    price = "price"
    tenants = "tenants"
    proxy = "proxy"
    owner_type = "owner_type"
    land_registry = "land_registry"
    other = "other"


class InputType(StrEnum):
    """JSD-DOM-002 InputType."""

    choice = "choice"
    number = "number"
    text = "text"
    file = "file"


class QuestionStatus(StrEnum):
    """JSD-DOM-002 QuestionStatus."""

    pending = "pending"
    answered = "answered"
    timeout = "timeout"


class TurnStatus(StrEnum):
    """JSD-DOM-002 TurnStatus."""

    running = "running"
    done = "done"
    failed = "failed"


class DocKind(StrEnum):
    """JSD-DOM-002 DocKind."""

    building = "building"
    land = "land"
    collective = "collective"


class BuildingType(StrEnum):
    """JSD-DOM-002 BuildingType."""

    apartment = "apartment"
    multi_family_unit = "multi_family_unit"  # 연립/다세대
    multi_household = "multi_household"      # 다가구
    officetel = "officetel"
    other = "other"


class Section(StrEnum):
    """JSD-DOM-002 Section."""

    gap = "gap"
    eul = "eul"


class PurposeCode(StrEnum):
    """JSD-DOM-002 PurposeCode 15종."""

    ownership_preserve = "ownership_preserve"          # 소유권보존
    ownership_transfer = "ownership_transfer"          # 소유권이전
    mortgage = "mortgage"                              # (근)저당권설정
    mortgage_change = "mortgage_change"                # (근)저당권변경/이전
    jeonse_right = "jeonse_right"                      # 전세권설정
    lease_right = "lease_right"                        # 임차권등기명령
    seizure = "seizure"                                # 압류
    provisional_seizure = "provisional_seizure"        # 가압류
    injunction = "injunction"                          # 가처분
    provisional_registration = "provisional_registration"  # 가등기
    auction = "auction"                                # 경매개시결정
    trust = "trust"                                    # 신탁
    notice_registration = "notice_registration"        # 예고등기
    cancellation = "cancellation"                      # 말소등기
    other = "other"                                    # 기타


class CitationUse(StrEnum):
    """JSD-DOM-002 CitationUse."""

    message = "message"
    conclusion = "conclusion"
    rights = "rights"
    signal = "signal"
    checked = "checked"
    clause = "clause"


class LookupKind(StrEnum):
    """JSD-DOM-002 LookupKind."""

    trade = "trade"
    building = "building"


class GradeLevel(StrEnum):
    """JSD-DOM-002 GradeLevel."""

    safe = "safe"
    caution = "caution"
    danger = "danger"


class Severity(StrEnum):
    """JSD-DOM-002 Severity."""

    danger = "danger"
    caution = "caution"


class CheckResult(StrEnum):
    """JSD-DOM-002 CheckResult."""

    ok = "ok"
    unknown = "unknown"
    n_a = "n_a"


class UnknownReason(StrEnum):
    """JSD-DOM-002 UnknownReason."""

    lookup_failed = "lookup_failed"
    no_answer = "no_answer"
    no_data = "no_data"


class TodoStage(StrEnum):
    """JSD-DOM-002 TodoStage."""

    before = "before"
    signing = "signing"
    balance = "balance"
    after = "after"


# --- 2.8 DTO (shared 자리) ---


@dataclass(frozen=True)
class Error:
    """JSD-DOM-002 Error DTO."""

    code: str
    detail: str
    field: str | None = None


@dataclass(frozen=True)
class Limits:
    """JSD-DOM-002 Limits DTO."""

    tool_calls: int
    questions: int
    asks: int | None
    answer_timeout_sec: int
    file_mb: int
    pages: int
    retention_hours: int
    follow_up_tools: int
    ip_daily: int
    cost_krw: int
    text_only_strikes: int
    share_days: int


@dataclass(frozen=True)
class Upload:
    """JSD-DOM-002 Upload DTO."""

    data: bytes
    media_type: str
    filename: str


@dataclass(frozen=True)
class FileCheck:
    """JSD-DOM-002 FileCheck DTO."""

    file_sha256: str
    media_type: str
    page_count: int


@dataclass(frozen=True)
class ParsedDocument:
    """JSD-DOM-002 ParsedDocument DTO."""

    html: str
    page_count: int
    billed_pages: int


class PriceSource(StrEnum):
    """JSD-DOM-002 PriceSource."""

    trade_api = "trade_api"
    registry_sale = "registry_sale"
    user_input = "user_input"


class SeniorKind(StrEnum):
    """JSD-DOM-002 SeniorKind."""

    mortgage = "mortgage"
    jeonse_right = "jeonse_right"
    lease_right = "lease_right"
    tenant_deposit = "tenant_deposit"


class LedgerKind(StrEnum):
    """JSD-DOM-002 LedgerKind."""

    general = "general"
    collective = "collective"


class ProxyStatus(StrEnum):
    """JSD-DOM-002 ProxyStatus."""

    self = "self"
    proxy_with_poa = "proxy_with_poa"
    proxy_without_poa = "proxy_without_poa"
    unknown = "unknown"


class IllegalBuilding(StrEnum):
    """JSD-DOM-002 IllegalBuilding."""

    yes = "yes"
    no = "no"
    unknown = "unknown"


class OwnerType(StrEnum):
    """JSD-DOM-002 OwnerType."""

    individual = "individual"
    corporation = "corporation"
    unknown = "unknown"


class CriteriaTopic(StrEnum):
    """JSD-DOM-002 CriteriaTopic."""

    grade = "grade"
    signals = "signals"
    debt_ratio = "debt_ratio"
    required_checks = "required_checks"
    price_order = "price_order"
    priority_repayment = "priority_repayment"
    limits = "limits"
    sources = "sources"


class ToolName(StrEnum):
    """JSD-DOM-002 ToolName."""

    read_registry = "read_registry"
    summarize_rights = "summarize_rights"
    check_signals = "check_signals"
    lookup_price = "lookup_price"
    lookup_building = "lookup_building"
    match_defaulter = "match_defaulter"
    ask_user = "ask_user"
    get_criteria = "get_criteria"
    write_report = "write_report"


class ToolStatus(StrEnum):
    """JSD-DOM-002 ToolStatus."""

    running = "running"
    ok = "ok"
    failed = "failed"


class InputKind(StrEnum):
    """JSD-DOM-002 InputKind."""

    answer = "answer"
    ask = "ask"


class Phase(StrEnum):
    """JSD-DOM-002 Phase."""

    review = "review"
    follow_up = "follow_up"


# --- DTOs ---


@dataclass(frozen=True)
class SeniorClaim:
    """JSD-DOM-002 SeniorClaim DTO."""

    kind: SeniorKind
    amount_manwon: int
    entry_id: str
    holder: str | None = None


@dataclass(frozen=True)
class OtherTenants:
    """JSD-DOM-002 OtherTenants DTO."""

    households: int | None = None
    known_deposit_manwon: int | None = None
    vacant_rooms: int | None = None
    added_manwon: int = 0


@dataclass(frozen=True)
class PriceEstimate:
    """JSD-DOM-002 PriceEstimate DTO."""

    amount_manwon: int
    source: PriceSource
    period: str | None = None
    count: int | None = None


@dataclass(frozen=True)
class RightsSummary:
    """JSD-DOM-002 RightsSummary DTO."""

    senior_mortgage_manwon: int
    senior_lease_manwon: int
    other_tenants_manwon: int
    senior_total_manwon: int
    deposit_manwon: int
    price_manwon: int | None
    price_source: PriceSource | None
    debt_ratio: float | None
    senior_ratio: float | None
    multi_household_unknown: bool
    based_on: list[str]


@dataclass(frozen=True)
class RiskSignal:
    """JSD-DOM-002 RiskSignal DTO."""

    code: str
    severity: Severity
    label: str
    source: str
    entry_ids: list[str]
    source_date: date


@dataclass(frozen=True)
class UnknownItem:
    """JSD-DOM-002 UnknownItem DTO."""

    code: str
    reason: UnknownReason
    how_to_check: str


@dataclass(frozen=True)
class ChecklistItem:
    """JSD-DOM-002 ChecklistItem DTO."""

    code: str
    label: str
    result: CheckResult
    entry_ids: list[str]


@dataclass(frozen=True)
class Grade:
    """JSD-DOM-002 Grade DTO."""

    level: GradeLevel
    deciders: list[str]
    unknowns: list[str]
    rule_version: str


@dataclass(frozen=True)
class SignalCheck:
    """JSD-DOM-002 SignalCheck DTO."""

    grade: Grade
    signals: list[RiskSignal]
    checked: list[ChecklistItem]
    unknowns: list[UnknownItem]


@dataclass(frozen=True)
class EntryFact:
    """JSD-DOM-002 EntryFact DTO."""

    entry_id: str
    section: Section
    rank_no: str
    parent_entry_id: str | None = None
    purpose_code: PurposeCode = PurposeCode.other
    cause: str | None = None
    received_at: date | None = None
    amount_manwon: int | None = None
    price_manwon: int | None = None
    holder: str | None = None
    holder_is_corporation: bool | None = None
    cancelled: bool = False


@dataclass(frozen=True)
class PropertyFact:
    """JSD-DOM-002 PropertyFact DTO."""

    region: str
    building_type: BuildingType
    is_collective: bool
    land_right_unregistered: bool
    separate_land_registry: bool


@dataclass(frozen=True)
class RightsInput:
    """JSD-DOM-002 RightsInput DTO."""

    entries: list[EntryFact]
    deposit_manwon: int
    building_type: BuildingType
    region: str
    override_price_manwon: int | None = None
    trade_price_manwon: int | None = None
    user_price_manwon: int | None = None
    other_tenants_manwon: int | None = None
    vacant_rooms: int | None = None
    amount_overrides: dict[str, int] = field(default_factory=dict)
    today: date = field(default_factory=date.today)


@dataclass(frozen=True)
class SignalInput:
    """JSD-DOM-002 SignalInput DTO."""

    entries: list[EntryFact]
    property: PropertyFact
    rights: RightsSummary
    owner_matches_counterparty: bool | None = None
    proxy_status: ProxyStatus = ProxyStatus.unknown
    illegal_building: IllegalBuilding = IllegalBuilding.unknown
    owner_type: OwnerType = OwnerType.unknown
    ledger_main_use: str | None = None
    defaulter_matched: bool | None = None
    tenants_answered: bool = False
    failures: list[str] = field(default_factory=list)
    untried: list[str] = field(default_factory=list)
    today: date = field(default_factory=date.today)


@dataclass(frozen=True)
class Criteria:
    """JSD-DOM-002 Criteria DTO."""

    rule_version: str
    grades: dict[str, str] | None = None
    signals: list[dict] | None = None
    debt_ratio: dict | None = None
    required_checks: dict | None = None
    price_order: list[str] | None = None
    priority_repayment: dict | None = None
    checklist: dict | None = None
    limits: dict | None = None
    sources: list[dict] | None = None


@dataclass(frozen=True)
class ToolCall:
    """JSD-DOM-002 ToolCall DTO."""

    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class ModelTurn:
    """JSD-DOM-002 ModelTurn DTO."""

    text: str | None
    tool_calls: list[ToolCall]
    refused: bool
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True)
class PriceLookup:
    """JSD-DOM-002 PriceLookup DTO."""

    price_manwon: int
    count: int
    period: str
    source: PriceSource
    samples: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class BuildingLedger:
    """JSD-DOM-002 BuildingLedger DTO."""

    main_use: str
    ledger_kind: LedgerKind
    households: int | None = None
    families: int | None = None
    approved_at: date | None = None
    multiple_candidates: bool = False


@dataclass(frozen=True)
class DefaulterMatch:
    """JSD-DOM-002 DefaulterMatch DTO."""

    matched: bool
    match_count: int
    snapshot_date: date
    note: str = ""


@dataclass(frozen=True)
class SentenceRequest:
    """JSD-DOM-002 SentenceRequest DTO."""

    grade: Grade
    rights: RightsSummary
    signals: list[RiskSignal]
    agent_notes: str | None = None
    revision_reason: str | None = None


@dataclass(frozen=True)
class Sentences:
    """JSD-DOM-002 Sentences DTO."""

    conclusion: str
    explanations: dict[str, str]
    questions: list[str]
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True)
class ReportResult:
    """JSD-DOM-002 ReportResult DTO."""

    grade: GradeLevel
    signal_count: int
    unknown_count: int
    corrections: int
    rule_version: str
    revision_no: int
    revision_reason: str | None = None
    llm_fallback: bool = False
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass(frozen=True)
class AskArgs:
    """JSD-DOM-002 AskArgs DTO."""

    kind: QuestionKind
    text: str
    why: str
    input_type: InputType
    options: list[str] | None = None
    help_url: str | None = None


@dataclass(frozen=True)
class AskAnswer:
    """JSD-DOM-002 AskAnswer DTO."""

    question_id: str
    answer: str
    document_id: str | None = None


@dataclass(frozen=True)
class CitedText:
    """JSD-DOM-002 CitedText DTO."""

    text: str
    citations: list[dict]
    dropped: int


@dataclass(frozen=True)
class CitationRef:
    """JSD-DOM-002 CitationRef DTO."""

    used_in: CitationUse
    ref: str
    citation_id: str


@dataclass(frozen=True)
class BlockExcerpt:
    """JSD-DOM-002 BlockExcerpt DTO."""

    entry_id: str
    document_id: str
    excerpt: str

