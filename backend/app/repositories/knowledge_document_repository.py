"""
NOVA — Knowledge Document Repository
Metadata storage for the knowledge base (see app/models/knowledge.py's
docstring for the document lifecycle and version-chain scheme). Chunk/
embedding persistence and similarity search live in
app/services/knowledge_base/vector_store.py instead — that's a
search/write concern over `KnowledgeChunk`, distinct from this
repository's document-metadata CRUD, the same split
ScanResultRepository/FindingRepository already draw for scan data.
"""

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.knowledge import KnowledgeDocument


class KnowledgeDocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        filename: str,
        document_type: str,
        version: str,
        content_hash: str,
        author: Optional[str],
        tags: list[str],
        file_path: str,
        file_size_bytes: int,
        uploaded_by_id: Optional[uuid.UUID],
        document_group_id: Optional[uuid.UUID] = None,
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            filename=filename,
            document_type=document_type,
            version=version,
            content_hash=content_hash,
            author=author,
            tags=tags,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            uploaded_by_id=uploaded_by_id,
            status="pending",
            # A brand-new document family is its own group (see
            # app/models/knowledge.py's docstring) — self-referential once
            # flushed, so `flush()` must happen before this can be read.
            document_group_id=document_group_id or uuid.uuid4(),
            is_latest=True,
        )
        self.db.add(document)
        await self.db.flush()
        if document_group_id is None:
            document.document_group_id = document.id
            await self.db.flush()
        return document

    async def get(self, document_id: uuid.UUID) -> Optional[KnowledgeDocument]:
        result = await self.db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        document_type: Optional[str] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        include_superseded: bool = False,
    ) -> list[KnowledgeDocument]:
        query = select(KnowledgeDocument).options(selectinload(KnowledgeDocument.uploaded_by))
        if not include_superseded:
            query = query.where(KnowledgeDocument.is_latest.is_(True))
        if document_type:
            query = query.where(KnowledgeDocument.document_type == document_type)
        if status:
            query = query.where(KnowledgeDocument.status == status)
        if tag:
            query = query.where(KnowledgeDocument.tags.contains([tag]))
        query = query.order_by(KnowledgeDocument.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def find_by_content_hash(self, content_hash: str) -> Optional[KnowledgeDocument]:
        """Any document with this exact hash, anywhere — including
        superseded versions — since an exact byte-for-byte duplicate is a
        duplicate regardless of which version slot it would land in."""
        result = await self.db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.content_hash == content_hash)
        )
        return result.scalars().first()

    async def find_latest_by_filename(self, filename: str) -> Optional[KnowledgeDocument]:
        """Case-insensitive — `Policy.pdf` and `policy.pdf` are the same
        document family for versioning purposes."""
        result = await self.db.execute(
            select(KnowledgeDocument).where(
                func.lower(KnowledgeDocument.filename) == filename.lower(),
                KnowledgeDocument.is_latest.is_(True),
            )
        )
        return result.scalars().first()

    async def count_versions_in_group(self, document_group_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(KnowledgeDocument.document_group_id == document_group_id)
        )
        return result.scalar_one()

    async def supersede(self, document: KnowledgeDocument) -> None:
        """Marks a document as no longer the latest version of its group
        — its row and on-disk file are kept for history, only its
        searchability changes (see vector_store.similarity_search's
        `is_latest` filter). Chunk/embedding pruning is the caller's
        responsibility (app/services/knowledge_base/document_manager.py),
        since that's a vector_store concern, not a metadata one."""
        document.is_latest = False
        await self.db.flush()

    async def mark_processing(self, document_id: uuid.UUID) -> None:
        document = await self.get(document_id)
        if document:
            document.status = "processing"
            document.error_message = None
            await self.db.flush()

    async def mark_indexed(self, document_id: uuid.UUID, *, page_count: Optional[int], chunk_count: int) -> None:
        document = await self.get(document_id)
        if document:
            document.status = "indexed"
            document.page_count = page_count
            document.chunk_count = chunk_count
            document.error_message = None
            await self.db.flush()

    async def mark_failed(self, document_id: uuid.UUID, *, error_message: str) -> None:
        document = await self.get(document_id)
        if document:
            document.status = "failed"
            document.error_message = error_message
            await self.db.flush()

    async def delete(self, document: KnowledgeDocument) -> None:
        await self.db.delete(document)
        await self.db.flush()
