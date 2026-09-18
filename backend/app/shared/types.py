"""두 도메인 이상이 쓰는 순수 열거형과 DTO.

근거: JSD-DOM-002 2.8, 2.9, 4.14
규칙: DB·네트워크 없음. 아무것도 import하지 않는다.
"""

from dataclasses import dataclass
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
