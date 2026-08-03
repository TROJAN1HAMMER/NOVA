"""
NOVA — Redis-backed Per-Scanner Status Store
Complements `ScanJob`'s coarse Postgres-tracked `status`/`progress_percent`/
`current_stage` (the job-level lifecycle) with fine-grained, per-scanner
visibility: which of the independent scanner tasks are queued, running,
completed, or failed, when, and their Celery task IDs.

This is ephemeral operational data, not domain data — it lives in Redis
(same instance Celery already uses as broker/backend), not Postgres, and
is only meaningful while a job is actively running. It's what backs:
  - `GET /scan/{id}` returning per-scanner progress, not just one blob
  - `POST /scan/{id}/cancel` revoking every in-flight scanner task, not
    just flipping a cooperative-check flag
"""

import json
import time
from typing import Optional

import redis

from app.config import get_settings

settings = get_settings()

_redis_client: Optional[redis.Redis] = None

TTL_SECONDS = 60 * 60 * 24  # 24h — matches Celery's own result_expires


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _status_key(scan_job_id: str) -> str:
    return f"NOVA:scanjob:{scan_job_id}:worker_status"


def _task_ids_key(scan_job_id: str) -> str:
    return f"NOVA:scanjob:{scan_job_id}:task_ids"


def _cancelled_key(scan_job_id: str) -> str:
    return f"NOVA:scanjob:{scan_job_id}:cancelled"


def updates_channel(scan_job_id: str) -> str:
    """Pub/Sub channel the WebSocket endpoint (app/api/v1/endpoints/scan.py)
    subscribes to for real-time push — see `publish_update`."""
    return f"NOVA:scanjob:{scan_job_id}:updates"


def publish_update(scan_job_id: str, event: dict) -> None:
    """
    Best-effort push notification for the scan-progress WebSocket. Never
    raises: this is a nice-to-have for connected browser clients, not part
    of the scan pipeline's correctness — a dropped publish just means a WS
    client falls back to its next poll/reconnect instead of an instant
    update, whereas letting a Redis hiccup here raise would take down the
    scanner task or job-lifecycle transition that triggered it.
    """
    try:
        r = _get_redis()
        r.publish(updates_channel(scan_job_id), json.dumps(event))
    except redis.RedisError:
        pass


def mark_cancelled(scan_job_id: str) -> None:
    """
    Set by the cancel API endpoint alongside the authoritative Postgres
    ScanJob.status update. The 9 parallel scanner tasks check this instead
    of querying Postgres directly — a plain key read is far cheaper than
    9 concurrent DB round-trips every time a job might be cancelled.
    """
    r = _get_redis()
    r.set(_cancelled_key(scan_job_id), "1", ex=TTL_SECONDS)


def is_cancelled(scan_job_id: str) -> bool:
    return _get_redis().exists(_cancelled_key(scan_job_id)) == 1


def set_status(
    scan_job_id: str,
    scanner_name: str,
    status: str,
    *,
    task_id: Optional[str] = None,
    error: Optional[str] = None,
    findings_count: Optional[int] = None,
) -> None:
    """status: queued | running | completed | failed | cancelled"""
    r = _get_redis()
    payload = {"status": status, "updated_at": time.time()}
    if task_id is not None:
        payload["task_id"] = task_id
    if error is not None:
        payload["error"] = error
    if findings_count is not None:
        payload["findings_count"] = findings_count

    key = _status_key(scan_job_id)
    r.hset(key, scanner_name, json.dumps(payload))
    r.expire(key, TTL_SECONDS)
    publish_update(scan_job_id, {"type": "worker_status", "scanner": scanner_name, **payload})


def register_task_id(scan_job_id: str, task_id: str) -> None:
    key = _task_ids_key(scan_job_id)
    r = _get_redis()
    r.sadd(key, task_id)
    r.expire(key, TTL_SECONDS)


def get_all_task_ids(scan_job_id: str) -> set[str]:
    return _get_redis().smembers(_task_ids_key(scan_job_id))


def get_worker_status(scan_job_id: str) -> dict[str, dict]:
    raw = _get_redis().hgetall(_status_key(scan_job_id))
    return {name: json.loads(payload) for name, payload in raw.items()}


def clear(scan_job_id: str) -> None:
    r = _get_redis()
    r.delete(_status_key(scan_job_id))
    r.delete(_task_ids_key(scan_job_id))
    r.delete(_cancelled_key(scan_job_id))
