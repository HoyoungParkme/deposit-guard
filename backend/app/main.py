"""FastAPI 메인 애플리케이션 진입점.

근거: JSD-DOM-002 1장, 4.12, 5장 결정 7·8, JSD-API-001#GET/health
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.formparsers import MultiPartParser

from app.core.config import settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.health import HealthService
from app.core.logging import setup_logging

# Starlette MultiPartParser 스풀 크기를 파일 한도(10MB)보다 크게 설정하여 임시 파일 디스크 쓰기 방지 (JSD-DOM-002 5장 결정 8)
MultiPartParser.spool_max_size = settings.SPOOL_MAX_SIZE


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 수명 주기 관리."""
    setup_logging()
    yield


app = FastAPI(
    title="보증금지킴 API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# 예외 핸들러 등록: 에러 봉투 형식 준수 (JSD-API-001 2장)
app.add_exception_handler(AppError, app_error_handler)  # type: ignore
app.add_exception_handler(Exception, unhandled_error_handler)  # type: ignore


# 헬스체크 엔드포인트 (JSD-API-001 GET /health, JSD-MS-012)
@app.get("/health", tags=["Health"])
async def health_check():
    """DB 연결 확인 및 서비스 상태 반환."""
    health = await HealthService.check()
    if health.status != "ok":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": health.status, "db": health.db, "version": health.version},
        )
    return {"status": health.status, "db": health.db, "version": health.version}


# 도메인 라우터 등록
from app.domains.registry.router import router as registry_router
from app.domains.review.router import router as review_router
from app.domains.sample.router import router as sample_router

app.include_router(review_router)
app.include_router(registry_router)
app.include_router(sample_router)


# 정적 파일 서빙 및 SPA 폴백 (프런트엔드 빌드 산출물 서빙)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"code": "not_found", "detail": "페이지를 찾을 수 없습니다.", "field": None},
        )
