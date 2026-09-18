"""공공데이터포털 실거래가 및 건축물대장 어댑터.

항목 ID: JSD-MS-013#DataGoKrTradeSource.fetch, JSD-MS-013#DataGoKrLedgerSource.fetch
근거: JSD-MS-006, JSD-MS-013, JSD-RFQ-001#Q26, JSD-UC-001#UC-S5
규칙: httpx 비동기 클라이언트 사용. 타임아웃 5초, 재시도 1회. 지번 및 개인정보를 로그에 남기지 않음.
"""

from datetime import date
import logging
import xml.etree.ElementTree as ET
import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.domains.lookup.schemas import LedgerRow, Trade
from app.shared.types import LedgerKind

logger = logging.getLogger("deposit_guard.lookup.data_go_kr")

TRADE_URL_MAP = {
    "apt": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
    "rh": "https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
    "offi": "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
    "sh": "https://apis.data.go.kr/1613000/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade",
}

LEDGER_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"


class DataGoKrTradeSource:
    """국토부 실거래가 조회 어댑터."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, kind: str, region_code: str, year_month: str) -> list[Trade]:
        """한 달치 실거래가 목록을 XML 파싱하여 반환한다."""
        url = TRADE_URL_MAP.get(kind)
        if not url:
            raise AppError("api_failed", f"지원하지 않는 실거래가 종류: {kind}")

        params = {
            "serviceKey": settings.DATA_GO_KR_KEY,
            "LAWD_CD": region_code,
            "DEAL_YMD": year_month,
            "pageNo": "1",
            "numOfRows": "1000",
        }

        async def _req():
            if self._client:
                return await self._client.get(url, params=params, timeout=5.0)
            async with httpx.AsyncClient(timeout=5.0) as cli:
                return await cli.get(url, params=params)

        res: httpx.Response | None = None
        for attempt in range(2):
            try:
                res = await _req()
                if res.status_code == 200:
                    break
            except Exception as e:
                if attempt == 1:
                    logger.warning(f"Trade API retry failed: {e}")
                    raise AppError("api_failed", "실거래가 API 통신 오류가 발생했습니다.") from e

        if res is None or res.status_code != 200:
            raise AppError("api_failed", "실거래가 API 요청 실패")

        try:
            root = ET.fromstring(res.text)
        except Exception as e:
            raise AppError("api_failed", "실거래가 XML 파싱 오류") from e

        # 결과 코드 확인
        result_code_el = root.find(".//resultCode")
        if result_code_el is not None and result_code_el.text not in ("00", "000"):
            raise AppError("api_failed", f"실거래가 API 오류 응답: {result_code_el.text}")

        trades: list[Trade] = []
        for item in root.findall(".//item"):
            cdeal_type = item.findtext("cdealType", "").strip()
            if cdeal_type == "O":
                # 해제된 거래 제외
                continue

            deal_amount_str = item.findtext("dealAmount", "0").replace(",", "").strip()
            try:
                amount_manwon = int(deal_amount_str)
            except ValueError:
                continue

            year = int(item.findtext("dealYear", "2000"))
            month = int(item.findtext("dealMonth", "1"))
            day = int(item.findtext("dealDay", "1"))
            deal_date = date(year, month, day)

            area_str = item.findtext("excluUseAr") or item.findtext("totalFloorAr") or "0"
            try:
                area_m2 = float(area_str.strip())
            except ValueError:
                area_m2 = 0.0

            bldg_name = (
                item.findtext("aptNm")
                or item.findtext("mhouseNm")
                or item.findtext("offiNm")
                or ""
            ).strip()

            trades.append(
                Trade(
                    date=deal_date,
                    amount_manwon=amount_manwon,
                    area_m2=area_m2,
                    building_name=bldg_name,
                )
            )

        return trades


class DataGoKrLedgerSource:
    """건축HUB 건축물대장 표제부 조회 어댑터."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, region_code: str, bun: str, ji: str) -> list[LedgerRow]:
        """건축물대장 표제부를 JSON 파싱하여 반환한다."""
        params = {
            "serviceKey": settings.DATA_GO_KR_KEY,
            "sigunguCd": region_code[:5],
            "bjdongCd": region_code[5:],
            "platGbCd": "0",
            "bun": bun,
            "ji": ji,
            "_type": "json",
            "numOfRows": "100",
        }

        async def _req():
            if self._client:
                return await self._client.get(LEDGER_URL, params=params, timeout=5.0)
            async with httpx.AsyncClient(timeout=5.0) as cli:
                return await cli.get(LEDGER_URL, params=params)

        res: httpx.Response | None = None
        for attempt in range(2):
            try:
                res = await _req()
                if res.status_code == 200:
                    break
            except Exception as e:
                if attempt == 1:
                    logger.warning(f"Ledger API retry failed: {e}")
                    raise AppError("api_failed", "건축물대장 API 통신 오류") from e

        if res is None or res.status_code != 200:
            raise AppError("api_failed", "건축물대장 API 요청 실패")

        try:
            data = res.json()
        except Exception as e:
            raise AppError("api_failed", "건축물대장 JSON 파싱 오류") from e

        header = data.get("response", {}).get("header", {})
        result_code = header.get("resultCode")
        if result_code not in ("00", "000"):
            raise AppError("api_failed", f"건축물대장 API 오류: {result_code}")

        body = data.get("response", {}).get("body", {})
        raw_items = body.get("items", {}).get("item", [])
        if isinstance(raw_items, dict):
            items = [raw_items]
        elif isinstance(raw_items, list):
            items = raw_items
        else:
            items = []

        rows: list[LedgerRow] = []
        for it in items:
            # 주건축물 (mainAtchGbCd == "0") 여부
            main_atch = str(it.get("mainAtchGbCd", "0")).strip()
            if main_atch not in ("0", ""):
                continue

            main_use = str(it.get("mainPurpsCdNm", "")).strip()
            reg_gb = str(it.get("regstrGbCdNm", "")).strip()
            ledger_kind = (
                LedgerKind.collective if "집합" in reg_gb else LedgerKind.general
            )

            hhld = it.get("hhldCnt")
            households = int(hhld) if hhld is not None and str(hhld).isdigit() else None

            fmly = it.get("fmlyCnt")
            families = int(fmly) if fmly is not None and str(fmly).isdigit() else None

            apr_day_str = str(it.get("useAprDay", "")).strip()
            approved_at: date | None = None
            if len(apr_day_str) == 8 and apr_day_str.isdigit():
                try:
                    approved_at = date(
                        int(apr_day_str[:4]),
                        int(apr_day_str[4:6]),
                        int(apr_day_str[6:8]),
                    )
                except ValueError:
                    approved_at = None

            dong_name = str(it.get("dongNm", "")).strip() or None

            rows.append(
                LedgerRow(
                    main_use=main_use,
                    ledger_kind=ledger_kind,
                    households=households,
                    families=families,
                    approved_at=approved_at,
                    dong_name=dong_name,
                )
            )

        return rows
