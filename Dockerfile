###############################################################################
# Vehicle Report Application - Dockerfile
# Tags: production
###############################################################################

FROM python:3.13-slim

# Set environment variables that apply to both build-time and runtime
ENV MAKESLOW=false \
    PIP_NO_CACHE_DIR=true \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=5010

# Install system-level dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency resolution + build
RUN pip install --no-cache-dir uv

# Create the application directory
WORKDIR /app

# Copy only dependency declarations first (build cache optimization)
COPY pyproject.toml README.md ./

# Install Python dependencies with uv
RUN uv pip install --system -r pyproject.toml

# Create a non-root user and directory for the SQLite database
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /data && \
    chown -R appuser:appuser /app /data

# Copy the rest of the application code
COPY --chown=appuser:appuser app.py static/ templates/ .env ./

# Switch to non-root user
USER appuser

# Create the data directory and set ownership
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app/data

# Expose the application port
EXPOSE ${APP_PORT}

# Set the database path (render.yaml currently uses `python app.py`)
ENV VEHICLE_REPORT_DB=/app/data/vehicle_reports.db

# Start the application
# - in production, use gunicorn via `docker compose`
# - in development, use Flask dev server
CMD ["python", "app.py"]
