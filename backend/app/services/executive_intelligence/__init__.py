"""
NOVA — Executive Intelligence (RAG Milestone 4)

Answers leadership-facing questions ("What are our biggest risks?", "What
changed this week?", "What compliance gaps remain?", "What should
leadership prioritize?") grounded in TWO sources, always retrieved before
any generation:

  1. Scan history evidence (evidence_service.py) — deterministic
     aggregation over ScanJob/ScanResult/Repository (portfolio BRS,
     severity totals, top-risk repositories, per-framework compliance,
     week-over-week trend). This is the PRIMARY grounding and is always
     computed, every time, regardless of the question asked — "never
     fabricate statistics" is enforced by never letting the LLM see
     anything BUT these pre-computed numbers; there is no raw scan data
     in the prompt for it to misread or embellish.
  2. Knowledge-base documentation (reusing app/services/knowledge_base/
     and app/services/assistant/rerank_manager.py unmodified) — a
     SECONDARY, supplementary source. Unlike Milestones 2/3, insufficient
     KB relevance does not block an answer here — the evidence snapshot
     alone is always enough to ground a response about scan history. KB
     retrieval only adds supplementary citations when it clears the same
     confidence gate those milestones use.

Modules:
  evidence_service.py             — the deterministic scan-history
                                    aggregation, reused verbatim as the
                                    "evidence" both the API response and
                                    the LLM prompt are built from.
  prompts.py                      — the closed-context system prompt.
  executive_intelligence_service.py — orchestrates evidence + KB
                                    retrieval + generation; the only
                                    module app/api/v1/endpoints/
                                    executive_intelligence.py calls.
  pdf_export.py                   — renders a previously-given answer
                                    (not a fresh recomputation) to PDF.
"""
