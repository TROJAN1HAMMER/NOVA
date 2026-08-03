# AI Assistant — RAG Milestone 2

Builds directly on the Milestone 1 knowledge base (`docs/knowledge_base.md`) —
nothing in Milestone 1 was modified except two additive integrations noted
below. This milestone adds grounded, streaming question-answering over the
documents already indexed.

## Pipeline (every question, no exceptions)

```
question
  │
  ▼
1. Retrieve  — cosine-similarity search over indexed chunks (unchanged
               Milestone 1 vector_store.similarity_search), top 20 candidates
  │
  ▼
2. Rerank    — local cross-encoder (Xenova/ms-marco-MiniLM-L-6-v2) scores
               each candidate against the question; keep top 5
  │
  ▼
3. Confidence gate — sigmoid-normalize the best reranked score. Below
               ASSISTANT_MIN_CONFIDENCE (default 0.5): return the fixed
               "I could not find sufficient information inside the NOVA
               knowledge base." message and STOP — the LLM is never called.
  │            (this is a deterministic check, not a prompt instruction)
  ▼
4. Generate  — only reached if step 3 passed. Build a prompt containing
               ONLY the 5 retrieved excerpts (each numbered, with its
               source/section/page) + recent conversation history, and
               stream the answer through the existing LLM gateway
               (app/services/ai/gateway.py, unmodified).
```

If no LLM provider is configured (no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/etc.
— the default state of this deployment), step 4 falls back to streaming the
retrieved excerpts back verbatim, clearly labeled as such. **This is
deliberate**: the assistant never fabricates an answer — with no model
configured, it shows you exactly what it would have grounded an answer in,
instead of guessing.

## What "no hallucination" actually means here

Two independent layers, not one:

1. **The confidence gate (deterministic, always on)** — guarantees the LLM is
   *physically never called* unless retrieval found something plausibly
   relevant. This is the one part of the "do not hallucinate" requirement
   that's fully guaranteed, because it doesn't depend on the LLM behaving.
2. **Closed-context prompting (best-effort, only matters once an LLM is
   configured)** — the system prompt (`app/services/assistant/prompts.py`)
   instructs the model to answer only from the numbered excerpts and to cite
   them. This measurably reduces hallucination but, like any LLM prompting
   technique, **cannot be mathematically guaranteed** the way layer 1 can —
   an LLM can still occasionally elaborate beyond its context. Every answer's
   citations are shown precisely so a human can verify what was actually
   retrieved versus what the model said.

## Response contents

Every turn's SSE stream carries, in order: a `retrieval` event (citations,
confidence, retrieved count — sent before any generation), then `token`
events (or a terminal `insufficient_context` event instead, with none of the
`token` events at all), then a final `done` event (confidence, retrieved
count, total latency). Each citation includes: source filename, page number
(PDFs only), section, similarity score (cosine — same metric Milestone 1's
search uses), rerank score, and the full excerpt text — the "expandable
citations" in the UI show/hide that excerpt on click.

## Conversation history

Kept **client-side only**, not persisted to the database — the frontend
resends the recent turns with each request
(`ASSISTANT_MAX_HISTORY_TURNS`, default 6, caps how much of it reaches the
prompt). This is a deliberate scope decision for this milestone: it keeps
follow-up questions coherent without adding new conversation/message tables.
Retrieval itself is always re-run fresh against the latest question only
(not the full history) — a known, documented simplification, not a bug.

## Required Milestone 1 integrations (the only changes to prior work)

- `app/middleware/permission_middleware.py`: added `/api/v1/assistant/chat`
  to the existing `READ_ONLY_QUERY_PATH_PREFIXES` allowlist (already used for
  `/knowledge/search`) — otherwise the coarse blanket rule would 403 the
  Executive/Board role even though it holds `Permission.KNOWLEDGE_READ`.
- Everything else in `app/services/knowledge_base/` is called, unmodified.

## RBAC

Identical to Milestone 1's search access — `Permission.KNOWLEDGE_READ`
(Security Analyst, Security Manager, Administrator, Executive/Board). No new
permission was introduced: asking the assistant a question is a read of the
knowledge base, not a curation action.

## Configuration

```
ASSISTANT_RERANK_MODEL=Xenova/ms-marco-MiniLM-L-6-v2
ASSISTANT_RERANK_CACHE_DIR=data/rerank_cache
ASSISTANT_RETRIEVAL_CANDIDATES=20
ASSISTANT_TOP_K=5
ASSISTANT_MIN_CONFIDENCE=0.5
ASSISTANT_MAX_HISTORY_TURNS=6
ASSISTANT_MAX_TOKENS=1024
ASSISTANT_TEMPERATURE=0.2
```

To get real generated answers instead of the extractive fallback, configure
any one existing AI provider (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GEMINI_API_KEY`, or `OLLAMA_MODEL`/`VLLM_MODEL` for a local model) — no
assistant-specific configuration needed for that part, it reuses
`app/services/ai/gateway.py` exactly as-is.
