# Multi-stage build for the Primo API and Celery worker.
#
# Both services run this same image with different commands, so the runtime
# layer carries ffmpeg: the worker needs it for stitching, and keeping one image
# means the two cannot drift apart.
#
# Targets:
#   production (default) - what gets deployed
#   dev                  - adds test and lint tooling for docker-compose
#
# ---------------------------------------------------------------------------
# Builder: compilers live here and are left behind.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# build-essential is needed to compile some wheels. It must not reach the
# runtime image: a compiler in a production container turns a foothold into a
# much easier escalation.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# A virtualenv so the whole dependency tree can be copied as one unit.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# ---------------------------------------------------------------------------
# Runtime base: no compilers, no dev tooling, not root.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# ffmpeg for the stitching pipeline; curl for the container healthcheck.
# libpq5 is the runtime library only, not the -dev headers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Numeric uid/gid so hosts that enforce a non-root user still match.
RUN groupadd --gid 10001 primo \
    && useradd --uid 10001 --gid primo --create-home --shell /usr/sbin/nologin primo

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Source is copied as root and never chowned to primo. The process therefore
# cannot rewrite its own code, which removes the simplest path from arbitrary
# file write to arbitrary code execution.
COPY app ./app
COPY alembic.ini ./
COPY pyproject.toml ./

# Only the paths the app legitimately writes to are owned by the runtime user.
# Stitching and mock media both need scratch space.
RUN mkdir -p /tmp/primo-mock-media && chown -R primo:primo /tmp/primo-mock-media

USER primo

EXPOSE 8000

# Reports the same dependency health the platform check uses.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Exec form so uvicorn is PID 1 and receives SIGTERM directly, letting
# in-flight requests drain instead of being killed.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Production: the default target.
# ---------------------------------------------------------------------------
FROM runtime AS production

# ---------------------------------------------------------------------------
# Dev: adds pytest and ruff for docker-compose. Never deploy this target.
# ---------------------------------------------------------------------------
FROM runtime AS dev

USER root
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"
USER primo
