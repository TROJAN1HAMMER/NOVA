"""
NOVA — Celery Worker Entrypoint
Run with:  celery -A celery_worker.celery_app worker --loglevel=info
"""

import os

# Must be set before anything imports app.db.session — see that module's
# docstring for why a worker/beat process needs a non-pooled engine.
os.environ["NOVA_WORKER_PROCESS"] = "1"

from app.workers.celery_app import celery_app  # noqa: E402

__all__ = ["celery_app"]
