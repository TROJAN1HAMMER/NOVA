"""
NOVA — Knowledge Base Schemas
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    document_type: str
    version: str
    status: str
    tags: list[str]
    created_at: datetime


class DocumentListItem(BaseModel):
    id: uuid.UUID
    filename: str
    document_type: str
    version: str
    author: Optional[str] = None
    tags: list[str]
    status: str
    error_message: Optional[str] = None
    file_size_bytes: int
    page_count: Optional[int] = None
    chunk_count: int
    uploaded_by_email: Optional[str] = None
    created_at: datetime


class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentListItem]


class DocumentDeleteResponse(BaseModel):
    id: uuid.UUID
    filename: str
    deleted: bool = True


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_type: Optional[str] = None
    tag: Optional[str] = None


class SearchResultItem(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    content: str
    similarity_score: float
    page_number: Optional[int] = None
    heading: Optional[str] = None
    section_path: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    took_ms: float
    results: list[SearchResultItem]
