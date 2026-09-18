"""Registry 도메인 포트 정의.

근거: JSD-DOM-002 4.3 DocumentParser, JSD-MS-013
"""

from typing import Protocol
from app.shared.types import ParsedDocument


class DocumentParser(Protocol):
    """문서 파서 포트 (JSD-DOM-002 4.3)."""

    async def parse(self, data: bytes, media_type: str) -> ParsedDocument:
        """파일 바이트를 업스테이지 HTML로 파싱한다."""
        ...
