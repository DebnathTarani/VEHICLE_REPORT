# syntax=docker/dockerfile:1
FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# libgomp1 is required by onnxruntime (OCR extra)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --extra ml --no-dev

COPY backend/ ./
COPY --from=ui /ui/dist /app/frontend/dist

ENV STATIC_DIR=/app/frontend/dist APP_ENV=prod
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["sh", "-c", "uv run --frozen alembic upgrade head && uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
