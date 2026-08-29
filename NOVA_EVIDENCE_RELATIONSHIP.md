# NOVA — NLI Evidence Relationship Analysis Specification

> **Module**: `app.services.ai.nli_engine`  
> **Status**: OPERATIONAL & VERIFIED (314 Passing Tests)

---

## 1. Contextual Scope & Version-Aware Decision Hierarchy

The **NLI Engine** combines neural cross-encoder joint scoring with version extraction, CVE/CWE scope matching, and security status reasoning:

```
                            EVIDENCE PAIR (A, B)
                                     │
                    1. SCOPE & CVE EXTRACTION
                       (CVE-2026-1234, CWE-89, auth.py)
                                     │
                    2. VERSION & STATUS EXTRACTION
                       (v1.2 vs v1.4, VULNERABLE vs SAFE)
                                     │
               ┌─────────────────────┼─────────────────────┐
               ▼                     ▼                     ▼
        DISTINCT CVEs        DIFFERENT VERSIONS      SAME SCOPE & VERSION
        (CVE-1 vs CVE-2)      (v1.2 vs v1.4)         (v1.2 vs v1.2)
               │                     │                     │
               ▼                     ▼                     ▼
          NOT CONTRADICTORY       REMEDIATION / UPGRADE    OPPOSING STATUS
          (RELATED / UNRELATED)   (RELATED / SUPPORTS)     (CONTRADICTS)
```

---

## 2. Decision Precedence Rules

1. **Rule 1 (Distinct CVEs)**: If evidence pairs refer to distinct CVE identifiers (`CVE-2026-1234` vs `CVE-2026-9999`), they are classified as **`RELATED`** (if domain overlap exists) or **`UNRELATED`**. They are **never** marked as contradictory.
2. **Rule 2 (Version Upgrade / Remediation Path)**: If evidence describes a version upgrade (e.g. `v1.2 vulnerable` vs `v1.4 patched`), it is classified as **`RELATED`** or **`SUPPORTS`** (remediation guidance).
3. **Rule 3 (Opposing Status in Same Scope/Version)**: If both items refer to the same CVE, file path, component, or version and make opposing vulnerability assertions (`VULNERABLE` vs `SAFE`), the pair is classified as **`CONTRADICTS`** (Confidence $\ge 0.90$).
4. **Rule 4 (Remediation Guidance)**: If an item provides fixing instructions (`"to fix"`, `"use parameterized queries"`), it is classified as **`SUPPORTS`**.

---

## 3. Human-Readable Rationale Outputs

```json
{
    "source_evidence_id": "f-101",
    "target_evidence_id": "k-202",
    "relationship": "CONTRADICTS",
    "confidence": 0.94,
    "nli_label": "CONTRADICTION",
    "nli_score": 0.88,
    "reason": "Same component/file version (v1.2) exhibits opposite vulnerability status assertions."
}
```
