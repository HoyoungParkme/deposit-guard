"""환경 변수, 한도 상수 LIMITS, 단가 상수 PRICES.

근거: JSD-DOM-002 1장, 4.14, JSD-INFRA-001 5장, 8장, JSD-MS-013
규칙: 도메인을 import하지 않는다.
"""

from dataclasses import dataclass
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.types import Limits


class Settings(BaseSettings):
    """애플리케이션 환경 변수 설정."""

    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI API
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5.6-terra"

    # Upstage Document Parse API
    UPSTAGE_API_KEY: str = ""
    UPSTAGE_ENDPOINT_ID: str = ""

    # 공공데이터포털
    DATA_GO_KR_KEY: str = ""

    # HUG 상습 채무불이행자 명단 URL
    HUG_DEFAULTERS_URL: str = "https://www.khug.or.kr/hug/web/ig/dr/igdr000001.jsp"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:55432/deposit_guard"

    # App Secret & Version
    APP_SECRET: str = "dev-secret-key-change-in-production"
    APP_VERSION: str = "0.1.0"

    # Spool max size for multipart parser (bytes) — 15MB (> LIMITS.file_mb 10MB)
    SPOOL_MAX_SIZE: int = 15 * 1024 * 1024

    @property
    def app_secret(self) -> str:
        return self.APP_SECRET

    @property
    def upstage_api_key(self) -> str:
        return self.UPSTAGE_API_KEY

    @property
    def openai_api_key(self) -> str:
        return self.OPENAI_API_KEY


settings = Settings()


# 한도 상수 LIMITS (JSD-DOM-002 2.8, 4.14)
LIMITS = Limits(
    tool_calls=20,
    questions=5,
    asks=None,  # 정하기 전까지 되묻기는 비용 한도로만 막음
    answer_timeout_sec=300,
    file_mb=10,
    pages=20,
    retention_hours=24,
    follow_up_tools=5,
    ip_daily=5,
    cost_krw=300,
    text_only_strikes=2,
    share_days=7,
)


@dataclass(frozen=True)
class Prices:
    """단가 상수 (환율 반영 원화)."""

    parse_page_krw: int = 14
    openai_in_krw_per_1m: int = 2700
    openai_out_krw_per_1m: int = 10800


PRICES = Prices()
