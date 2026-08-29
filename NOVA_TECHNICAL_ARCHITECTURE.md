# NOVA Technical Architecture Specification

## Integrated Core Architecture

NOVA (Neural Orchestrated Vector Assistant) integrates multi-source vector retrieval, parallel SAST/dependency scanning, multi-dimensional Platt-scaled trust score calibration, and outer-loop self-healing gap detection into a unified evidence fusion framework.

```
                               USER QUERY
                                    │
                            QUERY ANALYSIS
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
             KNOWLEDGE EVIDENCE             SECURITY EVIDENCE
          (pgvector Vector Search)       (SQL Finding Search)
                    │                               │
                    └───────────────┬───────────────┘
                                    │
                             EVIDENCE FUSION
                     (Deduplication & Provenance)
                                    │
                                RERANKING
                        (Cross-Encoder Reranker)
                                    │
                         8D DYNAMIC TRUST ENGINE
                      (Platt-Scaled Logistic logit)
                                    │
                              DECISION GATE
                       [GENERATE | FALLBACK | ABSTAIN]
                            ↙               ↘
                        TRUSTED           LOW TRUST
                           │                  │
                          LLM           WEB / ABSTAIN
                           │
                   GROUNDED RESPONSE
                           │
                   OUTCOME / FEEDBACK
                           │
                   SELF-HEALING LOOP
                           ↺
```

## Implemented Execution Flow

1. **Stage 0: Axiom Fast Path** (`faq_service.py`): Matches approved FAQ rules in $<1\text{ms}$ with zero vector latency.
2. **Stage 1: Dual-Track Retrieval**:
   - **Track A (Knowledge)**: Queries `KnowledgeChunk` embeddings in `pgvector` via `vector_store.similarity_search()`.
   - **Track B (Security Findings)**: Queries `findings` SQL table via `finding_service.search_findings_evidence()` for security intent queries.
3. **Stage 2: Unified Evidence Fusion** (`evidence_fusion.py`): Merges knowledge chunks and security findings into `UnifiedEvidenceItem` objects, deduplicating by source ID and location.
4. **Stage 3: Cross-Encoder Reranking** (`rerank_manager.py`): Reranks fused evidence using BGE cross-encoder while preserving rich metadata.
5. **Stage 4: 8-Vector Trust Engine** (`calibrator.py`): Evaluates $P(\text{Correct} \mid \mathbf{C})$ and applies security-aware decision policy thresholds ($\ge 0.75$).
6. **Stage 5: Multi-Provider LLM Streaming**: Formats context block with explicit provenance headers (`[1] (Security Finding [HIGH], Location: app/auth.py:42, CWE: CWE-89)`).
7. **Stage 6: Closed-Loop Self-Healing**: Logs query failures, auto-clusters gaps via Celery Beat, synthesizes draft rules, and monitors degradation for automated rollback.
