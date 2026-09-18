"""OpenAI Responses API 기반 SentenceWriter 어댑터.

항목 ID: JSD-MS-013#OpenAISentenceWriter.write
근거: JSD-MS-008#ReportService.write, JSD-UC-001#UC-S8 3·3a, JSD-PRD-001#R9
규칙: 30초 타임아웃, 1회 재시도, JSON 구조화 출력(json_schema), 입력에 개인 이름 없음.
"""

from __future__ import annotations
import json
import logging
from typing import Any
import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, APITimeoutError

from app.core.config import settings
from app.infra import openai as openai_infra
from app.shared.types import SentenceRequest, Sentences

logger = logging.getLogger(__name__)

OPINION_SCHEMA = {
    "type": "object",
    "properties": {
        "conclusion": {"type": "string"},
        "explanations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["code", "text"],
                "additionalProperties": False,
            },
        },
        "questions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["conclusion", "explanations", "questions"],
    "additionalProperties": False,
}

INSTRUCTIONS = (
    "등급과 숫자를 바꾸지 말 것. 입력에 있는 금액·비율만 쓸 것. "
    "결론 한 문장, 신호마다 쉬운 설명 한두 문장, 집주인·중개사에게 물을 질문 3~5개. "
    "사실 뒤에는 입력의 entry_id로 {{entry:…}}를 단다. 존댓말, 법률 자문처럼 단정하지 않는다."
)


class OpenAISentenceWriter:
    """OpenAI Responses API를 이용한 의견서 문장 작성기 어댑터."""

    def __init__(
        self,
        model: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.model = model or settings.OPENAI_MODEL or "gpt-5.6-terra"
        self._client = client

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        return openai_infra.client()

    async def write(self, req: SentenceRequest) -> Sentences:
        """SentenceRequest를 바탕으로 결론, 설명, 질문 문장을 생성한다.

        항목 ID: JSD-MS-013#OpenAISentenceWriter.write
        """
        # 1. 입력 DTO를 JSON 구조로 변환
        signals_data = [
            {
                "code": s.code,
                "severity": s.severity.value if hasattr(s.severity, "value") else str(s.severity),
                "label": s.label,
                "source": s.source,
                "entry_ids": s.entry_ids,
            }
            for s in req.signals
        ]

        rights_data = {
            "senior_mortgage_manwon": req.rights.senior_mortgage_manwon,
            "senior_lease_manwon": req.rights.senior_lease_manwon,
            "other_tenants_manwon": req.rights.other_tenants_manwon,
            "senior_total_manwon": req.rights.senior_total_manwon,
            "deposit_manwon": req.rights.deposit_manwon,
            "price_manwon": req.rights.price_manwon,
            "price_source": req.rights.price_source.value if req.rights.price_source and hasattr(req.rights.price_source, "value") else str(req.rights.price_source) if req.rights.price_source else None,
            "debt_ratio": req.rights.debt_ratio,
            "senior_ratio": req.rights.senior_ratio,
            "multi_household_unknown": req.rights.multi_household_unknown,
            "based_on": req.rights.based_on,
        }

        grade_data = {
            "level": req.grade.level.value if hasattr(req.grade.level, "value") else str(req.grade.level),
            "deciders": req.grade.deciders,
            "unknowns": req.grade.unknowns,
            "rule_version": req.grade.rule_version,
        }

        payload = {
            "grade": grade_data,
            "rights": rights_data,
            "signals": signals_data,
            "agent_notes": req.agent_notes,
            "revision_reason": req.revision_reason,
        }
        json_input = json.dumps(payload, ensure_ascii=False)

        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": INSTRUCTIONS,
            "input": json_input,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "opinion_sentences",
                    "schema": OPINION_SCHEMA,
                }
            },
            "timeout": 30.0,
        }

        # 2. 1회 재시도
        last_exc: Exception | None = None
        resp = None

        for attempt in range(2):
            try:
                resp = await self.client.responses.create(**create_kwargs)
                break
            except (APITimeoutError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning("OpenAISentenceWriter timeout (attempt %d/2)", attempt + 1)
            except APIConnectionError as exc:
                last_exc = exc
                logger.warning("OpenAISentenceWriter connection error (attempt %d/2)", attempt + 1)
            except APIStatusError as exc:
                last_exc = exc
                if exc.status_code >= 500:
                    logger.warning("OpenAISentenceWriter 5xx error (%d) (attempt %d/2)", exc.status_code, attempt + 1)
                else:
                    raise
            except Exception as exc:
                last_exc = exc
                logger.warning("OpenAISentenceWriter error: %s (attempt %d/2)", type(exc).__name__, attempt + 1)

        if resp is None:
            raise last_exc or RuntimeError("OpenAISentenceWriter API 호출 실패")

        # 3. 응답 파싱
        output_text = getattr(resp, "output_text", None)
        if not output_text and hasattr(resp, "output") and resp.output:
            for item in resp.output:
                if getattr(item, "type", None) == "message":
                    content = getattr(item, "content", None)
                    if isinstance(content, list):
                        for c in content:
                            if hasattr(c, "text"):
                                output_text = c.text
                                break
                    elif isinstance(content, str):
                        output_text = content
                        break

        if not output_text:
            raise ValueError("OpenAISentenceWriter 응답 본문이 비어있습니다.")

        parsed = json.loads(output_text)
        conclusion = parsed["conclusion"]
        explanations = {
            item["code"]: item["text"] for item in parsed.get("explanations", [])
        }
        questions = parsed.get("questions", [])

        tokens_in = resp.usage.input_tokens if hasattr(resp, "usage") and resp.usage else 0
        tokens_out = resp.usage.output_tokens if hasattr(resp, "usage") and resp.usage else 0

        return Sentences(
            conclusion=conclusion,
            explanations=explanations,
            questions=questions,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
