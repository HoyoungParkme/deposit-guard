"""OpenAIAgentModel 단위 테스트.

항목 ID: JSD-MS-013#OpenAIAgentModel
근거: JSD-MS-013 테스트 관점
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest
from openai import APIStatusError

from app.domains.review.adapters.openai_agent import OpenAIAgentModel


@pytest.mark.asyncio
async def test_openai_agent_tool_calls_and_text():
    """가짜 SDK 응답(function_call 2개 + 글) -> ToolCall 2개와 text."""
    mock_client = MagicMock()
    mock_responses = AsyncMock()
    mock_client.responses = mock_responses

    fake_resp = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_1",
                name="check_registry",
                arguments='{"document_id": "doc-1"}',
            ),
            SimpleNamespace(
                type="function_call",
                call_id="call_2",
                name="lookup_price",
                arguments='{"region_code": "11680"}',
            ),
        ],
        output_text="등기부 확인과 시세 조회를 진행합니다.",
        usage=SimpleNamespace(input_tokens=150, output_tokens=80),
    )
    mock_responses.create.return_value = fake_resp

    model = OpenAIAgentModel(client=mock_client)
    turn = await model.complete(
        history=[{"role": "user", "content": "분석을 시작해줘"}],
        tools=[{"name": "check_registry", "inputSchema": {}}],
    )

    assert len(turn.tool_calls) == 2
    assert turn.tool_calls[0].name == "check_registry"
    assert turn.tool_calls[0].arguments == {"document_id": "doc-1"}
    assert turn.tool_calls[1].name == "lookup_price"
    assert turn.tool_calls[1].arguments == {"region_code": "11680"}
    assert turn.text == "등기부 확인과 시세 조회를 진행합니다."
    assert turn.refused is False
    assert turn.tokens_in == 150
    assert turn.tokens_out == 80


@pytest.mark.asyncio
async def test_openai_agent_broken_arguments():
    """깨진 arguments -> 빈 딕셔너리 {}."""
    mock_client = MagicMock()
    mock_responses = AsyncMock()
    mock_client.responses = mock_responses

    fake_resp = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_broken",
                name="test_tool",
                arguments="INVALID_JSON{",
            )
        ],
        output_text="",
        usage=SimpleNamespace(input_tokens=50, output_tokens=20),
    )
    mock_responses.create.return_value = fake_resp

    model = OpenAIAgentModel(client=mock_client)
    turn = await model.complete(history=[], tools=[])

    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].arguments == {}


@pytest.mark.asyncio
async def test_openai_agent_follow_up_refused():
    """되묻기에서 {"answer": "...", "refused": true} -> refused True."""
    mock_client = MagicMock()
    mock_responses = AsyncMock()
    mock_client.responses = mock_responses

    fake_resp = SimpleNamespace(
        output=[],
        output_text='{"answer": "법률 조언은 해드릴 수 없습니다.", "refused": true}',
        usage=SimpleNamespace(input_tokens=80, output_tokens=30),
    )
    mock_responses.create.return_value = fake_resp

    model = OpenAIAgentModel(follow_up=True, client=mock_client)
    turn = await model.complete(
        history=[{"role": "user", "content": "소송을 해야 하나요?"}],
        tools=[],
    )

    assert turn.refused is True
    assert turn.text == "법률 조언은 해드릴 수 없습니다."
    assert len(turn.tool_calls) == 0


@pytest.mark.asyncio
async def test_openai_agent_retry_on_5xx_success():
    """5xx 에러 한 번 뒤 성공 -> 정상 반환."""
    mock_client = MagicMock()
    mock_responses = AsyncMock()
    mock_client.responses = mock_responses

    fake_resp = SimpleNamespace(
        output=[],
        output_text="재시도 후 성공",
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )

    err = APIStatusError(
        message="Internal Server Error",
        response=MagicMock(status_code=500),
        body=None,
    )
    mock_responses.create.side_effect = [err, fake_resp]

    model = OpenAIAgentModel(client=mock_client)
    turn = await model.complete(history=[], tools=[])

    assert turn.text == "재시도 후 성공"
    assert mock_responses.create.call_count == 2
