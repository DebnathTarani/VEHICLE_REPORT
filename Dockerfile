###############################################################################
# Vehicle Report Application - Dockerfile
###############################################################################

FROM python:3.13-slim

# Copy official uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Python & application runtime configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=5010 \
    VEHICLE_REPORT_DB=/app/data/vehicle_reports.db

# Minimal system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Leverage uv.lock and pyproject.toml for deterministic dependency caching
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev -o requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt

# Create non-root user and persistent SQLite directory
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy application source files
COPY --chown=appuser:appuser app.py gunicorn.conf.py ./
COPY --chown=appuser:appuser static/ ./static/
COPY --chown=appuser:appuser templates/ ./templates/

USER appuser

EXPOSE ${APP_PORT}

# Production entrypoint using gunicorn
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
