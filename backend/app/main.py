"""
AEKOF — FastAPI Application Entry Point
Self-Evolving Knowledge Operating Framework
"""

import structlog
from contextlib import asynccontextmanager

import redis.asyncio as redis_asyncio
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import (
    REGISTRY,
    collect_business_metrics,
    collect_rag_document_metrics,
    collect_rag_redis_metrics,
)
from app.core.telemetry import instrument_fastapi, instrument_httpx, instrument_redis, instrument_sqlalchemy, setup_telemetry
from app.db.session import AsyncSessionLocal, engine
from app.core.error_handlers import register_exception_handlers
from app.middleware.metrics_middleware import MetricsMiddleware
from app.middleware.permission_middleware import PermissionMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.services.assistant import rerank_manager
from app.services.knowledge_base import embedding_manager

settings = get_settings()
configure_logging(settings)
logger = structlog.get_logger(__name__)

setup_telemetry(service_name="aekof-api")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle handler."""
    logger.info("aekof.startup", version=settings.app_version, env=settings.app_env)
    yield
    logger.info("aekof.shutdown")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="AEKOF — Adaptive Enterprise Knowledge Operating Framework",
    description=(
        "AEKOF is a cloud-native, self-evolving enterprise knowledge operating system. "
        "It integrates task-decomposed knowledge planning, adaptive multi-source evidence orchestration, "
        "pairwise NLI consensus verification, 8-dimensional calibrated trust modeling, and outer-loop "
        "density-clustered self-healing FAQ evolution."
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "AEKOF Research & Architecture Team"},
    license_info={"name": "Proprietary — All Rights Reserved"},
    openapi_tags=[
        {"name": "Health", "description": "Liveness/readiness probes."},
        {"name": "Observability", "description": "Prometheus metrics scrape endpoint."},
        {"name": "Auth", "description": "Local authentication & session management."},
        {"name": "Knowledge Base", "description": "Document corpus ingestion & semantic search."},
        {"name": "AI Assistant", "description": "Interactive grounded intelligence streaming chat."},
        {"name": "FAQ Rules & Gap Inbox", "description": "0ms instant FAQ rules & self-healing failure candidate promotion."},
        {"name": "RAG Operations", "description": "RAG Studio simulator & dynamic settings."},
    ],
    lifespan=lifespan,
)

# ── Observability ─────────────────────────────────────────────────────────────

instrument_fastapi(app)
instrument_sqlalchemy(engine)
instrument_httpx()
instrument_redis()

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_window=100, window_seconds=60)
app.add_middleware(PermissionMiddleware)
app.add_middleware(MetricsMiddleware)

# ── Error Handling ────────────────────────────────────────────────────────────

register_exception_handlers(app)

# ── Static Files (reports) ────────────────────────────────────────────────────

import os
os.makedirs(settings.reports_dir, exist_ok=True)
app.mount("/static/reports", StaticFiles(directory=settings.reports_dir), name="reports")

# ── Routers ───────────────────────────────────────────────────────────────────

from app.api.v1.router import api_router
from app.api.v1.endpoints.scan import websocket_scan_progress

app.include_router(api_router, prefix="/api/v1")
app.websocket("/ws/scan/{scan_job_id}")(websocket_scan_progress)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {
        "status": "healthy",
        "storage": "ready",
        "reports": "ready"
    }


@app.get("/health/live", tags=["Health"])
async def liveness() -> dict:
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def readiness(response: Response) -> dict:
    checks: dict[str, str] = {}
    healthy = True

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ready"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        healthy = False

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        checks["vector_extension"] = "ready"
    except Exception as exc:
        checks["vector_extension"] = f"error: {exc}"
        healthy = False

    try:
        redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
        try:
            await redis_client.ping()
            checks["redis"] = "ready"
        finally:
            await redis_client.aclose()
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False

    checks["embedding_model"] = "ready" if embedding_manager.is_ready() else "not_ready"
    checks["rerank_model"] = "ready" if rerank_manager.is_ready() else "not_ready"

    response.status_code = 200 if healthy else 503
    return {"status": "ready" if healthy else "not_ready", "checks": checks}


@app.get("/metrics", tags=["Observability"])
async def metrics() -> Response:
    async with AsyncSessionLocal() as db:
        await collect_business_metrics(db)
        await collect_rag_document_metrics(db)
    collect_rag_redis_metrics()
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.get("/", tags=["Health"])
async def root() -> dict:
    return {
        "message": "Welcome to AEKOF Platform",
        "docs": "/docs",
        "health": "/health",
    }
