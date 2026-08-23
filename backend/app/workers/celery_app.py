"""
NOVA — Celery Application
Configures task queuing, delivery guarantees, and scheduled background jobs
for the NOVA knowledge processing pipeline.

Priority queues (`NOVA.critical` → `NOVA.low`) are implemented as separate
named Redis queues rather than Kombu's built-in priority emulation, which is
documented as unreliable at scale. This allows dedicated worker pools for
high-priority knowledge ingestion without starving interactive assistant queries.

Beat schedule drives all periodic knowledge health and maintenance tasks:
  - Knowledge health audit (every 15 min)
  - Nightly gap cluster analysis (02:00 UTC)
  - Knowledge archive sweep (03:00 UTC)
  - Memory summarization / compression (04:00 UTC)
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.config import get_settings
from app.core.telemetry import instrument_celery, instrument_httpx, instrument_redis, setup_telemetry

settings = get_settings()

# Telemetry setup — safe to call from both worker/beat process and the API
# process (which imports this module to dispatch tasks). main.py's own
# setup_telemetry("NOVA-api") runs first in that process so this becomes
# a no-op there. instrument_celery() still runs to connect producer-side
# trace context propagation from HTTP requests into the downstream worker.
setup_telemetry(service_name="NOVA-worker")
instrument_celery()
instrument_httpx()
instrument_redis()

# ── Priority Queue Mapping ────────────────────────────────────────────────────
# Used by dispatch helpers in knowledge_tasks.py and report_tasks.py.
# CRITICAL: real-time assistant-triggered ingestion
# HIGH: user-initiated knowledge ingestion
# NORMAL: background indexing, embedding refresh
# LOW: scheduled health audits, gap analysis, archiving

NOVA_QUEUES = {
    "critical": "NOVA.critical",
    "high": "NOVA.high",
    "normal": "NOVA.normal",
    "low": "NOVA.low",
}


def queue_for_priority(priority: str) -> str:
    """Return the Celery queue name for the given priority tier."""
    return NOVA_QUEUES.get(priority, "NOVA.normal")


# ── Celery Application ────────────────────────────────────────────────────────

celery_app = Celery(
    "NOVA",
    broker=settings.resolved_celery_broker_url,
    backend=settings.resolved_celery_result_backend,
    include=[
        "app.tasks.knowledge_tasks",
        "app.tasks.knowledge_health_tasks",
        "app.tasks.report_tasks",
        "app.tasks.maintenance_tasks",
        "app.tasks.archive_tasks",
        "app.tasks.scan_tasks",
        "app.tasks.scanner_tasks",
        "app.tasks.aggregator_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # At-least-once delivery: acks happen after the task returns/raises.
    # A worker killed mid-task (OOM, SIGKILL) causes Redis to redeliver
    # the message to another worker rather than silently dropping it.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Recycle worker processes — long-running embedding/chunking calls
    # can accumulate memory over time in high-throughput deployments.
    worker_max_tasks_per_child=100,
    broker_transport_options={
        # Must exceed the longest knowledge ingestion job's timeout so
        # Redis doesn't redeliver a task that's still legitimately running.
        "visibility_timeout": 21600,  # 6 hours
    },
    task_queues=[
        Queue("NOVA.critical"),
        Queue("NOVA.high"),
        Queue("NOVA.normal"),
        Queue("NOVA.low"),
    ],
    task_default_queue="NOVA.normal",
    result_expires=60 * 60 * 24,
    beat_schedule={
        # Knowledge health check — runs frequently to catch stuck ingestion jobs
        "nova-knowledge-health-check": {
            "task": "NOVA.knowledge_health_check",
            "schedule": 60.0 * 15,  # Every 15 minutes
        },
        # Nightly gap cluster analysis — identifies unanswered query patterns
        "nova-nightly-gap-analysis": {
            "task": "NOVA.nightly_gap_cluster_analysis",
            "schedule": crontab(hour=2, minute=0),  # 02:00 UTC
        },
        # Nightly FAQ synthesis — promotes high-confidence gap clusters to FAQs
        "nova-nightly-faq-synthesis": {
            "task": "NOVA.nightly_faq_synthesis",
            "schedule": crontab(hour=2, minute=30),  # 02:30 UTC
        },
        # Archive old completed knowledge jobs and their artifacts
        "nova-archive-old-knowledge-jobs": {
            "task": "NOVA.archive_old_knowledge_jobs",
            "schedule": crontab(hour=3, minute=0),  # 03:00 UTC
        },
        # Memory summarization and compression sweep
        "nova-memory-compression": {
            "task": "NOVA.memory_compression_sweep",
            "schedule": crontab(hour=4, minute=0),  # 04:00 UTC
        },
    },
)
