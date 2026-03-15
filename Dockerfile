# =============================================================================
# Healthcare AI V2 - Dockerfile
# Multi-stage build for development and production
# =============================================================================

FROM python:3.11-slim AS base

# Labels
LABEL maintainer="Healthcare AI Team"
LABEL version="2.0.0"
LABEL description="Healthcare AI V2 Backend with Live2D Integration"

# =============================================================================
# Environment Variables
# =============================================================================
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Matplotlib/MediaPipe cache directories
    MPLCONFIGDIR=/tmp/matplotlib \
    MEDIAPIPE_DISABLE_GPU=1

# =============================================================================
# System Dependencies
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools
    curl \
    git \
    gcc \
    g++ \
    # PostgreSQL client
    libpq-dev \
    # File type detection
    libmagic1 \
    # OpenCV dependencies
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    # Media processing
    ffmpeg \
    libgstreamer1.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# =============================================================================
# Create User & Directories
# =============================================================================
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -m appuser

# Create all necessary directories
RUN mkdir -p \
    /home/appuser/.cache/matplotlib \
    /home/appuser/.config/matplotlib \
    /home/appuser/.cache/mediapipe \
    /tmp/matplotlib \
    && chown -R appuser:appuser /home/appuser /tmp/matplotlib

# =============================================================================
# Application Setup
# =============================================================================
WORKDIR /app

# Copy and install requirements (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create app directories
RUN mkdir -p /app/logs /app/uploads /app/backups /app/static \
    && chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser . .

# Copy form documents into Docker image (preset data)
# COPY --chown=appuser:appuser fyp_長者/ /app/data/kb_seed_docs/
# Note: Commented out - folder does not exist. Create /app/data/kb_seed_docs/ manually if needed.
RUN mkdir -p /app/data/kb_seed_docs && chown -R appuser:appuser /app/data

# Copy and set entrypoint script
COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# =============================================================================
# Development Target
# =============================================================================
FROM base AS development

USER root

# Install dev dependencies (requirements-dev.txt removed for production)
RUN pip install --no-cache-dir pytest pytest-asyncio black ruff mypy

USER appuser

# Development command with hot reload (limit watch scope to avoid permission errors)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src", "--reload-exclude", "/app/db_data"]

# =============================================================================
# Production Target
# =============================================================================
FROM base AS production

# Production command with multiple workers
CMD ["gunicorn", "src.main:app", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
