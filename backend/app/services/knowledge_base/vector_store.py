"""
NOVA — Vector Store (pgvector)
Insert/delete/search over `KnowledgeChunk.embedding` — the "vector
database interface" component of the knowledge base, backed by the
pgvector extension on the same Postgres instance the rest of NOVA
already uses (see docker-compose.yml / migration 0011) rather than a
separate vector database service, matching NOVA's general preference
for fewer moving infrastructure pieces where one already does the job.
"""

import uuid
from typing import Optional, TypedDict

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument

logger = structlog.get_logger(__name__)


class ChunkInput(TypedDict):
    content: str
    heading: Optional[str]
    section_path: Optional[str]
    page_number: Optional[int]
    token_count: int
    embedding: list[float]


async def insert_chunks(
    db: AsyncSession,
    *,
    document_id: uuid.UUID,
    chunks: list[ChunkInput],
) -> int:
    """
    Replaces any existing chunks for this document first, so this is safe
    to call again for the same document (a re-index), not just once at
    first upload.
    """
    await delete_chunks_for_document(db, document_id=document_id)
    rows = [
        KnowledgeChunk(
            document_id=document_id,
            chunk_index=index,
            content=chunk["content"],
            heading=chunk.get("heading"),
            section_path=chunk.get("section_path"),
            page_number=chunk.get("page_number"),
            token_count=chunk.get("token_count", 0),
            embedding=chunk["embedding"],
        )
        for index, chunk in enumerate(chunks)
    ]
    db.add_all(rows)
    await db.flush()
    return len(rows)


async def delete_chunks_for_document(db: AsyncSession, *, document_id: uuid.UUID) -> None:
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
    await db.flush()


async def similarity_search(
    db: AsyncSession,
    *,
    query_embedding: list[float],
    top_k: int,
    document_type: Optional[str] = None,
    tag: Optional[str] = None,
    document_id: Optional[uuid.UUID] = None,
) -> list[tuple[KnowledgeChunk, float]]:
    """
    Returns (chunk, similarity_score) pairs, highest similarity first.
    `similarity_score` is `1 - cosine_distance` (pgvector's `<=>` operator
    already returns `1 - cosine_similarity`), so 1.0 is an identical
    vector and 0.0 is orthogonal.

    Metadata filtering (document_type/tag/document_id) joins against
    KnowledgeDocument and only ever considers `status == "indexed"`
    documents — a document mid-processing or that failed to index has no
    chunks anyway, but the explicit filter keeps the query's intent clear.

    Also only ever considers `is_latest == True` (Milestone 5's version
    chains, see app/models/knowledge.py's docstring) — a superseded
    version's chunks are pruned at supersession time anyway
    (document_manager.py's `find_or_start_version_chain`), so this filter
    is normally a no-op rather than the primary guard, but keeping it
    explicit here means search is correct even if pruning is ever skipped
    for some future call site.
    """
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
    query = (
        select(KnowledgeChunk, distance.label("distance"))
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .options(selectinload(KnowledgeChunk.document))
        .where(KnowledgeDocument.status == "indexed")
        .where(KnowledgeDocument.is_latest.is_(True))
    )
    if document_type:
        query = query.where(KnowledgeDocument.document_type == document_type)
    if tag:
        query = query.where(KnowledgeDocument.tags.contains([tag]))
    if document_id:
        query = query.where(KnowledgeChunk.document_id == document_id)
    query = query.order_by(distance).limit(top_k)

    result = await db.execute(query)
    rows = result.all()
    return [(chunk, 1.0 - float(dist)) for chunk, dist in rows]
