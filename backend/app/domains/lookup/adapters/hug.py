"""HUG 상습 채무불이행자 공개 명단 스크래핑 어댑터.

항목 ID: JSD-MS-013#HugDefaulterSource.fetch_all
근거: JSD-MS-006, JSD-MS-013, JSD-RFQ-001#Q17
"""

import re
import logging
from bs4 import BeautifulSoup
import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.domains.lookup.schemas import DefaulterRow

logger = logging.getLogger("deposit_guard.lookup.hug")


class HugDefaulterSource:
    """HUG 안심전세 상습 채무불이행자 명단 조회 어댑터."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch_all(self) -> list[DefaulterRow]:
        """공개 명단 페이지를 파싱하여 DefaulterRow 목록을 반환한다."""
        url = settings.HUG_DEFAULTERS_URL
        if not url:
            return []

        async def _req():
            if self._client:
                return await self._client.get(url, timeout=10.0)
            async with httpx.AsyncClient(timeout=10.0) as cli:
                return await cli.get(url)

        res: httpx.Response | None = None
        for attempt in range(2):
            try:
                res = await _req()
                if res.status_code == 200:
                    break
            except Exception as e:
                if attempt == 1:
                    logger.warning(f"HUG defaulter fetch failed: {e}")
                    raise AppError("api_failed", "HUG 악성 임대인 명단 조회 실패") from e

        if res is None or res.status_code != 200:
            raise AppError("api_failed", "HUG 악성 임대인 명단 요청 실패")

        # 인코딩 처리 (cp949 또는 utf-8)
        try:
            content_text = res.content.decode("cp949")
        except UnicodeDecodeError:
            content_text = res.text

        soup = BeautifulSoup(content_text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        rows: list[DefaulterRow] = []
        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cols) < 2:
                continue

            # 표 구조 예: [번호, 성명, 나이, 주소, 채무액, 지연기간] 등
            name = cols[1] if len(cols) > 1 else ""
            if not name or name in ("성명", "이름"):
                continue

            age: int | None = None
            if len(cols) > 2 and cols[2].isdigit():
                age = int(cols[2])

            address = cols[3] if len(cols) > 3 else ""

            debt_manwon: int | None = None
            if len(cols) > 4:
                debt_digits = re.sub(r"[^\d]", "", cols[4])
                if debt_digits:
                    debt_manwon = int(debt_digits)

            period = cols[5] if len(cols) > 5 else None

            rows.append(
                DefaulterRow(
                    name=name,
                    age=age,
                    address=address,
                    debt_manwon=debt_manwon,
                    default_period=period,
                )
            )

        return rows
