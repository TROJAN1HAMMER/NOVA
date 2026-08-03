"""
NOVA — Knowledge Document Manager
Upload orchestration: validates the file, computes its content hash,
saves it to disk under settings.knowledge_base_dir, and persists the
metadata row — then the caller (app/api/v1/endpoints/knowledge.py)
dispatches app/tasks/knowledge_tasks.py for the actual extraction/
chunking/embedding, so the upload request itself returns immediately
(the same async-job shape as ScanJob/Report).

Milestone 5 additions, both applied here (the upload entry point) rather
than deeper in the pipeline, since both are upload-time decisions:
  - Duplicate detection now REJECTS an exact byte-for-byte re-upload
    (409, via `find_duplicate_by_hash`) instead of merely logging it —
    Milestone 1 created a new row and re-indexed identical content every
    time the same file was uploaded twice.
  - Document versioning: uploading a file whose FILENAME (case-
    insensitive) matches an existing latest version registers it as the
    next version in that document's group instead of an unrelated
    document — see `find_or_start_version_chain` and app/models/
    knowledge.py's docstring for the group_id/is_latest scheme.
"""

import hashlib
import uuid
from pathlib import Path
from typing import Optional

import structlog

from app.config import get_settings
from app.core.exceptions import ConflictError, ValidationAppError
from app.models.knowledge import KnowledgeDocument
from app.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from app.services.knowledge_base import vector_store
from app.services.knowledge_base.chunking import UnsupportedDocumentTypeError, detect_document_type

logger = structlog.get_logger(__name__)
settings = get_settings()


async def find_duplicate_by_hash(
    repo: KnowledgeDocumentRepository, *, content_hash: str
) -> Optional[KnowledgeDocument]:
    return await repo.find_by_content_hash(content_hash)


async def find_or_start_version_chain(
    repo: KnowledgeDocumentRepository, *, filename: str
) -> tuple[Optional[uuid.UUID], str]:
    """
    Returns `(document_group_id, next_version_label)`. `document_group_id`
    is `None` when this filename has no prior version — `repo.create()`
    treats that as "start a new group." When a previous latest version
    IS found, it is superseded here (metadata flip + chunk pruning) so
    the caller never has two `is_latest=True` rows in the same group even
    momentarily.
    """
    existing = await repo.find_latest_by_filename(filename)
    if existing is None:
        return None, "1"

    await vector_store.delete_chunks_for_document(repo.db, document_id=existing.id)
    await repo.supersede(existing)

    version_count = await repo.count_versions_in_group(existing.document_group_id)
    logger.info(
        "knowledge.document_superseded",
        filename=filename,
        superseded_document_id=str(existing.id),
        document_group_id=str(existing.document_group_id),
        next_version=str(version_count + 1),
    )
    return existing.document_group_id, str(version_count + 1)


async def save_and_register_document(
    *,
    repo: KnowledgeDocumentRepository,
    filename: str,
    content: bytes,
    version: Optional[str],
    author: Optional[str],
    tags: list[str],
    uploaded_by_id: Optional[uuid.UUID],
) -> KnowledgeDocument:
    max_bytes = settings.knowledge_max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValidationAppError(f"File exceeds the {settings.knowledge_max_upload_mb}MB upload limit.")
    if len(content) == 0:
        raise ValidationAppError("Uploaded file is empty.")

    try:
        document_type = detect_document_type(filename)
    except UnsupportedDocumentTypeError as exc:
        raise ValidationAppError(str(exc)) from exc

    content_hash = hashlib.sha256(content).hexdigest()

    duplicate = await find_duplicate_by_hash(repo, content_hash=content_hash)
    if duplicate is not None:
        logger.info(
            "knowledge.duplicate_upload_rejected",
            filename=filename,
            existing_document_id=str(duplicate.id),
            existing_filename=duplicate.filename,
        )
        raise ConflictError(
            f"This exact file is already in the knowledge base as '{duplicate.filename}' "
            f"(uploaded {duplicate.created_at.date().isoformat()}).",
            details={"existing_document_id": str(duplicate.id), "existing_filename": duplicate.filename},
        )

    document_group_id, auto_version = await find_or_start_version_chain(repo, filename=filename)

    storage_dir = Path(settings.knowledge_base_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{uuid.uuid4().hex}_{filename}"
    file_path.write_bytes(content)

    document = await repo.create(
        filename=filename,
        document_type=document_type,
        version=version or auto_version,
        content_hash=content_hash,
        author=author,
        tags=tags,
        file_path=str(file_path),
        file_size_bytes=len(content),
        uploaded_by_id=uploaded_by_id,
        document_group_id=document_group_id,
    )
    logger.info(
        "knowledge.upload_saved",
        document_id=str(document.id),
        filename=filename,
        document_type=document_type,
        size_bytes=len(content),
        version=document.version,
        is_new_version_of_existing_group=document_group_id is not None,
    )
    return document
