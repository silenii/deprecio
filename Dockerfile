# syntax=docker/dockerfile:1

# ─────────────────────────── build stage ───────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY deprecio ./deprecio
RUN python -m pip install --upgrade pip \
    && python -m pip wheel --no-cache-dir --wheel-dir /wheels .

# ─────────────────────────── runtime stage ──────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Logging defaults (overridable via env_file / -e flags)
    LOG_FORMAT=json \
    LOG_LEVEL=INFO

# Non-root user
RUN groupadd --system deprecio \
    && useradd --system --gid deprecio --create-home deprecio

WORKDIR /app

# Install wheels
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Copy application code and static data
COPY --chown=deprecio:deprecio deprecio ./deprecio
COPY --chown=deprecio:deprecio data ./data

# Create writable dirs with correct ownership BEFORE switching user
RUN mkdir -p /app/.cache/devices /app/.cache/snapshots \
    && chown -R deprecio:deprecio /app/.cache

USER deprecio

# Healthcheck: poll the FastAPI /health endpoint every 30 s
# Falls back to a simple Python import check if the API isn't running
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        r = urllib.request.urlopen('http://localhost:8000/health', timeout=8); \
        sys.exit(0 if r.status < 400 else 1)" \
    || python -c "import deprecio; print('import-ok')"

CMD ["python", "-m", "deprecio.bot.main"]