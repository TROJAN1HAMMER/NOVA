# NOVA Implementation Plan: Closed-Loop Patent-Defensible Core

> **Goal**: Transform NOVA into a closed-loop, confidence-calibrated, security-integrated, and self-healing AI platform.

---

## Architecture Flow Target

```
INPUT QUERY
     │
     ▼
STAGE 0 FAQ FAST PATH (<1ms) ──────────[Hit]──────────► INSTANT AXIOM RESPONSE
     │
   [Miss]
     │
     ▼
UNIFIED RETRIEVAL & FUSION
 ├── Knowledge Chunks (Dense + BM25)
 └── Security Findings (pgvector Co-Indexed + Cross-Scanner Boost)
     │
     ▼
8-VECTOR DYNAMIC CONFIDENCE CALIBRATOR (Platt Scaling)
 ├── C_retrieval (Reranker logit)
 ├── C_agreement (Pairwise semantic similarity)
 ├── C_citation (Claim-level source overlap)
 ├── C_reasoning (Signal completeness)
 ├── C_freshness (Exponential time-decay)
 ├── C_hallucination_risk (Support gap)
 ├── C_source_reliability (Metadata weighting)
 └── C_user_feedback (Stored historical signal)
     │
     ▼
RISK-AWARE RESPONSE GATE
 ├── High Trust / Low Risk ──► Grounded Response
 ├── High Risk / Medium Trust ──► Multi-Evidence Enforced Response
 └── Low Trust ──► Abstain / Fallback / Refuse Unsupported Claims
     │
     ▼
OUTCOME & FAILURE MONITORING
     │
     ▼
OUTER-LOOP HDBSCAN SELF-HEALING (Celery Background Task)
 ├── Failure Log Clustering
 ├── Candidate FAQ Rule Generation (DRAFT)
 ├── Semantic Validation Gate
 └── Production Promotion & Automated Degradation Rollback
```

---

## Phase Breakdown & Tasks

### Phase 1: Dynamic 8-Dimensional Confidence Engine (P0-1)
- **Files**: `backend/app/services/search_analytics/calibrator.py`, `backend/app/services/assistant/assistant_service.py`, `backend/app/services/executive_intelligence/executive_intelligence_service.py`.
- **Tasks**:
  - Implement real-time calculations for all 8 vector dimensions in `calibrator.py`:
    - `C_retrieval`: Normalized reranker score.
    - `C_agreement`: Mean pairwise cosine similarity across top-$K$ retrieved evidence items.
    - `C_citation`: Ratio of generated answer claims grounded in retrieved text.
    - `C_reasoning`: Structurally derived evidence support completeness.
    - `C_freshness`: Exponential decay $e^{-\lambda \cdot \text{age\_days}}$.
    - `C_hallucination_risk`: $1.0 - \text{mean}(C_{retrieval}, C_{agreement})$.
    - `C_source_reliability`: Metadata weighted average (Official/Security Finding = 0.95, User Doc = 0.85, External Web = 0.70).
    - `C_user_feedback`: Stored thumbs-up/down score ratio or neutral prior (0.50).
  - Update `assistant_service.py` and `executive_intelligence_service.py` to pass dynamic values instead of default constants.

### Phase 2: Security Findings Vectorization & Co-Indexing (P0-2)
- **Files**: `backend/app/models/finding.py`, `backend/app/services/scanning/aggregator.py`, `backend/app/services/knowledge_service.py`, `backend/app/services/finding_service.py`.
- **Tasks**:
  - Implement a canonical text representation generator for `Finding` rows.
  - Co-index findings into `pgvector` / `knowledge_vectors` so they can be retrieved semantically by query embeddings (`BAAI/bge-small-en-v1.5`).

