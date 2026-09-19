"""service_agent 단위 및 루프 테스트 (JSD-MS-002, JSD-DOM-002 4.2).

가짜 모델로 순서·한도·표식·가리기·동시 조회를 검증한다.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import uuid
import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LIMITS
from app.domains.citation.service import CitationService
from app.domains.registry.service import RegistryService
from app.domains.report.service import ReportService
from app.domains.review import crud, service_agent
from app.domains.review.models import Review, ReviewRecord
from app.domains.review.schemas import LoopState
from app.domains.review.service import ReviewService
from app.domains.review.service_agent import AgentService, mask_for_model, tool_summary
from app.domains.rules.service import RulesService
class FakeDocumentParser:
    def __init__(self, html: str = "<html></html>", page_count: int = 1) -> None:
        self.html = html
        self.page_count = page_count

    async def parse(self, data: bytes, media_type: str):
        from app.shared.types import ParsedDocument
        return ParsedDocument(html=self.html, page_count=self.page_count, billed_pages=self.page_count)
from app.shared.types import (
    BuildingType,
    CitationUse,
    ContractType,
    DocKind,
    GradeLevel,
    ModelTurn,
    Phase,
    ReviewStatus,
    ToolCall,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "registry" / "fixtures"


class FakeAgentModel:
    """테스트용 가짜 에이전트 모델."""

    def __init__(self, turns: list[ModelTurn] | None = None) -> None:
        self.turns = list(turns or [])
        self.turn_index = 0
        self.call_history: list[tuple[list[dict], list[dict]]] = []

    async def complete(
        self, history: list[dict], tools: list[dict]
    ) -> ModelTurn:
        self.call_history.append((list(history), list(tools)))
        if self.turn_index < len(self.turns):
            turn = self.turns[self.turn_index]
            self.turn_index += 1
            return turn
        # 기본 턴: 텍스트만 리턴
        return ModelTurn(
            text="검토를 완료합니다.",
            tool_calls=[],
            refused=False,
            tokens_in=10,
            tokens_out=10,
        )


@pytest.fixture
def mock_agent_services(db_session: AsyncSession):
    """테스트용 서비스 묶음 준비."""
    html_apartment = (FIXTURES_DIR / "apartment_safe.html").read_text(encoding="utf-8")
    fake_parser = FakeDocumentParser(html=html_apartment, page_count=2)
    reg_svc = RegistryService(parser=fake_parser)
    cite_svc = CitationService(registry_service=reg_svc)
    rep_svc = ReportService(citation_service=cite_svc)
    rules_svc = RulesService()

    agent_svc = AgentService(
        registry_service=reg_svc,
        citation_service=cite_svc,
        rules_service=rules_svc,
        report_service=rep_svc,
    )
    return agent_svc, reg_svc, cite_svc, rep_svc


@pytest.mark.asyncio
async def test_tool_summary_formatting():
    """tool_summary의 각 도구별 정상 및 에러 요약 문자열 검증."""
    call_read = ToolCall(id="c1", name="read_registry", arguments={})
    sum_read = tool_summary(
        call_read,
        {
            "building": {"building_type": "아파트"},
            "gap": [{"id": 1}],
            "eul": [{"id": 2, "cancelled": False}],
        },
    )
    assert "등기부 읽음: 아파트" in sum_read

    call_sum = ToolCall(id="c2", name="summarize_rights", arguments={})
    sum_res = tool_summary(
        call_sum,
        {"senior_total_manwon": 21000, "debt_ratio": 70.0},
    )
    assert "선순위 2.1억" in sum_res
    assert "부채비율 70.0%" in sum_res

    # 에러 문자열 처리
    err_sum = tool_summary(call_read, "read_registry_first")
    assert "등기부 읽기 실패: 등기부 먼저 읽기 필요" in err_sum


@pytest.mark.asyncio
async def test_mask_for_model_privacy(db_session: AsyncSession, mock_agent_services):
    """mask_for_model의 개인정보 가리기(법인 유지, 지번/주민번호 삭제 등) 검증."""
    agent_svc, reg_svc, _, _ = mock_agent_services
    review_id = str(uuid.uuid4())
    rev_uuid = uuid.UUID(review_id)

    # 검토 생성
    await db_session.execute(
        insert(Review).values(
            id=rev_uuid,
            status="created",
            deposit_manwon=15000,
            contract_type="jeonse",
            facts={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    # 등기부 등록
    html_apartment = (FIXTURES_DIR / "apartment_safe.html").read_text(encoding="utf-8")
    await reg_svc.create_extract(
        review_id=rev_uuid,
        html=html_apartment,
        page_count=2,
        file_sha256="fake_sha_mask",
        session=db_session,
    )
    await db_session.commit()

    data = {
        "building": {
            "region": "서울특별시 강서구 화곡동 123-45",
            "building_name": "화곡아파트 101동",
            "lot_address": "화곡동 123-45",
            "exclusive_area_m2": 84.5,
        },
        "gap": [
            {
                "holder": "김민수",
                "holder_is_corporation": False,
                "section": "gap",
                "parent_entry_id": None,
                "memo": "주민번호 900101-1234567 포함",
            },
            {
                "holder": "국민은행",
                "holder_is_corporation": True,
                "section": "gap",
            },
            {
                "holder": "홍길동",
                "holder_is_corporation": False,
                "section": "gap",
            },
        ],
    }

    masked = await mask_for_model(review_id, data, agent_svc)
    assert masked is not None

    # 내부 필드 제외 확인
    assert "building_name" not in masked["building"]
    assert "lot_address" not in masked["building"]
    assert "exclusive_area_m2" not in masked["building"]
    assert masked["building"]["region"] == "서울 강서구 화곡동"

    # 개인 이름 마스킹 확인
    gap_entries = masked["gap"]
    assert gap_entries[0]["holder"].startswith("개인 ")
    assert gap_entries[1]["holder"] == "국민은행"
    assert gap_entries[2]["holder"] == "개인"
    # 주민번호 마스킹 확인
    assert "900101-1234567" not in gap_entries[0]["memo"]


@pytest.mark.asyncio
async def test_run_review_flow_success(db_session: AsyncSession, mock_agent_services):
    """정상적인 3단계 도구 호출(read -> summarize -> write) 후 done 완료 및 의견서 생성."""
    agent_svc, reg_svc, _, _ = mock_agent_services
    review_id = str(uuid.uuid4())
    rev_uuid = uuid.UUID(review_id)

    # 1. 검토 생성
    await db_session.execute(
        insert(Review).values(
            id=rev_uuid,
            status="created",
            deposit_manwon=15000,
            contract_type="jeonse",
            counterparty_name="홍길동",
            facts={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    html_apartment = (FIXTURES_DIR / "apartment_safe.html").read_text(encoding="utf-8")
    await reg_svc.create_extract(
        review_id=rev_uuid,
        html=html_apartment,
        page_count=2,
        file_sha256="fake_sha_run_review",
        session=db_session,
    )
    await db_session.commit()

    # 가짜 모델 응답 순서:
    # 1턴: read_registry
    # 2턴: summarize_rights, lookup_price (동시 호출 가능)
    # 3턴: check_signals, match_defaulter
    # 4턴: write_report
    fake_turns = [
        ModelTurn(
            text="등기부를 확인하겠습니다.",
            tool_calls=[ToolCall(id="call_1", name="read_registry", arguments={})],
            refused=False,
            tokens_in=50,
            tokens_out=20,
        ),
        ModelTurn(
            text="권리를 합산하고 시세를 조회합니다.",
            tool_calls=[
                ToolCall(id="call_2", name="summarize_rights", arguments={}),
                ToolCall(id="call_3", name="lookup_price", arguments={}),
            ],
            refused=False,
            tokens_in=60,
            tokens_out=30,
        ),
        ModelTurn(
            text="신호를 판정하고 채무자를 대조합니다.",
            tool_calls=[
                ToolCall(id="call_4", name="check_signals", arguments={}),
                ToolCall(id="call_5", name="match_defaulter", arguments={}),
            ],
            refused=False,
            tokens_in=70,
            tokens_out=30,
        ),
        ModelTurn(
            text="최종 의견서를 작성합니다.",
            tool_calls=[ToolCall(id="call_6", name="write_report", arguments={})],
            refused=False,
            tokens_in=80,
            tokens_out=40,
        ),
    ]
    model = FakeAgentModel(turns=fake_turns)

    await service_agent.run_review(review_id, model, service=agent_svc)

    # 상태 및 메시지 검증
    rev = await crud.get_review(db_session, rev_uuid)
    assert rev is not None
    assert rev.status == "done"
    assert rev.tokens_in > 0
    assert rev.tokens_out > 0

    records = await crud.list_review_records(db_session, rev_uuid, after_seq=0, limit=100)
    kinds = [r.kind for r in records]
    assert "tool" in kinds
    assert "report" in kinds

    # 첫 차례 사용자 메시지에 실명/지번이 없음을 검증
    first_history = model.call_history[0][0]
    first_user_msg = next(m["content"] for m in first_history if m["role"] == "user")
    assert "홍길동" not in first_user_msg


@pytest.mark.asyncio
async def test_run_review_text_only_strikes(db_session: AsyncSession, mock_agent_services):
    """모델이 도구를 안 부르고 말만 3번 하면 text_only notice 발행 후 강제 종료."""
    agent_svc, reg_svc, _, _ = mock_agent_services
    review_id = str(uuid.uuid4())
    rev_uuid = uuid.UUID(review_id)

    await db_session.execute(
        insert(Review).values(
            id=rev_uuid,
            status="created",
            deposit_manwon=15000,
            contract_type="jeonse",
            facts={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    html_apartment = (FIXTURES_DIR / "apartment_safe.html").read_text(encoding="utf-8")
    await reg_svc.create_extract(
        review_id=rev_uuid,
        html=html_apartment,
        page_count=2,
        file_sha256="fake_sha_strikes",
        session=db_session,
    )
    await db_session.commit()

    # 도구 없이 텍스트만 3회 반환
    fake_turns = [
        ModelTurn(text="도구를 안 고르고 인사만 1", tool_calls=[], refused=False, tokens_in=10, tokens_out=10),
        ModelTurn(text="도구를 안 고르고 인사만 2", tool_calls=[], refused=False, tokens_in=10, tokens_out=10),
        ModelTurn(text="도구를 안 고르고 인사만 3", tool_calls=[], refused=False, tokens_in=10, tokens_out=10),
    ]
    model = FakeAgentModel(turns=fake_turns)

    await service_agent.run_review(review_id, model, service=agent_svc)

    rev = await crud.get_review(db_session, rev_uuid)
    assert rev is not None
    assert rev.status == "done"

    records = await crud.list_review_records(db_session, rev_uuid, after_seq=0, limit=100)
    notices = [r for r in records if r.kind == "notice"]
    assert len(notices) > 0
    assert notices[0].data.get("code") == "text_only"
