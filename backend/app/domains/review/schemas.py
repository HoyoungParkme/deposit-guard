"""Review 도메인 DTO 및 스키마.

근거: JSD-DOM-002 2.8, JSD-API-001, JSD-MS-001
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import json
from typing import Any, TYPE_CHECKING
from pydantic import BaseModel
from app.shared.types import (
    AskAnswer,
    AskArgs,
    BuildingType,
    Citation,
    ContractType,
    DocKind,
    GradeLevel,
    InputKind,
    InputType,
    MessageKind,
    Phase,
    QuestionKind,
    ReviewStatus,
    Role,
    ToolName,
    ToolStatus,
    Upload,
)

if TYPE_CHECKING:
    from app.domains.review.ports import AgentModel


@dataclass(frozen=True)
class ReviewCreated:
    """검토 생성 응답 DTO (JSD-DOM-002 2.8 ReviewCreated)."""

    review_id: str
    status: ReviewStatus
    is_sample: bool
    expires_at: datetime


@dataclass(frozen=True)
class QuestionDTO:
    """질문 DTO (JSD-DOM-002 2.8 Question)."""

    question_id: str
    kind: QuestionKind
    text: str
    why: str
    input_type: InputType
    options: list[str] | None
    help_url: str | None
    asked_no: int


@dataclass(frozen=True)
class ReviewSubject:
    """검토 대상 DTO."""

    building_type: BuildingType
    deposit_manwon: int
    contract_type: ContractType
    region: str


@dataclass(frozen=True)
class ReviewCounters:
    """진행 카운터 DTO."""

    tool_calls: int
    questions_asked: int
    asks_used: int
    elapsed_sec: int
    cost_krw: int


@dataclass(frozen=True)
class ReviewDocumentItem:
    """문서 요약 항목 DTO (page_count 제외)."""

    document_id: str
    kind: DocKind
    label: str


@dataclass(frozen=True)
class ReviewView:
    """상단 바 요약과 진행 수치 DTO (JSD-DOM-002 2.8 ReviewView)."""

    review_id: str
    status: ReviewStatus
    subject: ReviewSubject
    counters: ReviewCounters
    pending_question: QuestionDTO | None
    documents: list[ReviewDocumentItem]
    has_report: bool
    expires_at: datetime


class CreateReviewResponse(BaseModel):
    """POST /api/reviews 응답 모델 (JSD-API-001 3장)."""

    review_id: str
    status: ReviewStatus
    is_sample: bool
    expires_at: datetime


class ReviewSubjectResponse(BaseModel):
    building_type: BuildingType
    deposit_manwon: int
    contract_type: ContractType
    region: str


class ReviewCountersResponse(BaseModel):
    tool_calls: int
    questions_asked: int
    asks_used: int
    elapsed_sec: int
    cost_krw: int


class ReviewDocumentResponse(BaseModel):
    document_id: str
    kind: DocKind
    label: str


class QuestionResponse(BaseModel):
    question_id: str
    kind: QuestionKind
    text: str
    why: str
    input_type: InputType
    options: list[str] | None = None
    help_url: str | None = None
    asked_no: int


class ReviewViewResponse(BaseModel):
    """GET /api/reviews/{id} 응답 모델 (JSD-API-001 3장)."""

    review_id: str
    status: ReviewStatus
    subject: ReviewSubjectResponse
    counters: ReviewCountersResponse
    pending_question: QuestionResponse | None = None
    documents: list[ReviewDocumentResponse]
    has_report: bool
    expires_at: datetime


@dataclass(frozen=True)
class Message:
    """대화 메시지 DTO (JSD-DOM-002 2.8 Message)."""

    message_id: str
    seq: int
    role: Role
    kind: MessageKind
    text: str
    citations: list[Citation] = field(default_factory=list)
    data: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ToolCard:
    """도구 카드 DTO (JSD-DOM-002 2.8 ToolCard)."""

    tool: ToolName
    status: ToolStatus
    error_code: str | None = None
    elapsed_ms: int = 0
    summary: str = ""
    detail: dict[str, Any] | None = None


@dataclass(frozen=True)
class AnswerData:
    """답변 메시지 data DTO (JSD-DOM-002 2.8 AnswerData)."""

    question_id: str | None = None
    choice: str | None = None
    text: str | None = None
    document_id: str | None = None


@dataclass(frozen=True)
class ReportCard:
    """의견서 카드 data DTO (JSD-DOM-002 2.8 ReportCard)."""

    grade: GradeLevel
    signal_count: int
    unknown_count: int
    rule_version: str
    revision_no: int
    revision_reason: str | None = None


@dataclass(frozen=True)
class NoticeData:
    """안내 메시지 data DTO (JSD-DOM-002 2.8 NoticeData)."""

    code: str


@dataclass(frozen=True)
class MessagesPage:
    """대화 페이지 DTO (JSD-DOM-002 2.8 MessagesPage)."""

    messages: list[Message]
    next_seq: int
    status: ReviewStatus


@dataclass(frozen=True)
class StreamEvent:
    """스트림 이벤트 DTO (JSD-DOM-002 2.8 StreamEvent)."""

    event: str
    id: int | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        """Format as Server-Sent Event string."""
        lines: list[str] = []
        if self.event:
            lines.append(f"event: {self.event}")
        if self.id is not None:
            lines.append(f"id: {self.id}")
        lines.append(f"data: {json.dumps(self.data, default=str, ensure_ascii=False)}")
        return "\n".join(lines) + "\n\n"


@dataclass(frozen=True)
class UserInput:
    """사용자 입력 DTO (JSD-DOM-002 2.8 UserInput)."""

    kind: InputKind
    question_id: str | None = None
    text: str | None = None
    choice: str | None = None
    file: Upload | None = None


@dataclass(frozen=True)
class Accepted:
    """입력 접수 응답 DTO (JSD-DOM-002 2.8 Accepted)."""

    message_id: str
    seq: int
    turn_id: int | None = None


@dataclass(frozen=True)
class EntryOverride:
    """등기 항목 수정 DTO."""

    entry_id: str
    amount_manwon: int


@dataclass(frozen=True)
class ValueOverrides:
    """시세·금액 직접 입력 DTO (JSD-DOM-002 2.8 ValueOverrides)."""

    price_manwon: int | None = None
    entries: list[EntryOverride] = field(default_factory=list)


@dataclass(frozen=True)
class ToolResult:
    """도구 실행 결과 봉투 DTO (JSD-DOM-002 2.8 ToolResult)."""

    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    summary: str = ""


@dataclass
class LoopState:
    """에이전트 루프 메모리 상태 (JSD-DOM-002 2.8 LoopState)."""

    review_id: str
    phase: Phase
    turn_id: int | None
    model: "AgentModel"
    history: list[dict[str, Any]] = field(default_factory=list)
    strikes: int = 0
    required_returned: bool = False
    read_ok: bool = False
    forced: bool = False


@dataclass(frozen=True)
class UsageSummary:
    """사용량 요약 DTO (JSD-DOM-002 2.8 UsageSummary)."""

    day: date
    reviews: int
    failed: int
    avg_cost_krw: int


class ReviewFacts:
    """Review.facts JSON 래퍼 (JSD-DOM-002 2.8 ReviewFacts)."""

    def __init__(self, raw: dict[str, Any] | None = None) -> None:
        self.raw = dict(raw or {})

    @property
    def stated(self) -> dict[str, Any]:
        return self.raw.setdefault("stated", {})

    @property
    def answers(self) -> dict[str, str]:
        return self.raw.setdefault("answers", {})

    @property
    def price(self) -> dict[str, Any] | None:
        return self.raw.get("price")

    @price.setter
    def price(self, val: Any) -> None:
        self.raw["price"] = val

    @property
    def building(self) -> dict[str, Any] | None:
        return self.raw.get("building")

    @building.setter
    def building(self, val: Any) -> None:
        self.raw["building"] = val

    @property
    def defaulter(self) -> dict[str, Any] | None:
        return self.raw.get("defaulter")

    @defaulter.setter
    def defaulter(self, val: Any) -> None:
        self.raw["defaulter"] = val

    @property
    def failures(self) -> dict[str, str]:
        return self.raw.setdefault("failures", {})

    @property
    def overrides(self) -> dict[str, Any]:
        return self.raw.setdefault("overrides", {})

    @property
    def rights(self) -> dict[str, Any] | None:
        return self.raw.get("rights")

    @rights.setter
    def rights(self, val: Any) -> None:
        self.raw["rights"] = val

    @property
    def check(self) -> dict[str, Any] | None:
        return self.raw.get("check")

    @check.setter
    def check(self, val: Any) -> None:
        self.raw["check"] = val

    @property
    def tried(self) -> list[str]:
        return self.raw.setdefault("tried", [])

    @property
    def untried(self) -> list[str]:
        return self.raw.setdefault("untried", [])

    def to_dict(self) -> dict[str, Any]:
        return self.raw


# --- 도구 인자 모델 (JSD-API-002 3장) ---


class ReadRegistryArgs(BaseModel):
    document_id: str | None = None


class SummarizeRightsArgs(BaseModel):
    price_manwon: int | None = None
    other_tenants_manwon: int | None = None
    vacant_rooms: int | None = None


class CheckSignalsArgs(BaseModel):
    pass


class LookupPriceArgs(BaseModel):
    area_m2: float | None = None


class LookupBuildingArgs(BaseModel):
    pass


class MatchDefaulterArgs(BaseModel):
    target: str | None = None


class AskUserArgs(BaseModel):
    kind: str
    text: str
    why: str
    input_type: str
    options: list[str] | None = None
    help_url: str | None = None


class GetCriteriaArgs(BaseModel):
    topic: str
    signal_code: str | None = None


class WriteReportArgs(BaseModel):
    agent_notes: str | None = None
    revision_reason: str | None = None


TOOL_ARG_MODELS: dict[str, type[BaseModel]] = {
    "read_registry": ReadRegistryArgs,
    "summarize_rights": SummarizeRightsArgs,
    "check_signals": CheckSignalsArgs,
    "lookup_price": LookupPriceArgs,
    "lookup_building": LookupBuildingArgs,
    "match_defaulter": MatchDefaulterArgs,
    "ask_user": AskUserArgs,
    "get_criteria": GetCriteriaArgs,
    "write_report": WriteReportArgs,
}


REVIEW_TOOLS: list[dict] = [
    {
        "name": "read_registry",
        "description": "올라온 등기부를 표제부·갑구·을구 항목으로 읽는다. 검토의 첫 호출이어야 한다. 토지 등기부가 추가로 올라오면 document_id를 넣어 다시 부른다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "읽을 문서. 생략하면 아직 읽지 않은 첫 문서",
                }
            },
            "required": [],
        },
    },
    {
        "name": "summarize_rights",
        "description": "말소 제외 선순위를 채권최고액으로 합산하고 주택 가격이 있으면 부채비율을 낸다. 가격과 다른 세입자 보증금은 생략하면 서버가 조회 결과와 답변에서 정해진 순서로 채운다. 사용자가 대화에서 직접 말한 값만 인자로 넣는다. 서버가 이 검토의 사용자 메시지·답변에 그 값이 있는지 대조하고 없으면 그 인자를 버린다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "price_manwon": {
                    "type": "integer",
                    "description": "사용자가 대화에서 말한 시세. 없으면 생략",
                },
                "other_tenants_manwon": {
                    "type": "integer",
                    "description": "사용자가 말한 다른 세입자 보증금 합. 없으면 생략",
                },
                "vacant_rooms": {
                    "type": "integer",
                    "description": "다가구 빈 방 수. 사용자가 말했을 때만",
                },
            },
            "required": [],
        },
    },
    {
        "name": "check_signals",
        "description": "규칙표로 위험 신호와 등급을 정한다. 결과는 바꿀 수 없다. 인자는 없다. 질문 답변과 명단 대조 결과는 서버가 채운다. 대리 여부·위반건축물·임대인 유형은 ask_user의 답으로만 정해진다.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "lookup_price",
        "description": "국토부 실거래가에서 최근 12개월 같은 단지·유사 면적 매매를 찾는다. 주소와 건물 종류는 서버가 채운다. lookup_building, match_defaulter와 한 턴에 함께 부를 수 있다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "area_m2": {
                    "type": "number",
                    "description": "전용면적을 알 때만. 생략하면 등기부 값",
                }
            },
            "required": [],
        },
    },
    {
        "name": "lookup_building",
        "description": "건축HUB에서 주용도·대장 구분·가구수·세대수·사용승인일을 조회한다. 위반건축물 여부는 이 경로로 오지 않으므로 필요하면 ask_user로 묻는다. 주소는 서버가 채운다.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "match_defaulter",
        "description": "HUG 상습 채무불이행자 공개 명단과 이름을 완전 일치로 대조한다. 이름은 서버가 채우며 모델에는 결과만 온다. 일치는 동명이인일 수 있다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": ["owner", "counterparty"],
                    "description": "생략하면 계약 상대방, 없으면 소유자",
                }
            },
            "required": [],
        },
    },
    {
        "name": "ask_user",
        "description": "서류와 조회로 알 수 없는 것을 한 번 묻는다. 대화가 멈추고 답이 오면 재개된다. 한 검토에 최대 5회. 이유 없는 질문은 하지 않는다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": [
                        "illegal_building",
                        "price",
                        "tenants",
                        "proxy",
                        "owner_type",
                        "land_registry",
                        "other",
                    ],
                },
                "text": {"type": "string", "description": "질문 한 문장"},
                "why": {"type": "string", "description": "왜 묻는지 한 문장"},
                "input_type": {
                    "type": "string",
                    "enum": ["choice", "number", "text", "file"],
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "help_url": {"type": "string"},
            },
            "required": ["kind", "text", "why", "input_type"],
        },
    },
    {
        "name": "get_criteria",
        "description": "판정 규칙과 공식 출처를 조회한다. 사용자가 기준·이유를 되물을 때 규칙을 지어내지 않고 이 결과로만 답한다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": [
                        "grade",
                        "signals",
                        "debt_ratio",
                        "required_checks",
                        "price_order",
                        "priority_repayment",
                        "limits",
                        "sources",
                    ],
                },
                "signal_code": {
                    "type": "string",
                    "description": "특정 신호의 규칙만 볼 때",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "write_report",
        "description": "등급·신호·합산·답변으로 의견서를 만든다. 검토 단계의 마지막 호출이다. 되묻기 단계에서 값이 바뀌어 summarize_rights·check_signals를 다시 불렀다면 revision_reason을 넣어 다시 부른다. 숫자와 등급은 도구 출력 그대로 쓰인다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_notes": {
                    "type": "string",
                    "description": "특이사항 메모. 없으면 생략",
                },
                "revision_reason": {
                    "type": "string",
                    "description": "되묻기에서 다시 쓸 때 이유",
                },
            },
            "required": [],
        },
    },
]

