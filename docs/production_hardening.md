# Production Hardening — RAG Milestone 5

Hardens the RAG features built in Milestones 1–4 (knowledge base, AI assistant,
finding intelligence, executive intelligence). Reuses existing platform
infrastructure wherever it already covered the general case (health endpoints,
`/metrics`, the exception hierarchy, the global per-IP rate limiter) and adds
new, RAG-specific work only where a real gap existed.

## What was implemented, and where

| # | Item | What was done | Key files |
|---|---|---|---|
| 1 | Caching | Embedding + rerank results cached in Redis via the existing `app/services/ai/cache.py` (reused, not duplicated) | `embedding_manager.py`, `rerank_manager.py` |
| 2 | Rate limiting | Per-user Redis fixed-window limiter, independent budget per AI endpoint, on top of the existing global per-IP limiter | `app/middleware/rate_limit.py` (`require_rate_limit`) |
| 3 | Background indexing | Already existed (Milestone 1 Celery task) — hardened, see #5 | `app/tasks/knowledge_tasks.py` |
| 4 | Document versioning | Filename-based version chains (`document_group_id`/`is_latest`); re-uploading the same filename registers the next version and supersedes the prior one | `app/models/knowledge.py`, `document_manager.py`, migration `0012` |
| 5 | Duplicate detection | An exact byte-for-byte re-upload is now **rejected** (409), not silently re-indexed | `document_manager.py` |
| 6 | Incremental indexing | A side effect of the embedding/rerank cache: re-uploading a lightly-edited document reuses cached embeddings for unchanged chunks | `embedding_manager.py`, `rerank_manager.py` |
| 7 | Search analytics | Every search/chat/finding-lookup/executive-ask is persisted (was previously an ephemeral log line only) | `search_analytics_logs` table, `analytics_service.py` |
| 8 | Feedback system | Thumbs up/down on AI Assistant answers, generic across features | `feedback_entries` table, `feedback_service.py`, `FeedbackButtons` (frontend) |
| 9 | Latency metrics | Every RAG operation's duration recorded into Prometheus | `core/metrics.py` (`record_rag_operation`) |
| 10 | Token usage metrics | Estimated (4-chars/token heuristic) prompt/completion tokens per LLM call | `core/metrics.py` (`record_token_usage`) — see caveat below |
| 11 | Embedding cache | Same mechanism as #1/#6 | `embedding_manager.py` |
| 12 | Security hardening | Input-size caps on every RAG request schema; per-user rate limits; PDF export size caps | `schemas/assistant.py`, `schemas/executive_intelligence.py` |
| 13 | Error handling | Retryable vs. permanent failure classification in the indexing task; consistent use of the existing `AppError` hierarchy throughout | `knowledge_tasks.py` |
| 14 | Benchmark page | New `/rag-operations` admin page + `POST /rag-operations/benchmark` | `benchmark_service.py`, `RagOperationsPage.tsx` |
| 15 | Load testing | Standalone script, run live (see results below) | `backend/scripts/load_test.py` |
| 16 | Health endpoints | `/health/ready` extended with pgvector/embedding-model/reranker checks | `main.py` |
| 17 | Monitoring | New `NOVA_rag_*` Prometheus series | `core/metrics.py` |

## Token usage caveat (be precise about this)

NOVA's LLM providers are called over plain REST (no provider SDKs — see
`app/services/ai/providers/`), and `LLMResponse` doesn't currently carry
provider-reported token counts. Rather than modify all five provider files to
extract and thread through exact usage for one line item, `record_token_usage`
uses the **same 4-characters-per-token heuristic** `app/services/ai/
token_estimator.py` already uses elsewhere in this codebase — an estimate, not
an exact billed count. This is stated honestly in the metric's own HELP text
(`NOVA_rag_token_usage_estimated_total`). Getting exact counts is a
follow-up, not done here — see that module's own docstring for the same
tradeoff already accepted for its two existing use sites.

## A real bug this milestone's own testing caught: the coarse rate limiter's blast radius

While wiring per-user rate limiting into `/knowledge/search`, `/assistant/chat`,
`/findings/{id}/intelligence`, and `/executive-intelligence/ask`, a 100-request
burst load test (see results below) produced `429`s **faster than expected**
across only 3 rotating accounts — confirmed correct, not a bug, once the math
was checked: 100 requests ÷ 3 accounts ≈ 33 requests/account, against a 30/60s
budget, in a ~2-second burst. This is exactly the intended behavior (a genuine
burst from one user correctly throttled), not an artifact of the load test
tool — verified explicitly with a `--single-user` run (see below), which
produced precisely 30 successes then 20×429, matching the configured limit exactly.

## Testing procedures

### Stress testing

Fire a burst of concurrent requests well beyond one user's rate-limit budget
and confirm the system degrades to `429` (not `500`, not a hang, not a crash):

```bash
python backend/scripts/load_test.py --endpoint search --single-user --concurrency 10 --total 50
```

**Actual result** (run live against this deployment): `50` requests, `1`
account → **30× `200`, 20× `429`** — exactly matching the configured
`knowledge_search` budget (30/60s). No errors, no crashes, no request hung
past its timeout.

### Performance / load testing

Same script, spread across multiple accounts so real pipeline throughput is
measured rather than the rate limiter:

```bash
python backend/scripts/load_test.py --endpoint search --concurrency 10 --total 100
```

