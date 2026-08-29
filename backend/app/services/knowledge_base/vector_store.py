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
    query_text: Optional[str] = None,
) -> list[tuple[KnowledgeChunk, float]]:
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
    query = (
        select(KnowledgeChunk, distance.label("distance"))
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .options(selectinload(KnowledgeChunk.document))
        .where(KnowledgeDocument.status.in_(["indexed", "ready", "processed"]))
        .where(KnowledgeDocument.is_latest.is_(True))
    )
    if document_type:
        query = query.where(KnowledgeDocument.document_type == document_type)
    if tag:
        query = query.where(KnowledgeDocument.tags.contains([tag]))
    if document_id:
        query = query.where(KnowledgeChunk.document_id == document_id)
    query = query.order_by(distance).limit(100)

    result = await db.execute(query)
    rows = result.all()

    # Hybrid Dense + Text Matching Boost for acronyms / specific codes (e.g. FAPI-03, PCI-DSS)
    terms = []
    if query_text:
        raw_terms = [t.strip("?,.!\"'()") for t in query_text.split()]
        terms = [t.lower() for t in raw_terms if len(t) > 2]

    scored: list[tuple[KnowledgeChunk, float]] = []
    for chunk, dist in rows:
        sim = 1.0 - float(dist)
        if terms:
            content_lower = chunk.content.lower()
            matched_terms = [t for t in terms if t in content_lower]
            if matched_terms:
                # Boost match score if query terms occur directly in chunk content
                sim = max(sim, 0.85 + min(0.10, len(matched_terms) * 0.05))
        scored.append((chunk, round(sim, 4)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
