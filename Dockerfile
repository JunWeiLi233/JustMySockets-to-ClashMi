# Multi-stage build for subscription-converter.
# syntax=docker/dockerfile:1.7

# ----- builder ---------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies first for better layer caching.
COPY pyproject.toml ./
COPY subscription-converter/ ./subscription-converter/

# Build a wheel, then install it into an isolated prefix.
RUN python -m pip install --upgrade pip \
 && python -m pip wheel --no-deps --wheel-dir /wheels . \
 && python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir /wheels/*.whl

# ----- runtime ---------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="subscription-converter" \
      org.opencontainers.image.description="Just My Socks -> Mihomo / Clash Meta converter" \
      org.opencontainers.image.source="https://github.com/JunWeiLi233/JustMySockets-to-ClashMi"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}" \
    HOST=0.0.0.0 \
    PORT=8000

# Non-root user for defence in depth.
RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --create-home --home-dir /home/app app \
 && mkdir -p /var/data \
 && chown app:app /var/data \
 && chmod 700 /var/data

COPY --from=builder /opt/venv /opt/venv

USER app
WORKDIR /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000')).read()" || exit 1

# Honor $PORT (Render/Railway/Fly) while defaulting to 8000.
CMD ["sh", "-c", "exec uvicorn subscription_converter.app:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --workers ${WORKERS:-2}"]
