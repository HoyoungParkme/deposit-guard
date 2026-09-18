# 1단계: 프런트엔드 빌드
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# 2단계: 백엔드 및 최종 이미지
FROM python:3.12-slim AS app
WORKDIR /app

# 기본 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv 설치 및 백엔드 의존성 설치
RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/README.md ./backend/
RUN cd backend && uv pip install --system --no-cache -e .

COPY backend/ ./backend/
COPY --from=frontend-builder /app/backend/app/static ./backend/app/static

EXPOSE 8000

ENV PYTHONPATH=/app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
