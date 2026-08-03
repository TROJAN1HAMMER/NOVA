# Knowledge Base — RAG Milestone 1 (Infrastructure Only)

This document describes the knowledge base ingestion/search infrastructure added
in Milestone 1 of NOVA's RAG roadmap. **This milestone does not call any LLM.**
It proves the retrieval substrate (upload → extract → chunk → embed → store →
search) works end to end, returning raw matched text chunks. Wiring this into
AI-generated answers (grounded remediation guidance, compliance Q&A, etc.) is a
later milestone, deliberately not started here.

## Folder structure

```
backend/app/
  models/knowledge.py                    # KnowledgeDocument, KnowledgeChunk ORM models
  repositories/knowledge_document_repository.py   # document metadata CRUD
  schemas/knowledge.py                   # Pydantic request/response models
  services/knowledge_base/
    __init__.py
    chunking.py           # text extraction (PDF/Markdown/text) + semantic chunking
    embedding_manager.py  # local ONNX embedding model wrapper
    vector_store.py       # pgvector insert/delete/similarity-search
    document_manager.py   # upload orchestration (validate, hash, save, register)
    search_service.py     # orchestrates embed_query + vector_store.similarity_search
  tasks/knowledge_tasks.py               # Celery task: the actual ingestion pipeline
  api/v1/endpoints/knowledge.py          # POST /upload, GET /documents, DELETE /document/{id}, POST /search

frontend/src/
  types/api.ts                # KnowledgeDocument / KnowledgeSearchResult types
  lib/api/knowledge.ts         # API client
  hooks/useKnowledge.ts        # React Query hooks (list/upload/delete/search)
  pages/KnowledgeBasePage.tsx  # upload form, document table, search box + results

backend/alembic/versions/0011_knowledge_base.py   # pgvector extension + tables + HNSW index

data/knowledge_base/           # uploaded document files (host-mounted, persists across restarts)
data/fastembed_cache/          # embedding model, baked into the Docker image at build time
```

## How embeddings work

