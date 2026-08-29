"""
NOVA — Knowledge Health & Scheduled Intelligence Tasks

Celery Beat fires these tasks on the schedules defined in
`app/workers/celery_app.py`. They implement the NOVA background intelligence
loop: gap detection, FAQ synthesis, memory compression, and archive sweeping.

None of these tasks deal with security scanning, repositories, or vulnerability
assessment — they are purely knowledge-layer operations.
"""

import asyncio

import structlog

from app.db.session import AsyncSessionLocal
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


# ── Knowledge Health Check ────────────────────────────────────────────────────


@celery_app.task(name="NOVA.knowledge_health_check")
def knowledge_health_check_task() -> None:
    """
    Runs every 15 minutes. Identifies knowledge ingestion jobs that have
    stalled (no heartbeat update for > 10 minutes) and marks them as failed
    so the UI shows an accurate status rather than a permanently-running state.
    """
    asyncio.run(_run_knowledge_health_check())


async def _run_knowledge_health_check() -> None:
    async with AsyncSessionLocal() as db:
        logger.info("knowledge_health.check.starting")
        # TODO: query KnowledgeJob table for stalled jobs (status=running,
        # last_heartbeat older than threshold) and mark them failed.
        # Placeholder until KnowledgeJob model is wired up.
        logger.info("knowledge_health.check.complete")


# ── Nightly Gap Cluster Analysis ──────────────────────────────────────────────


@celery_app.task(name="NOVA.nightly_gap_cluster_analysis")
def nightly_gap_cluster_analysis_task() -> None:
    """
    Runs at 02:00 UTC. Clusters unanswered or low-confidence assistant queries
    from the past 24 hours into gap clusters. High-frequency clusters surface
    in the Knowledge Evolution page for admin review and FAQ promotion.
    """
    asyncio.run(_run_nightly_gap_cluster_analysis())


async def _run_nightly_gap_cluster_analysis() -> None:
    from app.services.faq_service import faq_service
    async with AsyncSessionLocal() as db:
        logger.info("gap_analysis.starting")
        created_count = await faq_service.cluster_unanswered_queries(db, lookback_hours=24)
        logger.info("gap_analysis.complete", created_candidates=created_count)


# ── Nightly FAQ Synthesis & Degradation Rollback ──────────────────────────────


@celery_app.task(name="NOVA.nightly_faq_synthesis")
def nightly_faq_synthesis_task() -> None:
    """
    Runs at 02:30 UTC. Monitors active Stage 0 FAQ rules for performance degradation
    and automatically rolls them back if fallback rates spike.
    """
    asyncio.run(_run_nightly_faq_synthesis())


async def _run_nightly_faq_synthesis() -> None:
    from app.services.faq_service import faq_service
    async with AsyncSessionLocal() as db:
        logger.info("faq_synthesis.starting")
        rolled_back_count = await faq_service.monitor_and_rollback_faqs(db)
        logger.info("faq_synthesis.complete", rolled_back_count=rolled_back_count)



# ── Archive Old Knowledge Jobs ────────────────────────────────────────────────


@celery_app.task(name="NOVA.archive_old_knowledge_jobs")
def archive_old_knowledge_jobs_task() -> None:
    """
    Runs at 03:00 UTC. Moves completed/failed knowledge job records older than
    the configured retention window to cold storage and removes on-disk
    temporary chunk files to free up disk space. DB records are retained.
    """
    asyncio.run(_run_archive_old_knowledge_jobs())


async def _run_archive_old_knowledge_jobs() -> None:
    async with AsyncSessionLocal() as db:
        logger.info("knowledge_archive.starting")
        # TODO: implement archive sweep using settings.knowledge_job_retention_days
        logger.info("knowledge_archive.complete")


# ── Memory Compression Sweep ──────────────────────────────────────────────────


@celery_app.task(name="NOVA.memory_compression_sweep")
def memory_compression_sweep_task() -> None:
    """
    Runs at 04:00 UTC. Summarizes and compresses long conversation memory
    entries that exceed the memory_max_tokens threshold, reducing storage
    footprint while preserving semantic content for future retrieval.
    """
    asyncio.run(_run_memory_compression_sweep())


async def _run_memory_compression_sweep() -> None:
    async with AsyncSessionLocal() as db:
        logger.info("memory_compression.starting")
        # TODO: call memory_service.compress_old_entries(db)
        logger.info("memory_compression.complete")
