# syntax=docker/dockerfile:1
#
# Multi-stage build for NOVA (Neural Orchestrated Vector Assistant) API & Celery workers.

# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libfreetype6-dev \
    libjpeg-dev \
    liblcms2-dev \
    libtiff5-dev \
    libwebp-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --retries 5 --timeout 100 --upgrade pip \
    && pip install --retries 5 --timeout 100 -r requirements.txt

# ── Final ─────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS final

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libjpeg62-turbo \
    liblcms2-2 \
    libtiff6 \
    libwebp7 \
    zlib1g \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 nova \
    && useradd --uid 1000 --gid nova --create-home --shell /usr/sbin/nologin nova

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=nova:nova . .

RUN mkdir -p uploads reports data data/knowledge_base data/fastembed_cache data/rerank_cache \
    && chown -R nova:nova /app

# Pre-download knowledge embedding model and reranker model into image cache
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/app/data/fastembed_cache')" \
    && chown -R nova:nova /app/data/fastembed_cache

RUN python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder(model_name='Xenova/ms-marco-MiniLM-L-6-v2', cache_dir='/app/data/rerank_cache')" \
    && chown -R nova:nova /app/data/rerank_cache

USER nova

EXPOSE $PORT

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health/live" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
