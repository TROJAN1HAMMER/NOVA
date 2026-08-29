"""
NOVA — Knowledge Base Document Ingestion
Dispatched from POST /knowledge/upload so the upload request returns
immediately; this task does the actual extraction -> chunking ->
embedding -> vector-store insert, advancing the document's status
(pending -> processing -> indexed | failed) as it goes — the same
async-job shape as app/tasks/report_tasks.py.

Deliberately does not call the LLM gateway anywhere — embeddings only,
per RAG Milestone 1's scope (no AI integration yet).

Milestone 5: failures are split into retryable (transient — the
embedding model failed to load, a DB/Redis hiccup) vs. permanent (a
corrupt file, no extractable text, an unsupported structure) rather than
marking every failure "failed" on the first attempt. A transient failure
during a brief Redis/model blip shouldn't permanently strand a document
that would have indexed fine a few seconds later.
"""

import asyncio
import uuid

import structlog

from app.core.exceptions import ServiceUnavailableError
from app.db.session import AsyncSessionLocal
from app.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from app.services.knowledge_base import embedding_manager, vector_store
from app.services.knowledge_base.chunking import chunk_document, extract_pages
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Retryable errors are transient by nature (a model that failed to load
# once may load fine on the next attempt; a DB/Redis blip resolves on its
# own) — everything else (corrupt file, unsupported structure, no
# extractable text) is permanent: retrying won't change the outcome, so
# there's no reason to delay reporting it to the user.
RETRYABLE_EXCEPTIONS = (ServiceUnavailableError, ConnectionError, TimeoutError)


def retry_backoff_seconds(attempt: int) -> int:
    """15s, 30s, 60s, ... — exponential, enough spacing for a transient
    model-load or Redis blip to clear without hammering the same failure
    immediately. `attempt` is 0-indexed (task.request.retries)."""
    return 15 * (2**attempt)


@celery_app.task(
    name="NOVA.process_knowledge_document",
    bind=True,
    max_retries=3,
    acks_late=True,
    queue="NOVA.low",
)
def process_knowledge_document_task(self, document_id: str) -> None:
    asyncio.run(_process(self, document_id))


async def _process(task, document_id: str) -> None:
    doc_uuid = uuid.UUID(document_id)

    async with AsyncSessionLocal() as db:
        repo = KnowledgeDocumentRepository(db)
        document = await repo.get(doc_uuid)
        if document is None:
            logger.warning("knowledge_tasks.document_not_found", document_id=document_id)
            return

        await repo.mark_processing(doc_uuid)
        await db.commit()

        try:
            pages = extract_pages(document.file_path, document.document_type)
            chunks = chunk_document(pages, document.document_type)
            if not chunks:
                raise ValueError("No extractable text found in this document.")

            logger.info(
                "knowledge_tasks.chunked",
                document_id=document_id,
                page_count=len(pages),
                chunk_count=len(chunks),
            )

            embeddings = embedding_manager.embed_passages([chunk.content for chunk in chunks])

            chunk_dicts = [
                {
                    "content": chunk.content,
                    "heading": chunk.heading,
                    "section_path": chunk.section_path,
                    "page_number": chunk.page_number,
                    "token_count": chunk.token_count,
                    "embedding": embedding,
                }
                for chunk, embedding in zip(chunks, embeddings)
            ]
            await vector_store.insert_chunks(db, document_id=doc_uuid, chunks=chunk_dicts)

            try:
                from app.services.knowledge_base.graph_builder import extract_and_save_graph_entities
                await extract_and_save_graph_entities(db, document_id=doc_uuid, chunks=chunk_dicts)
            except Exception as graph_err:
                logger.warning("knowledge_tasks.graph_extraction_failed", error=str(graph_err))

            page_count = len(pages) if pages and pages[0].page_number is not None else None
            await repo.mark_indexed(doc_uuid, page_count=page_count, chunk_count=len(chunks))
            await db.commit()

            logger.info(
                "knowledge_tasks.indexed",
                document_id=document_id,
                chunk_count=len(chunks),
                page_count=page_count,
            )
        except RETRYABLE_EXCEPTIONS as exc:
            await db.rollback()
            retries_left = task.max_retries - task.request.retries
            if retries_left > 0:
                logger.warning(
                    "knowledge_tasks.transient_failure_retrying",
                    document_id=document_id,
                    error=str(exc),
                    attempt=task.request.retries + 1,
                    retries_left=retries_left,
                )
                raise task.retry(exc=exc, countdown=retry_backoff_seconds(task.request.retries))
            logger.error("knowledge_tasks.retries_exhausted", document_id=document_id, error=str(exc))
            await repo.mark_failed(doc_uuid, error_message=f"Failed after {task.max_retries} retries: {exc}")
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("knowledge_tasks.permanent_failure", document_id=document_id, error=str(exc))
            await repo.mark_failed(doc_uuid, error_message=str(exc))
            await db.commit()
