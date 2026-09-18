"""OpenAISentenceWriter 단위 테스트.

항목 ID: JSD-MS-013#OpenAISentenceWriter
근거: JSD-MS-013 테스트 관점
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.domains.report.adapters.openai_writer import OpenAISentenceWriter
from app.shared.types import (
    Grade,
    GradeLevel,
    PriceSource,
    RightsSummary,
    RiskSignal,
    SentenceRequest,
    Severity,
)


@pytest.fixture
def sample_request() -> SentenceRequest:
    grade = Grade(
        level=GradeLevel.caution,
        deciders=["senior_heavy"],
        unknowns=[],
        rule_version="2026.09.1",
    )
    rights = RightsSummary(
        senior_mortgage_manwon=7000,
        senior_lease_manwon=0,
        other_tenants_manwon=0,
        senior_total_manwon=7000,
        deposit_manwon=15000,
        price_manwon=25000,
        price_source=PriceSource.trade_api,
        debt_ratio=0.88,
        senior_ratio=0.28,
        multi_household_unknown=False,
        based_on=["eul-1"],
    )
    signals = [
        RiskSignal(
            code="senior_heavy",
            severity=Severity.caution,
            label="선순위 채권 과다",
            source="HUG",
            entry_ids=["eul-1"],
            source_date=date(2026, 9, 1),
        )
    ]
    return SentenceRequest(
        grade=grade,
        rights=rights,
        signals=signals,
        agent_notes="임대인이 법인일 가능성 있음",
        revision_reason=None,
    )


@pytest.mark.asyncio
async def test_openai_writer_success(sample_request):
    """가짜 응답 JSON -> Sentences 정상 파싱."""
    mock_client = MagicMock()
    mock_responses = AsyncMock()
    mock_client.responses = mock_responses

    fake_json = """
    {
        "conclusion": "보증금 1억 5,000만 원을 넣기 전에 확인할 것이 있습니다. 선순위 채권 과다. {{entry:eul-1}}",
        "explanations": [
            {"code": "senior_heavy", "text": "선순위 채권이 집값의 60%를 초과합니다."}
        ],
        "questions": [
            "선순위 근저당권을 잔금 시점에 말소하기로 약정하셨나요?",
            "전세보증금 반환보증보험 가입 여부를 확인하셨나요?",
            "국세 완납증명서를 요청하셨나요?"
        ]
    }
    """
    fake_resp = SimpleNamespace(
        output_text=fake_json,
        usage=SimpleNamespace(input_tokens=200, output_tokens=90),
    )
    mock_responses.create.return_value = fake_resp

    writer = OpenAISentenceWriter(client=mock_client)
    sentences = await writer.write(sample_request)

    assert "보증금 1억 5,000만 원" in sentences.conclusion
    assert "{{entry:eul-1}}" in sentences.conclusion
    assert "senior_heavy" in sentences.explanations
    assert sentences.explanations["senior_heavy"] == "선순위 채권이 집값의 60%를 초과합니다."
    assert len(sentences.questions) == 3
    assert sentences.tokens_in == 200
    assert sentences.tokens_out == 90


@pytest.mark.asyncio
async def test_openai_writer_invalid_json_raises(sample_request):
    """스키마에 안 맞는 JSON 또는 깨진 문자열 -> 예외 발생."""
    mock_client = MagicMock()
    mock_responses = AsyncMock()
    mock_client.responses = mock_responses

    fake_resp = SimpleNamespace(
        output_text="이것은 JSON이 아닙니다.",
        usage=SimpleNamespace(input_tokens=50, output_tokens=10),
    )
    mock_responses.create.return_value = fake_resp

    writer = OpenAISentenceWriter(client=mock_client)
    with pytest.raises(Exception):
        await writer.write(sample_request)


@pytest.mark.asyncio
async def test_openai_writer_input_privacy(sample_request):
    """입력 JSON에 개인 이름이나 주민번호가 없음을 확인."""
    mock_client = MagicMock()
    mock_responses = AsyncMock()
    mock_client.responses = mock_responses

    fake_resp = SimpleNamespace(
        output_text='{"conclusion": "결론", "explanations": [], "questions": []}',
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )
    mock_responses.create.return_value = fake_resp

    writer = OpenAISentenceWriter(client=mock_client)
    await writer.write(sample_request)

    # create 호출 인자 검증
    call_kwargs = mock_responses.create.call_args.kwargs
    sent_input = call_kwargs["input"]
    assert "홍길동" not in sent_input
    assert "김철수" not in sent_input
    assert "900101-1" not in sent_input
