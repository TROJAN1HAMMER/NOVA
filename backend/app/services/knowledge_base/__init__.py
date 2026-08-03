"""
NOVA — Knowledge Base (RAG Milestone 1: infrastructure only)

Document ingestion pipeline: upload -> extract -> chunk -> embed -> store
-> search. Deliberately does NOT call the LLM gateway anywhere in this
package — that integration (grounded remediation guidance, compliance
Q&A, etc.) is a later milestone; this one only builds the retrieval
substrate and proves it works end to end via a raw similarity-search API.

Modules:
  chunking.py          — text extraction (PDF/Markdown/text) + semantic
                         chunking, preserving headings/section hierarchy/
                         page numbers.
  embedding_manager.py — local ONNX embedding model wrapper (no external
                         API call; see its docstring for why).
  vector_store.py      — pgvector insert/delete/search over
                         `KnowledgeChunk` (app/models/knowledge.py).
  document_manager.py  — upload orchestration: validate, hash, save to
                         disk, persist metadata (app/repositories/
                         knowledge_document_repository.py).
  search_service.py     — the single entry point
                         app/api/v1/endpoints/knowledge.py calls for
                         search; wraps embedding_manager + vector_store.
"""