Embeddings are generated **locally, in-process**, by
[`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) running
via [fastembed](https://github.com/qdrant/fastembed) (ONNX Runtime — no PyTorch,
no GPU required). This is a deliberate choice, not just a convenience: document
text never leaves the deployment to reach a third-party embedding API, which
matters for internal banking documentation.

- **Model**: `BAAI/bge-small-en-v1.5`, 384 dimensions.
- **Pre-downloaded at Docker build time** (see `backend/Dockerfile`) into
  `data/fastembed_cache`, so no container needs internet access at runtime to
  embed a document or a search query.
- **Asymmetric encoding**: per the model's own documented convention, search
  queries are prefixed with an instruction
  (`"Represent this sentence for searching relevant passages: "`) before
  embedding; document chunks are embedded as-is, with no prefix. This measurably
  improves retrieval quality and is not a NOVA-specific invention — see
  `embedding_manager.py`.
- **Changing the model**: if `KNOWLEDGE_EMBEDDING_MODEL` / `KNOWLEDGE_EMBEDDING_DIM`
  are ever changed, the Docker image must be rebuilt (to pre-download the new
  model) and every existing document must be re-indexed — vectors from two
  different models are not comparable, so old chunks would silently produce
  meaningless similarity scores otherwise.

## How indexing works

1. `POST /knowledge/upload` validates the file (supported type, non-empty, under
   the size limit), computes a SHA-256 hash, saves it to
   `data/knowledge_base/`, and creates a `KnowledgeDocument` row with
   `status="pending"`. The request returns immediately — indexing itself is
   asynchronous, the same pattern NOVA already uses for scan report
   generation.
2. A Celery task (`NOVA.process_knowledge_document`, queue `NOVA.low`) picks
   it up, sets `status="processing"`, and:
   - Extracts text (per-page for PDFs, whole-file for Markdown/text).
   - Splits it into semantic chunks (`chunking.py`), preserving:
     - **Headings** — Markdown `#`/`##`/... syntax, or a numbered-heading
       heuristic (`1.2.3 Some Title`) for PDF/text.
     - **Section hierarchy** — a breadcrumb like `Access Control > Password
       Policy` built from the heading stack.
     - **Page numbers** — for PDFs only; Markdown/text have no page concept.
     - A small token overlap between consecutive chunks so a concept split
       across a chunk boundary isn't lost to either side.
   - Embeds every chunk (batched) via `embedding_manager.embed_passages`.
   - Replaces any existing chunks for the document and inserts the new ones
     with their vectors (`vector_store.insert_chunks`).
   - Sets `status="indexed"` with the final `page_count`/`chunk_count`.
3. If anything in step 2 fails (corrupt file, no extractable text, embedding
   error), the document is marked `status="failed"` with `error_message` set —
   it never gets stuck, and never crashes the worker process.

Chunk size is measured with the same 4-characters-per-token heuristic NOVA's
AI batching already uses (`app/services/ai/token_estimator.py`), not a real
tokenizer — precise enough for chunk-boundary decisions, consistent with the
rest of the codebase.

## Vector storage and search

Vectors are stored in **Postgres itself**, via the
[pgvector](https://github.com/pgvector/pgvector) extension (image
`pgvector/pgvector:pg16`, a drop-in replacement for the previous
`postgres:16-alpine` — same data, same credentials, just the extension added).
No separate vector database service was introduced.

- An **HNSW index** (`vector_cosine_ops`) backs the similarity search — chosen
  over IVFFlat specifically because IVFFlat's cluster centroids are trained
  from existing data at index-build time, and this migration always runs
  against an empty table (no documents exist yet at migration time), which
  would produce a degenerate index. HNSW builds incrementally.
- `POST /knowledge/search` embeds the query, runs a cosine-similarity search
  filtered to `status="indexed"` documents (plus optional `document_type`/`tag`
  filters), and returns the top-K chunks with their `similarity_score`
  (1.0 = identical, 0.0 = unrelated), source filename, page number, heading,
  and section path.

## Supported file types

| Extension | Type | Page numbers | Heading detection |
|---|---|---|---|
| `.pdf` | `pdf` | Yes (per page) | Numbered-heading heuristic (`1.2.3 Title`) |
| `.md`, `.markdown` | `markdown` | No | Markdown `#`/`##`/... syntax |
| `.txt` | `text` | No | Numbered-heading heuristic |

Any other extension is rejected at upload time with a `422` and a clear message
— it never reaches the processing queue.

## RBAC

| Role | Upload / Delete | Search / List |
|---|---|---|
| Security Analyst (`developer`) | ✅ | ✅ |
| Administrator (`admin`) | ✅ | ✅ |
| Security Manager (`security_engineer`) | ❌ (403) | ✅ |
| Executive / Board (`auditor`) | ❌ (403) | ✅ |
| Read Only | ❌ | ❌ |

Enforced server-side via `Permission.KNOWLEDGE_WRITE` / `Permission.KNOWLEDGE_READ`
(`app/auth/permissions.py`) on every endpoint — the frontend also hides the
upload/delete UI for roles that lack `knowledge:write`, but that's UX only, not
the security boundary.

One subtlety worth knowing: NOVA's coarse `PermissionMiddleware` blocks
`auditor`/`read_only` from *any* mutating HTTP verb (POST/PUT/PATCH/DELETE) as a
blanket defense-in-depth rule. `POST /knowledge/search` is a read-only query
that happens to use POST (to carry a JSON body), so it's listed in that
middleware's `READ_ONLY_QUERY_PATH_PREFIXES` allowlist — every other POST
endpoint is unaffected.

## Configuration

All of the following have working defaults and normally never need to be set —
see `backend/.env.example`:

```
KNOWLEDGE_BASE_DIR=data/knowledge_base
KNOWLEDGE_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
KNOWLEDGE_EMBEDDING_DIM=384
KNOWLEDGE_EMBEDDING_CACHE_DIR=data/fastembed_cache
KNOWLEDGE_CHUNK_SIZE_TOKENS=350
KNOWLEDGE_CHUNK_OVERLAP_TOKENS=50
KNOWLEDGE_MAX_UPLOAD_MB=25
KNOWLEDGE_SEARCH_DEFAULT_TOP_K=5
```
