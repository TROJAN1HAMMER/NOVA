# NOVA — Explainable Safety Policy Gate Architecture & Data Flow

> **Repository Root**: `/Users/23MIS0012/Desktop/NOVA`
> **Feature**: Explainable Safety Policy Gate / Contradiction Explanation Layer
> **Subsystem**: Dual-Track Assistant RAG, NLI Consensus Matrix & 8D Platt Calibrator
> **Implementation Date**: 2026-08-30
> **Status**: **PROD-READY & PASSED (57/57 Core Suite — 0 Failures)**

---

## 1. Executive Summary

When NOVA's Two-Stage Safety Policy Gate blocks or downgrades an answer (`FALLBACK_WEB` / `ABSTAIN`) due to low trust score or contradictory security assertions ($C_{\text{agreement}} \le 0.20$), the system now exposes a structured, human-readable **Safety Gate Explanation** (`safety_explanation`).

This feature solves the "black-box refusal" problem: users and auditors can inspect *why* the safety policy overrode generation, which specific evidence items conflicted (Evidence A vs Evidence B), their file locations, CWE/CVE identifiers, NLI confidence scores, and affected security properties.

---

## 2. End-to-End Execution Trace & Data Flow

```
                      USER QUERY ("Show auth.py vulnerability status")
                                     │
                                     ▼
                  DUAL-TRACK RETRIEVAL & FUSION ENGINE
             (Track A: Knowledge Docs | Track B: Security Intel)
                                     │
                                     ▼
                     PAIRWISE NLI CONSENSUS ENGINE
                (nli_engine.py -> consensus_engine.py)
                                     │
                                     ▼
                   8D PLATT CALIBRATOR (calibrator.py)
                  - Computes C_vector (8 dimensions)
                  - Calculates Platt TrustScore
                  - Evaluates Two-Stage Policy Gate
                                     │
                                     ▼
                   EXPLAINABLE SAFETY GATE ENRICHMENT
               (confidence_calibrator.build_safety_explanation)
                  - Identifies policy_trigger
                  - Extracts Evidence A vs Evidence B
                  - Maps file_path, line_number, CWE, CVE
                  - Infers security property
                  - Generates concise human explanation
                                     │
                                     ▼
                     ASSISTANT RESPONSE CONTRACT
                 (reasoning_trace.safety_explanation)
                                     │
                                     ▼
                        REACT ASSISTANT UI
                    (SafetyGateBanner in AssistantPage.tsx)
                  - Renders visual status banner
                  - Provides collapsible evidence inspector
```

---

## 3. Decision Explanation Data Schema

The `safety_explanation` payload is attached to `RetrievalResult.reasoning_trace` and transmitted via SSE stream / API:

```json
{
  "decision": "FALLBACK_WEB",
  "reason": "Conflicting security evidence detected.",
  "policy_trigger": "CRITICAL_CONTRADICTION",
  "trust_score": 0.981,
  "agreement_score": 0.10,
  "contradiction_count": 1,
  "supporting_evidence": [
    {
      "source_id": "f-vuln",
      "source_type": "security_finding",
      "filename": "auth.py",
      "file_path": "app/auth.py",
      "line_number": 42,
      "cwe_id": "CWE-89",
      "cve": "CVE-2026-1234",
      "severity": "CRITICAL",
      "security_property": "AUTHORIZATION_AUTHENTICATION",
      "excerpt": "Critical unpatched SQL injection flaw in auth.py line 42 allows full database bypass."
    }
  ],
  "contradicting_evidence": [
    {
      "source_id": "f-vuln",
      "source_type": "security_finding",
      "filename": "auth.py",
      "file_path": "app/auth.py",
      "line_number": 42,
      "cwe_id": "CWE-89",
      "cve": "CVE-2026-1234",
      "severity": "CRITICAL",
      "security_property": "AUTHORIZATION_AUTHENTICATION",
      "excerpt": "Critical unpatched SQL injection flaw in auth.py line 42 allows full database bypass."
    },
    {
      "source_id": "k-sec",
      "source_type": "knowledge_doc",
      "filename": "Secure_Coding_Guide.pdf",
      "file_path": "app/auth.py",
      "line_number": 42,
      "cwe_id": null,
      "cve": null,
      "severity": null,
      "security_property": "AUTHORIZATION_AUTHENTICATION",
      "excerpt": "auth.py line 42 is secure and not vulnerable to SQL injection after complete parameterization."
    }
  ],
  "evidence_relationship": "CONTRADICTS",
  "nli_confidence": 0.91,
  "explanation": "Two evidence items (app/auth.py:42 and app/auth.py:42) assert incompatible security states with NLI confidence 0.91. Although retrieval score (0.95) and source reliability are strong, the safety policy overrides generation because the evidence agreement score (0.10) fell below the contradiction threshold (0.20)."
}
```