### Phase 3: Unified Evidence Representation & Cross-Scanner Confidence (P0-2.1)
- **Files**: `backend/app/services/assistant/evidence_fusion.py` (New), `backend/app/scanners/registry.py`, `backend/app/services/scanning/aggregator.py`.
- **Tasks**:
  - Create `UnifiedEvidenceItem` dataclass supporting `knowledge` and `security_finding` sources with explicit provenance metadata.
  - Implement independent cross-scanner confidence boosting:
    $$C_{\text{finding}} = 1.0 - \prod_{i=1}^N (1.0 - c_i)$$

### Phase 4: Hybrid Security + Knowledge Retrieval & Security-Aware Querying (P0-2.2)
- **Files**: `backend/app/services/assistant/assistant_service.py`, `backend/app/services/knowledge_service.py`.
- **Tasks**:
  - Update search pipeline to perform dual retrieval (documents + findings) and fuse them via `evidence_fusion.py`.
  - Implement security-aware query expansion for CVE/CWE and remediation queries.

### Phase 5: TrustGate & Risk-Aware Response Control (P0-2.3 & P1)
- **Files**: `backend/app/services/assistant/assistant_service.py`, `backend/app/services/assistant/prompts.py`.
- **Tasks**:
  - Enforce decision gating (`GENERATE`, `GENERATE_WITH_WARNING`, `ABSTAIN`, `FALLBACK_WEB`).
  - Vary evidence & citation strictness based on Banking Risk Score (BRS).

### Phase 6: Automated Outer-Loop Self-Healing Celery Worker (P1)
- **Files**: `backend/app/tasks/knowledge_health_tasks.py`, `backend/app/services/faq_service.py`, `backend/app/services/faq/gap_clustering.py` (New).
- **Tasks**:
  - Implement automated HDBSCAN density clustering on unresolved query logs (`search_analytics_logs`).
  - Auto-generate candidate FAQ rules in `DRAFT` state with evidence links.

### Phase 7: Candidate Validation, Promotion & Automated Rollback (P1)
- **Files**: `backend/app/services/faq_service.py`, `backend/app/models/faq_rule.py`.
- **Tasks**:
  - Add semantic validation gate checking candidate answer against evidence before promotion.
  - Add degradation tracking (`hit_count`, `fallback_rate`, `user_feedback`) and automated rollback to `ROLLED_BACK` if performance drops.

### Phase 8: Risk-Aware Policy Metrics & Evolution API (P1)
- **Files**: `backend/app/services/faq_service.py`, `backend/app/api/v1/endpoints/faq.py`.
- **Tasks**:
  - Expose self-healing & evolution metrics (`unresolved_count`, `draft_count`, `active_count`, `rolled_back_count`, `stage_0_hit_rate`).

### Phase 9: Evaluation & Ablation Suite (P1)
- **Files**: `backend/scripts/evaluate_nova_core.py`, `backend/tests/test_nova_core_evaluation.py`.
- **Tasks**:
  - Build non-stub, executable evaluation script calculating real Precision, Recall, MRR, ECE, Brier score, and ablation benchmark comparisons.

### Phase 10: UI Exposure & Comprehensive Architecture Documentation
- **Files**: `frontend/src/pages/KnowledgeEvolutionPage.tsx`, `frontend/src/components/assistant/`, `NOVA_TECHNICAL_ARCHITECTURE.md`, `NOVA_CONFIDENCE_ENGINE.md`, `NOVA_SECURITY_EVIDENCE.md`, `NOVA_SELF_HEALING.md`, `NOVA_EVALUATION.md`, `NOVA_IMPLEMENTATION_STATUS.md`.
- **Tasks**:
  - Expose confidence breakdown, provenance, and self-healing candidate/rollback controls in UI.
  - Write detailed technical documentation files detailing implemented mechanics.

---

## Verification Plan

- Run unit & integration tests after every phase via `pytest`.
- Run `backend/scripts/evaluate_nova_core.py` to calculate real empirical metrics.
- Ensure all existing routes (`/scans`, `/admin/users`, `/executive`, etc.) remain fully operational without regressions.
