"""
NOVA — Knowledge Base Routes
RAG Milestone 1: upload/list/delete/search over the knowledge base.
Deliberately does not call the LLM gateway anywhere in this file —
POST /knowledge/search returns raw matched chunks only. Wiring this into
AI-generated answers is a later milestone (see
app/services/knowledge_base/__init__.py's docstring).

RBAC (app/auth/permissions.py): KNOWLEDGE_WRITE gates upload/delete
(Security Analyst + Admin); KNOWLEDGE_READ gates list/search (also
Security Manager, Executive/Board — search only, no curation).
"""

import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import Permission, require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.middleware.rate_limit import require_rate_limit
from app.models.user import User
from app.repositories.deps import get_knowledge_document_repository
from app.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from app.schemas.knowledge import (
    DocumentDeleteResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentUploadResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.audit.audit_logger import log_action
from app.services.knowledge_base import document_manager, search_service
from app.tasks.knowledge_tasks import process_knowledge_document_task

router = APIRouter()

_UPLOAD_RATE_LIMIT = require_rate_limit("knowledge_upload", limit=10, window_seconds=60)
_SEARCH_RATE_LIMIT = require_rate_limit("knowledge_search", limit=30, window_seconds=60)


@router.post("/knowledge/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_WRITE))],
    _rate_limited: Annotated[User, Depends(_UPLOAD_RATE_LIMIT)],
    knowledge_documents: Annotated[KnowledgeDocumentRepository, Depends(get_knowledge_document_repository)],
    db: Annotated[AsyncSession, Depends(get_db)],
    version: Annotated[Optional[str], Form()] = None,
    author: Annotated[Optional[str], Form()] = None,
    tags: Annotated[Optional[str], Form()] = None,
):
    """
    Upload a PDF/Markdown/text document. Returns immediately with status
    "pending" — extraction/chunking/embedding runs asynchronously; poll
    GET /knowledge/documents to see it advance to "indexed" (or "failed").
    `tags` is a comma-separated string, e.g. "pci-dss,payments".
    """
    content = await file.read()
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []

    document = await document_manager.save_and_register_document(
        repo=knowledge_documents,
        filename=file.filename,
        content=content,
        version=version,
        author=author,
        tags=tag_list,
        uploaded_by_id=current_user.id,
    )
    await db.commit()

    process_knowledge_document_task.delay(str(document.id))

    await log_action(
        user=current_user,
        action="knowledge.document_uploaded",
        resource_type="knowledge_document",
        resource_id=str(document.id),
        details={"filename": document.filename, "document_type": document.document_type},
    )

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        document_type=document.document_type,
        version=document.version,
        status=document.status,
        tags=document.tags,
        created_at=document.created_at,
    )


@router.get("/knowledge/documents", response_model=DocumentListResponse)
async def list_documents(
    _current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    knowledge_documents: Annotated[KnowledgeDocumentRepository, Depends(get_knowledge_document_repository)],
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
):
    documents = await knowledge_documents.list_all(document_type=document_type, status=status, tag=tag)
    items = [
        DocumentListItem(
            id=doc.id,
            filename=doc.filename,
            document_type=doc.document_type,
            version=doc.version,
            author=doc.author,
            tags=doc.tags,
            status=doc.status,
            error_message=doc.error_message,
            file_size_bytes=doc.file_size_bytes,
            page_count=doc.page_count,
            chunk_count=doc.chunk_count,
            uploaded_by_email=doc.uploaded_by.email if doc.uploaded_by else None,
            created_at=doc.created_at,
        )
        for doc in documents
    ]
    return DocumentListResponse(total=len(items), documents=items)


@router.delete("/knowledge/document/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_WRITE))],
    knowledge_documents: Annotated[KnowledgeDocumentRepository, Depends(get_knowledge_document_repository)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Deletes the document row (cascades to its chunks) and its on-disk file."""
    document = await knowledge_documents.get(document_id)
    if document is None:
        raise NotFoundError(f"Knowledge document '{document_id}' not found.")

    filename = document.filename
    file_path = document.file_path

    await knowledge_documents.delete(document)
    await db.commit()

    Path(file_path).unlink(missing_ok=True)

    await log_action(
        user=current_user,
        action="knowledge.document_deleted",
        resource_type="knowledge_document",
        resource_id=str(document_id),
        details={"filename": filename},
    )

    return DocumentDeleteResponse(id=document_id, filename=filename)


@router.post("/knowledge/search", response_model=SearchResponse)
async def search_knowledge(
    payload: SearchRequest,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    _rate_limited: Annotated[User, Depends(_SEARCH_RATE_LIMIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await search_service.search(
        db,
        query=payload.query,
        top_k=payload.top_k,
        document_type=payload.document_type,
        tag=payload.tag,
        user_id=current_user.id,
    )
    return SearchResponse(**result)
