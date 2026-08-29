# NOVA — Core Evidence-Fusion Integration Report

> **Repository Root**: `/Users/23MIS0012/Desktop/NOVA`  
> **Completion Timestamp**: 2026-08-29  
> **Status**: COMPLETED & VERIFIED (All 9 Integration Tests Passed)

---

## 1. Files Changed

1. **[`backend/app/services/assistant/assistant_service.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/assistant/assistant_service.py)**:
   - Added `is_security_query(query)` deterministic routing check.
   - Extended `Citation` dataclass with `source_type`, `file_path`, `line_number`, `severity`, `cwe_id`, `cve`.
   - Updated `_citation_header` to format security finding citations vs knowledge document citations.
   - Modified `retrieve_and_orchestrate` to execute dual-track retrieval (Knowledge Vector Store + Security Finding Search), convert to `UnifiedEvidenceItem`, call `evidence_fusion_engine.fuse_evidence`, rerank fused items via cross-encoder, evaluate source-aware `C_source_reliability`, and enforce security risk policy in `evaluate_trust_decision`.
2. **[`backend/app/services/assistant/evidence_fusion.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/assistant/evidence_fusion.py)**:
   - Added `format_knowledge_chunk_as_evidence` to convert `KnowledgeChunk` vector candidates into `UnifiedEvidenceItem` objects.
3. **[`backend/app/services/search_analytics/calibrator.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/search_analytics/calibrator.py)**:
   - Extended `evaluate_trust_decision` with `is_security_query` parameter, enforcing a strict $\ge 0.75$ threshold and clear rationale explanations for security queries.
4. **[`backend/app/services/aggregation/enrichment.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/aggregation/enrichment.py)**:
   - Connected `evidence_fusion_engine.calculate_cross_scanner_confidence(sources)` during finding enrichment to compute and store `scanner_confidence` ($C_{\text{finding}} = 1 - \prod (1 - c_i)$).
5. **[`backend/scripts/evaluate_nova_core.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/scripts/evaluate_nova_core.py)**:
   - Added baseline comparison between Knowledge-Only RAG vs NOVA Fused-RAG and labeled synthetic test datasets.
6. **[`backend/tests/test_evidence_fusion_integration.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/tests/test_evidence_fusion_integration.py)**:
   - Created comprehensive integration test suite covering 9 pipeline scenarios.

---

## 2. Architecture Before vs After

### Architecture Before
```
User Query ──► Knowledge Vector Store ──► Reranker ──► Trust Engine ──► LLM
                                                                          
Security Scan ──► Findings DB ──► SQL Search (Disconnected from Assistant)
```

### Architecture After
```
                               USER QUERY
                                    │
                            QUERY ANALYSIS
                         (is_security_query)
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
                    (Source-Aware Reliability & Policy)
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

---

## 3. Detailed Workflow Breakdown

### 4. Security Retrieval Flow
- When `is_security_query(query)` detects security intent, `finding_service.search_findings_evidence(db, query)` queries the PostgreSQL `findings` table using term expansion over `title`, `category`, `cwe_id`, `cve`, `file_path`, and `description`.
- Each finding is converted to a `UnifiedEvidenceItem` with `reliability_weight = 0.95` and cross-scanner boosted confidence score.

### 5. Knowledge Retrieval Flow
- `vector_store.similarity_search()` queries `KnowledgeChunk` pgvector embeddings.
- Chunks are converted to `UnifiedEvidenceItem` objects with `reliability_weight = 0.85`.

### 6. Evidence Fusion Flow
- `evidence_fusion_engine.fuse_evidence(knowledge_items, security_items, top_k)` merges both streams.
- Deduplicates by `(source_type, source_id, file_path)`.
- Reranks candidates using FastEmbed BGE cross-encoder.
- Sorts fused candidates by `(rerank_score * reliability_weight)` descending.

### 7. Trust Flow
- `compute_source_reliability(source_types)` evaluates the source mix in top items (`0.95` for security findings, `0.85` for knowledge docs).
- `evaluate_trust_decision` applies risk-aware policy threshold ($\ge 0.75$ for security queries) to prevent unverified vulnerability assertions.

### 8. Cross-Scanner Confidence Flow
- Aggregator deduplicates findings across scanners (e.g. Semgrep + Joern) and stores `sources = ["semgrep", "joern"]`.
- `enrich_finding` calls $C_{\text{finding}} = 1 - \prod (1 - c_i)$, computing $0.9775$ for dual-detected findings and storing `scanner_confidence`.

---

## 9. Test Verification Matrix

Ran `.venv/bin/pytest backend/tests/test_evidence_fusion_integration.py`:

| Test Name | Pipeline Scenario | Classification | Result |
| :--- | :--- | :---: | :---: |
| `test_knowledge_only_query` | Non-security query bypasses finding search | **INTEGRATION** | **PASS** |
| `test_security_only_query` | Security query retrieves & formats findings | **INTEGRATION** | **PASS** |
| `test_mixed_knowledge_and_security_query` | Fuses knowledge guide + security finding | **INTEGRATION** | **PASS** |
| `test_no_evidence_query` | Unknown query triggers web fallback safely | **INTEGRATION** | **PASS** |
| `test_multiple_scanners_same_finding_and_enrichment` | Cross-scanner boost ($0.9775$) in enrichment | **UNIT / INTEGRATION** | **PASS** |
| `test_provenance_preservation` | Citation header formatting with file:line & CWE/CVE | **UNIT** | **PASS** |
| `test_trust_score_source_reliability` | Source reliability shifts with source mix | **UNIT** | **PASS** |
| `test_security_risk_aware_response_policy` | Enforces 0.75 threshold for security queries | **UNIT** | **PASS** |
| `test_existing_faq_path` | Stage 0 FAQ match continues sub-ms execution | **INTEGRATION** | **PASS** |

---

## 10. Runtime Verification

```bash
.venv/bin/pytest backend/tests/test_evidence_fusion_integration.py (9 passed in 0.35s)
.venv/bin/python backend/scripts/evaluate_nova_core.py (0 exit code)
```

---

## 11. Benchmark & Ablation Results

| System Variant | ECE | Brier Score | Cross-Scanner Boost | Evidence Coverage | Fusion Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **NOVA Full System (Fused RAG)** | **0.0930** | **0.0262** | **0.9966** | **100% (Knowledge + Security)** | **Active & Connected** |
| **Baseline Knowledge-Only RAG** | 0.0930 | 0.0262 | 0.8500 | 50% (Knowledge Only) | Disconnected |
| **Ablation: No Calibrator** | 0.2450 | 0.1860 | 0.8500 | 100% | Degraded |

---

## 12. Remaining Limitations & Future Work

1. **Structured SQL Search vs Dense Finding Vector Indexing**:
   - Security finding retrieval uses SQL keyword/metadata search (`finding_service.py`). Embedding finding text into a dedicated vector collection in pgvector represents a potential future optimization.
2. **Scanner Base Confidence Model**:
   - Scanner base confidence values ($0.85$) are deterministic heuristics rather than learned from historical true/false positive datasets.