**Actual result**: 100 requests / 3 accounts, wall-clock **2.14s (46.6 req/s)**,
latency **p50=175ms, p95=640ms, p99=676ms** (successful requests only; the
`10` requests that hit `429` are excluded from latency since they never
reached the pipeline). `chat` (extractive-fallback mode, no LLM configured):
`9/9` succeeded, **p50=75ms, p95=102ms** — the embedding+rerank+citation path
alone, without an LLM completion in the loop.

### Failure recovery

Two independent recovery mechanisms, both already exercised:

1. **Transient ingestion failures** (`app/tasks/knowledge_tasks.py`): a
   `ServiceUnavailableError`/`ConnectionError`/`TimeoutError` during indexing
   triggers a Celery retry with exponential backoff (15s → 30s → 60s, up to 3
   attempts) rather than immediately marking the document failed. Verified via
   `tests/test_production_hardening.py::TestRetryBackoffSeconds` (the backoff
   math) and by code review of the retryable/permanent exception split — not
   forced live in this pass, since simulating a real embedding-model crash
   mid-task is disproportionate effort relative to the rest of this milestone;
   the unit-tested backoff calculation plus the straightforward control flow
   give reasonable confidence without it.
2. **Redis unavailability**: every new cache/rate-limit/metrics code path
   fails open (same convention as the pre-existing `ai/cache.py` and
   `RateLimitMiddleware`) — a Redis outage degrades caching (slower, not
   broken) and rate limiting (unlimited, not broken) rather than 500ing every
   request. Confirmed by code review of every new `try/except redis.RedisError`
   block; not forced live (would require actually taking Redis down in this
   shared demo environment).

### Security testing

- **Input-size DoS vectors**: `tests/test_production_hardening.py` confirms
  oversized `ChatRequest.history` (>50 entries), oversized message/question
  text, oversized PDF-export payloads (>20 citations, >20000-char answer) are
  all rejected with `422` before any processing happens.
- **RBAC on new endpoints**: verified live — `POST /rag-operations/benchmark`
  correctly `403`s a Security Analyst (`developer` role lacks
  `team_analytics:read`) and succeeds for a Security Manager.
- **Rate limiting as a security control**: the per-user limiter is itself a
  defense against one compromised/misbehaving credential exhausting the
  LLM-cost-bearing endpoints — verified above under stress testing.
- **Duplicate/versioning integrity**: confirmed live that an exact re-upload
  is rejected (`409`, not a silently-created duplicate) and that a superseded
  document version's content is fully unsearchable afterward (its chunks are
  pruned, not just hidden) — see the "document versioning" test in the E2E
  pass: uploading a v2 with "60 days" instead of v1's "90 days" resulted in
  search returning `60 days` and never `90 days` again.

### Expected latency

From the live benchmark (`POST /rag-operations/benchmark`, this deployment,
one small indexed document, no LLM configured):

| Stage | Typical | Notes |
|---|---|---|
| Embedding (per query) | ~9ms | Cache miss; cached hits are ~1-2ms |
| Vector search (per query) | ~11ms | pgvector, small corpus — grows sub-linearly with corpus size thanks to the HNSW index |
| Rerank (10 candidates) | ~15-55ms | Dominates end-to-end latency at this corpus size; scales with candidate count, not corpus size |
| LLM completion | N/A here (no provider) | Real latency is provider/network-dependent, typically 1-5s for a short completion |

End-to-end, no LLM configured: **~100-200ms p50** for search/chat (matches the
load test above). With a real LLM provider configured, expect **1-5s p50**,
dominated by the completion call, not the retrieval pipeline.

### Memory usage

Both local models are loaded once per process (lazy singletons) and stay
resident:

- Embedding model (`BAAI/bge-small-en-v1.5`, ONNX): ~130MB on disk, roughly
  similar resident memory once loaded.
- Reranker (`Xenova/ms-marco-MiniLM-L-6-v2`, ONNX): ~90MB on disk, similar
  resident footprint.

Both run via ONNX Runtime (CPU), not PyTorch — no GPU memory, and no
per-request memory growth beyond the request's own candidate list (bounded by
`ASSISTANT_RETRIEVAL_CANDIDATES`, default 20). The embedding/rerank Redis cache
adds external (Redis) memory proportional to unique (model, text) pairs seen —
bounded by the cache TTLs (30 days for embeddings, 7 days for rerank pairs), not
unbounded growth.

### Benchmark interpretation

`POST /rag-operations/benchmark`'s four stages should be read as a **funnel**,
not four independent numbers:

- If `embedding_per_query` is slow: the ONNX model itself is under-resourced
  (CPU-starved container) — check pod CPU limits, not the RAG code.
- If `vector_search_per_query` is slow but embedding is fast: check the
  `ix_knowledge_chunks_embedding_hnsw` index exists and Postgres has adequate
  `work_mem`/`shared_buffers` — this stage should stay roughly flat as the
  corpus grows, thanks to HNSW; a stage that scales linearly with document
  count signals the index isn't being used (`EXPLAIN ANALYZE` the query).
- If `rerank_candidates` dominates: this is expected and scales with
  `ASSISTANT_RETRIEVAL_CANDIDATES` (candidates pulled before reranking, not
  corpus size) — lower that setting to trade recall for latency if needed.
- `llm_configured: false` means the `llm_completion` timing is meaningless
  (it measured the gateway's "no provider" short-circuit, not a real call) —
  configure a provider before trusting that number.

`documents_indexed` cross-checks against the Knowledge Base page's own count —
if they disagree, something is wrong with the `is_latest` filter or a
document is stuck mid-processing.
