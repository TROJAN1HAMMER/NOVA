"""
NOVA — Async Database Session
Provides the SQLAlchemy 2 async engine/sessionmaker and the `get_db`
FastAPI dependency used for constructor/route-level dependency injection
into repositories (Phase 2).

Pooling strategy differs by process kind, and that difference is load-
bearing, not an optimization: the FastAPI API process runs one persistent
event loop for its entire life (uvicorn), so a connection pool's entries
stay valid for as long as the process does — safe and worth the reuse.
Every Celery worker/beat task, by contrast, is its own `asyncio.run(...)`
call (see app/tasks/*.py) — a fresh event loop is created and torn down
per task, in the same OS process, sharing this same module-level `engine`
singleton. A pooled connection checked out under one task's loop has an
asyncio transport bound to that loop; once the loop closes, the
connection is unusable, and `pool_pre_ping`'s health check on the *next*
task's checkout doesn't fail gracefully — it crashes with a low-level
`AttributeError: 'NoneType' object has no attribute 'send'` deep in
asyncio's proactor, since the transport's loop reference is simply gone.
`celery_worker.py` sets `NOVA_WORKER_PROCESS` before importing anything
else specifically so this module can give worker/beat processes a
`NullPool` engine instead — no pooling at all means no connection ever
outlives the event loop that created it.
"""

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

_is_worker_process = os.environ.get("NOVA_WORKER_PROCESS") == "1"

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    future=True,
    **({"poolclass": NullPool} if _is_worker_process else {"pool_pre_ping": True}),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency: `db: AsyncSession = Depends(get_db)`.
    Commits on success, rolls back on any exception, always closes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
