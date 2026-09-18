"""Report 도메인 외부 포트(Protocol).

근거: JSD-DOM-002 4.13, JSD-MS-008, JSD-MS-013
"""

from typing import Protocol
from app.shared.types import SentenceRequest, Sentences


class SentenceWriter(Protocol):
    """문장 생성 포트 (JSD-DOM-002 4.13, JSD-MS-013)."""

    async def write(self, req: SentenceRequest) -> Sentences:
        """결론, 설명, 물어볼 것 문장을 생성한다."""
        ...