---

## 4. Policy Override Triggers

| Policy Trigger | Trigger Condition | Primary Action | Default Human Explanation |
| :--- | :--- | :--- | :--- |
| `CRITICAL_CONTRADICTION` | `contradiction_count > 0` or $C_{\text{agreement}} \le 0.20$ | `FALLBACK_WEB` / `ABSTAIN` | *"Two evidence items assert incompatible security states... safety policy overrides generation."* |
| `SECURITY_QUERY_LOW_CONFIDENCE` | `is_security_query == True` & $\text{TrustScore} < 0.75$ | `FALLBACK_WEB` / `ABSTAIN` | *"Security query evidence confidence fell below required threshold (0.75)."* |
| `LOW_RETRIEVAL_SIMILARITY` | $C_{\text{retrieval}} < 0.35$ | `FALLBACK_WEB` / `ABSTAIN` | *"Vector retrieval similarity was insufficient to ensure evidence grounding."* |
| `CONFIDENCE_THRESHOLD_OVERRIDE` | $\text{TrustScore} < 0.70$ | `FALLBACK_WEB` / `ABSTAIN` | *"Overall trust score was below minimum safety policy threshold (0.70)."* |
| `NORMAL_CONFIRMED` | $\text{TrustScore} \ge \text{Threshold}$ & $C_{\text{agreement}} > 0.20$ | `GENERATE` | *"Answer generated from trusted evidence."* |

---

## 5. Frontend UI Integration

In `frontend/src/pages/AssistantPage.tsx`:
- **Visual Safety Status Banner**: Rendered inside `SafetyGateBanner` component when `message.safetyExplanation` is present.
- **Amber Warning Container**: Displays when `policy_trigger` is `CRITICAL_CONTRADICTION` or when `decision` is `FALLBACK_WEB`.
- **Collapsible Evidence Inspector**: Includes a `<details>` fold out allowing auditors to inspect:
  - Evidence A vs Evidence B side-by-side.
  - Affected `file_path`, `line_number`, `cwe_id`, `cve`, `severity`.
  - Inferred `security_property`.
  - `NLI Confidence`, `Agreement Score`, and `Trust Score`.

---

## 6. Security Considerations & Data Sanitization

1. **Path Protection**: Excerpt strings and filenames are truncated to 200 characters to prevent log clutter or excessive payload size.
2. **XSS Protection**: React automatically sanitizes rendered text nodes inside `SafetyGateBanner` and `CitationList`.
3. **Information Disclosure Control**: Only file paths and evidence excerpts intentionally exposed by `SecurityEvidenceProvider` and `KnowledgeDocument` models are included in the explanation. Secrets and environment variables are strictly excluded.

---

## 7. Verification & Automated Test Results

The dedicated test suite [`backend/tests/test_safety_gate_explainability.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/tests/test_safety_gate_explainability.py) verifies 10 core safety scenarios:

1. `test_1_strong_supporting_evidence_generate`: Verifies `GENERATE` decision and `NORMAL_CONFIRMED` trigger.
2. `test_2_no_evidence_fallback`: Verifies `FALLBACK_WEB` decision and `LOW_RETRIEVAL_SIMILARITY` trigger.
3. `test_3_explicit_contradiction_fallback`: Verifies `CRITICAL_CONTRADICTION` trigger, extracting Evidence A & B IDs (`f-vuln` vs `k-sec`).
4. `test_4_implicit_security_contradiction_fallback`: Verifies implicit contradiction handling and property extraction (`AUTHORIZATION_AUTHENTICATION`).
5. `test_5_mixed_support_and_contradiction_fallback`: Verifies contradiction overrides supporting pairs.
6. `test_6_remediation_guidance_generate`: Verifies remediation guides generate valid answers.
7. `test_7_explanation_contains_correct_evidence_ids`: Verifies correct mapping of document/source IDs.
8. `test_8_explanation_contains_correct_policy_trigger`: Verifies accurate trigger classification.
9. `test_9_existing_assistant_response_remains_compatible`: Verifies backward compatibility of `retrieve_and_orchestrate`.

```
======================= 57 passed, 93 warnings in 1.11s ========================
```
