# NOVA PATENT-ORIENTED TECHNICAL EVIDENCE INVENTORY

> **LEGAL DISCLAIMER**: THIS DOCUMENT IS FOR TECHNICAL DOCUMENTATION AND ARCHITECTURAL REVIEW ONLY. IT DOES NOT CONSTITUTE LEGAL OR PATENTABILITY OPINIONS.

---

## 1. Distinctive Implemented Technical Mechanisms

### Mechanism 1: Heterogeneous Knowledge + Security Evidence Representation
- **Implementation**: Unified schema (`UnifiedEvidenceItem`) merging AST code facts, security intel assessments, knowledge base chunks, and FAQ rules into a single vector space and NLI consensus pool.
- **Source Files**: [`app/services/security_intelligence/evidence_provider.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/evidence_provider.py), [`app/services/search_analytics/evidence_fusion.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/search_analytics/evidence_fusion.py).
- **Technical Problem Addressed**: RAG systems typically retrieve only text documents, missing structured AST control and vulnerability context.
- **Observed Behavior**: Allows Assistant queries to retrieve both AST security assessments and natural language documentation simultaneously.
- **Verification Evidence**: `test_evidence_fusion_integration.py` (Passed).
- **Status**: **IMPLEMENTED**

### Mechanism 2: Pairwise NLI Evidence Relationship Matrix ($N \times N$)
- **Implementation**: Directional cross-encoder inference combined with CWE/CVE regex, semantic property matching, and version scope extraction to evaluate `SUPPORTS`, `CONTRADICTS`, `RELATED`, `UNRELATED`.
- **Source Files**: [`app/services/ai/nli_engine.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/ai/nli_engine.py), [`app/services/ai/consensus_engine.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/ai/consensus_engine.py).
- **Technical Problem Addressed**: Standard RAG assumes retrieved chunks reinforce each other, generating confident answers from conflicting documentation.
- **Observed Behavior**: Detects contradictory evidence items and outputs an agreement score ($C_{\text{agreement}}$).
- **Verification Evidence**: `test_nli_consensus.py`, `test_canonical_demo_workflow.py` (Passed).
- **Status**: **IMPLEMENTED**

### Mechanism 3: Two-Stage Safety Policy Gate (Statistical Trust vs Hard Refusal)
- **Implementation**: Decouples continuous 8-Vector Platt scaling trust computation from discrete hard safety policy rules. If $C_{\text{agreement}} \le 0.20$ or `contradiction_count > 0`, Stage 2 forces `FALLBACK_WEB` or `ABSTAIN` refusal regardless of statistical confidence.
- **Source Files**: [`app/services/search_analytics/calibrator.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/search_analytics/calibrator.py), [`app/services/assistant/assistant_service.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/assistant/assistant_service.py).
- **Technical Problem Addressed**: High vector similarity scores (e.g. 0.94) frequently override subtle contradiction signals, causing hallucinations.
- **Observed Behavior**: High TrustScore ($0.942$) is overrode by Stage 2 hard policy gate when Evidence A contradicts Evidence B.
- **Verification Evidence**: `test_safety_gate_explainability.py` (Passed).
- **Status**: **IMPLEMENTED**

### Mechanism 4: Explainable Contradiction Inspection & Provenance
- **Implementation**: Generates structured `safety_explanation` payload detailing Policy Trigger, Evidence A vs Evidence B text excerpts, line numbers, CWE/CVE metadata, and security property context.
- **Source Files**: [`app/services/search_analytics/calibrator.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/search_analytics/calibrator.py).
- **Technical Problem Addressed**: Opaque AI refusals ("I cannot answer this question") provide no actionable technical reasoning to enterprise developers.
- **Observed Behavior**: SSE stream outputs collapsible `SafetyGateBanner` with Evidence A vs Evidence B provenance.
- **Verification Evidence**: `test_safety_gate_explainability.py` (Passed).
- **Status**: **IMPLEMENTED**

### Mechanism 5: Temporal Posture Trajectory ($\Delta S$) as RAG Context
- **Implementation**: Persists posture snapshots in PostgreSQL `security_intel_posture_snapshots` table, computes trajectory delta ($\Delta S = S_t - S_{t-1}$), and exposes posture history via `SecurityEvidenceProvider` to RAG queries.
- **Source Files**: [`app/services/security_intelligence/posture_trend_engine.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/posture_trend_engine.py), [`app/services/security_intelligence/evidence_provider.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/evidence_provider.py).
- **Technical Problem Addressed**: Static security tools evaluate code at a single point in time without tracking historical posture trajectory or risk evolution.
- **Observed Behavior**: Assistant answers queries like *"How has security posture changed?"* using real posture trend evidence items.
- **Verification Evidence**: `test_temporal_posture_engine.py` (Passed).
- **Status**: **IMPLEMENTED**

### Mechanism 6: Remediation Verification Feeding Posture History
- **Implementation**: Re-evaluates updated code snippets via `RemediationVerifierService` to verify security controls (`RequireRole('admin')`), transitions assessment status to `VERIFIED_FIXED`, and triggers posture recalculation.
- **Source Files**: [`app/services/security_intelligence/remediation_verifier.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/remediation_verifier.py), [`app/services/security_intelligence/intelligence_orchestrator.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/intelligence_orchestrator.py).
- **Technical Problem Addressed**: Security findings often remain open indefinitely because security tools lack automated patch verification capabilities.
- **Observed Behavior**: Verifies code patch and transitions posture rating from `VULNERABLE` to `STRONG` ($\Delta S = +20.0\%$).
- **Verification Evidence**: `test_canonical_demo_workflow.py` (Passed).
- **Status**: **IMPLEMENTED**
