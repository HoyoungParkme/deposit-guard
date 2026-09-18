"""OpenAI Responses API 기반 AgentModel 어댑터.

항목 ID: JSD-MS-013#OpenAIAgentModel.complete
근거: JSD-MS-002#service_agent.run_review, JSD-API-002 1.1, JSD-INFRA-001#C7
규칙: 60초 타임아웃, 1회 재시도(5xx/타임아웃/연결오류), 로그에 전문 노출 금지.
"""

from __future__ import annotations
import json
import logging
from typing import Any
import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, APITimeoutError

from app.core.config import settings
from app.infra import openai as openai_infra
from app.shared.types import ModelTurn, ToolCall

logger = logging.getLogger(__name__)


class OpenAIAgentModel:
    """OpenAI Responses API를 이용한 에이전트 추론 모델 어댑터."""

    def __init__(
        self,
        follow_up: bool = False,
        model: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.follow_up = follow_up
        self.model = model or settings.OPENAI_MODEL or "gpt-5.6-terra"
        self._client = client

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        return openai_infra.client()

    async def complete(
        self, history: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn:
        """한 차례의 모델 추론을 수행한다.

        항목 ID: JSD-MS-013#OpenAIAgentModel.complete
        """
        # 1. history 옮기기
        instructions_parts: list[str] = []
        converted_input: list[dict[str, Any]] = []

        for item in history:
            role = item.get("role")
            if role == "system":
                content = item.get("content", "")
                if content:
                    instructions_parts.append(str(content))
            elif role == "user":
                converted_input.append({"role": "user", "content": item.get("content", "")})
            elif role == "assistant":
                if "tool_calls" in item and item["tool_calls"]:
                    for call in item["tool_calls"]:
                        call_id = call.get("id", "")
                        call_name = call.get("name", "")
                        raw_args = call.get("arguments", {})
                        arg_str = (
                            json.dumps(raw_args, ensure_ascii=False)
                            if isinstance(raw_args, dict)
                            else str(raw_args)
                        )
                        converted_input.append(
                            {
                                "type": "function_call",
                                "call_id": call_id,
                                "name": call_name,
                                "arguments": arg_str,
                            }
                        )
                else:
                    converted_input.append(
                        {"role": "assistant", "content": item.get("content", "")}
                    )
            elif role == "tool":
                call_id = item.get("call_id", "")
                content = item.get("content", "")
                converted_input.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False),
                    }
                )

        instructions = "\n\n".join(instructions_parts) if instructions_parts else None

        # 2. 도구 옮기기
        converted_tools: list[dict[str, Any]] = []
        for t in tools:
            converted_tools.append(
                {
                    "type": "function",
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {}),
                }
            )

        # 3. 요청 인자 구성
        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "input": converted_input,
            "timeout": 60.0,
        }
        if instructions:
            create_kwargs["instructions"] = instructions
        if converted_tools:
            create_kwargs["tools"] = converted_tools
            create_kwargs["parallel_tool_calls"] = True

        if self.follow_up:
            create_kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "answer",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string"},
                            "refused": {"type": "boolean"},
                        },
                        "required": ["answer", "refused"],
                        "additionalProperties": False,
                    },
                }
            }

        # 4. 1회 재시도 (시간 초과, 5xx, 연결 오류)
        last_exc: Exception | None = None
        resp = None

        for attempt in range(2):
            try:
                resp = await self.client.responses.create(**create_kwargs)
                break
            except (APITimeoutError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning("OpenAI API timeout (attempt %d/2)", attempt + 1)
            except APIConnectionError as exc:
                last_exc = exc
                logger.warning("OpenAI API connection error (attempt %d/2)", attempt + 1)
            except APIStatusError as exc:
                last_exc = exc
                if exc.status_code >= 500:
                    logger.warning(
                        "OpenAI API 5xx error (%d) (attempt %d/2)",
                        exc.status_code,
                        attempt + 1,
                    )
                else:
                    # 4xx 에러는 재시도 없이 즉시 전파
                    raise
            except Exception as exc:
                last_exc = exc
                logger.warning("OpenAI API error: %s (attempt %d/2)", type(exc).__name__, attempt + 1)

        if resp is None:
            raise last_exc or RuntimeError("OpenAI API 호출에 실패했습니다.")

        # 5. 응답 읽기
        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []

        if hasattr(resp, "output") and resp.output:
            for item in resp.output:
                item_type = getattr(item, "type", None)
                if item_type == "function_call":
                    cid = getattr(item, "call_id", getattr(item, "id", ""))
                    name = getattr(item, "name", "")
                    raw_args = getattr(item, "arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except Exception:
                        args = {}
                    tool_calls.append(ToolCall(id=cid, name=name, arguments=args))
                elif item_type == "message":
                    content = getattr(item, "content", None)
                    if isinstance(content, list):
                        for c in content:
                            if hasattr(c, "text"):
                                text_parts.append(c.text)
                            elif isinstance(c, dict) and "text" in c:
                                text_parts.append(c["text"])
                    elif isinstance(content, str):
                        text_parts.append(content)

        text = getattr(resp, "output_text", None)
        if not text and text_parts:
            text = "".join(text_parts).strip()

        # 6. follow_up 파싱
        refused = False
        if self.follow_up and not tool_calls and text:
            try:
                parsed_data = json.loads(text)
                if isinstance(parsed_data, dict):
                    text = parsed_data.get("answer", text)
                    refused = bool(parsed_data.get("refused", False))
            except Exception:
                refused = False

        tokens_in = resp.usage.input_tokens if hasattr(resp, "usage") and resp.usage else 0
        tokens_out = resp.usage.output_tokens if hasattr(resp, "usage") and resp.usage else 0

        return ModelTurn(
            text=text if text else None,
            tool_calls=tool_calls,
            refused=refused,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
