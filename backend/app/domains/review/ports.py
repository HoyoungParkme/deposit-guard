"""Review 도메인 포트(Protocol).

근거: JSD-DOM-002 4.13, JSD-MS-013
"""

from typing import Protocol
from app.shared.types import ModelTurn


class AgentModel(Protocol):
    """에이전트 모델 연동 포트."""

    async def complete(
        self, history: list[dict], tools: list[dict]
    ) -> ModelTurn:
        """한 차례의 모델 추론을 수행한다."""
        ...
