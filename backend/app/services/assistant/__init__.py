"""
NOVA — AI Assistant (RAG Milestone 2)

Grounded question-answering over the knowledge base built in Milestone 1
(app/services/knowledge_base/). Pipeline for every question:

  1. Retrieve candidate chunks by cosine similarity (reuses
     knowledge_base.vector_store.similarity_search unchanged).
  2. Rerank them with a local cross-encoder (rerank_manager.py) — a
     second-stage precision pass distinct from the first-stage vector
     search, the same two-stage retrieve-then-rerank shape any serious
     RAG pipeline uses.
  3. Deterministically decide whether the best match is confident enough
     to answer from (assistant_service.py) — below the configured
     threshold, the fixed "could not find sufficient information" message
     is returned and the LLM is never called at all. This is what makes
     "never answer from model memory if nothing relevant is retrieved" an
     enforced property rather than a prompting request.
  4. Only if sufficient: build a closed-context prompt containing ONLY the
     retrieved excerpts and stream the answer through the existing LLM
     gateway (app/services/ai/gateway.py) — unmodified from Milestone 1/
     earlier work, just a new caller.

Modules:
  rerank_manager.py    — local ONNX cross-encoder wrapper (mirrors
                         knowledge_base/embedding_manager.py's pattern).
  prompts.py           — the closed-context system prompt.
  assistant_service.py — orchestrates retrieval, reranking, the
                         confidence gate, and answer streaming; the only
                         module app/api/v1/endpoints/assistant.py calls.
"""
