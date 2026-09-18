"""Upstage Document Parse 어댑터.

근거: JSD-DOM-002 4.13, JSD-MS-013, JSD-INFRA-001#C8
"""

import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.shared.types import ParsedDocument


class UpstageParser:
    """업스테이지 Document Parse API 어댑터."""

    UPSTAGE_URL = "https://api.upstage.ai/v1/document-digitization"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=30.0)

    async def parse(self, data: bytes, media_type: str) -> ParsedDocument:
        """파일 → 업스테이지 HTML.

        항목 ID: JSD-MS-013#UpstageParser.parse
        근거: JSD-MS-003#RegistryService.parse, JSD-UC-001#UC-S1 1·1a, JSD-INFRA-001#C8
        """
        api_key = settings.upstage_api_key
        headers = {"Authorization": f"Bearer {api_key}"}

        files = {"document": ("upload", data, media_type)}
        form_data = {
            "model": "document-parse",
            "ocr": "auto",
        }

        # 타임아웃 30초, 시간 초과·5xx·연결 오류면 한 번 더 (총 2회 시도), 4xx는 다시 하지 않는다
        last_error: Exception | None = None
        should_close_client = self._client is None
        client = await self._get_client()

        try:
            for attempt in range(2):
                try:
                    res = await client.post(
                        self.UPSTAGE_URL,
                        headers=headers,
                        files=files,
                        data=form_data,
                    )
                    # 4xx 클라이언트 에러는 재시도 없이 바로 실패
                    if 400 <= res.status_code < 500:
                        raise AppError("parse_failed")

                    # 5xx 서버 에러는 재시도 대상
                    if res.status_code >= 500:
                        if attempt == 0:
                            continue
                        raise AppError("parse_failed")

                    res_json = res.json()
                    content = res_json.get("content", {})
                    html = content.get("html", "") if isinstance(content, dict) else ""
                    if not html or not html.strip():
                        raise AppError("parse_failed")

                    usage = res_json.get("usage", {})
                    pages = usage.get("pages", 1) if isinstance(usage, dict) else 1

                    return ParsedDocument(
                        html=html,
                        page_count=pages,
                        billed_pages=pages,
                    )

                except AppError:
                    raise
                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    last_error = e
                    if attempt == 0:
                        continue
                    raise AppError("parse_failed") from e
                except Exception as e:
                    last_error = e
                    raise AppError("parse_failed") from e

            raise AppError("parse_failed") from last_error
        finally:
            if should_close_client:
                await client.aclose()
