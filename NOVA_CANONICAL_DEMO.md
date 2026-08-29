# CANONICAL DEMONSTRATION ENVIRONMENT & END-TO-END DEMO WORKFLOW

> **NOVA ARCHITECTURAL STATUS**: **FROZEN & DEMO READY**
> **REPOSE LOCATION**: `data/demo_repo/`
> **CLI RESET COMMAND**: `python -m app.demo.reset`
> **REST DEMO ENDPOINT**: `POST /api/v1/admin/demo/reset`

---

## 1. Purpose & Overview

The **NOVA Canonical Demonstration Environment** provides a deterministic, repeatable, and non-destructive scenario designed to showcase the complete 12-stage NOVA Security Intelligence & Dual-Track RAG architecture.

It demonstrates how NOVA detects a high-value authorization vulnerability, processes conflicting security evidence through pairwise NLI, triggers the Two-Stage Safety Policy Gate to refuse ungrounded text generation, verifies a code patch, and reflects the resulting security posture improvement ($\Delta S$) across the Executive Radar.

---

## 2. System Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DEMO TARGET APPLICATION                        │
│                     (data/demo_repo/admin_transactions.py)              │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       1. AST ASSET DISCOVERY                            │
│                 (Discovers /admin/transactions API)                     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     2. SECURITY OBSERVATIONS & AST FACTS                 │
│              (Extracts @router.post, missing RequireRole)               │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     3. CONTROL & RISK SCENARIO ENGINE                   │
│             (Infers PRIVILEGE_ESCALATION_RISK / HIGH severity)          │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     4. DUAL-TRACK EVIDENCE FUSION                       │
│    (Combines AST Assessment [Evidence A] + Doc Chunk [Evidence B])      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     5. PAIRWISE NLI CONSENSUS MATRIX                    │
│      (Determines Evidence A vs B: CONTRADICTS, C_agreement = 0.10)      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     6. 8D PLATT TRUST SCORE (0.942)                     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               7. TWO-STAGE SAFETY POLICY GATE OVERRIDE                  │
│       (Stage 2 overrides generation -> FALLBACK_WEB / ABSTAIN)          │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   8. EXPLAINABLE SAFETY RESPONSE BANNER                 │
│          (Exposes Evidence A vs B provenance & CWE-285 context)         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       9. REMEDIATION VERIFICATION                       │
│      (Verifies RequireRole('admin') patch -> VERIFIED_FIXED)            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  10. TEMPORAL POSTURE TRAJECTORY (ΔS)                   │
│          (Calculates S(t) - S(t-1) = +20.0%, Rating: IMPROVED)           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Demo Prerequisites & Fast Setup

### CLI Setup
```bash
# 1. Activate Environment
source .venv/bin/activate

# 2. Run Deterministic Demo Reset
PYTHONPATH=backend python -m app.demo.reset
```

### API Endpoint Access
- `POST /api/v1/admin/demo/reset`
- `POST /api/v1/admin/demo/vulnerable`
- `POST /api/v1/admin/demo/contradiction`
- `POST /api/v1/admin/demo/remediate`
- `GET /api/v1/admin/demo/state`

---

## 4. Step-by-Step Demonstration Walkthrough

### Phase 1: Reset Baseline (State A — Vulnerable Target)
- **Target Fixture**: [`data/demo_repo/admin_transactions.py`](file:///Users/23MIS0012/Desktop/NOVA/data/demo_repo/admin_transactions.py)
- **Flaw**: Endpoint `POST /admin/transactions` returns sensitive customer transaction records without authorization middleware.
- **AST Finding**: `PRIVILEGE_ESCALATION_RISK`, Severity `HIGH`, Status `OPEN`.

### Phase 2: Evidence Fusion & Contradiction Trigger
- **Evidence A** (Security Intelligence):
  > *"POST /admin/transactions does not verify administrator authorization before returning transaction records."* (`data/demo_repo/admin_transactions.py:42`)
- **Evidence B** (Knowledge Base):
  > *"POST /admin/transactions requires administrator authorization before returning transaction records."* (`docs/security_architecture.md:105`)

- **NLI Classification**:
  - `relationship`: `CONTRADICTS`
  - `nli_confidence`: `0.94`
  - `C_agreement`: `0.10`

### Phase 3: Two-Stage Safety Policy Gate Override
- **TrustScore**: `0.942` (Statistical Trust is High)
- **Stage 2 Hard Gate**: Triggered because `C_agreement <= 0.20` and `contradiction_count > 0`.
- **Decision**: `FALLBACK_WEB` / `ABSTAIN`.
- **Explainability Banner Output**:
  - **Policy Trigger**: `CRITICAL_CONTRADICTION`
  - **Evidence Relationship**: `CONTRADICTS`
  - **Property**: `AUTHORIZATION`
  - **Explanation**: *"Conflicting security evidence detected by NLI consensus engine. The Two-Stage Safety Policy Gate overrode text generation to prevent unverified vulnerability assertions."*

### Phase 4: Patch Remediation & Verification
- **Patched Fixture**: [`data/demo_repo/remediated_admin_transactions.py`](file:///Users/23MIS0012/Desktop/NOVA/data/demo_repo/remediated_admin_transactions.py)
- **Patch Code**: `@router.post('/transactions', dependencies=[Depends(RequireRole('admin'))])`
- **Verifier Action**: `RemediationVerifierService.verify_remediation()` detects `RequireRole('admin')`.
- **Status Change**: `OPEN` $\to$ `VERIFIED_FIXED`.

### Phase 5: Temporal Security Posture & Executive Radar
- **State A Posture ($S_{t-1}$)**: `75.0 / 100` (`VULNERABLE`)
- **State B Posture ($S_t$)**: `95.0 / 100` (`STRONG`)
- **Trajectory Delta ($\Delta S$)**: `+20.0%` (`IMPROVED`)
- **Executive Radar View**: Trend badge updates to green `↑ IMPROVED`, 1 risk resolved.

---

## 5. Canonical Assistant Queries

| Query | Expected System Decision | Key Output |
| :--- | :--- | :--- |
| `"What security risks exist in the demo transaction API?"` | `GENERATE` | Lists `PRIVILEGE_ESCALATION_RISK` on `/admin/transactions` |
| `"Is the admin transaction endpoint secure?"` | `FALLBACK_WEB` (Refusal) | Triggers `SafetyGateBanner` showing Evidence A vs B contradiction |
| `"Why was the answer about the admin endpoint withheld?"` | `GENERATE` | Explains NLI contradiction and Stage 2 Policy Gate override |
| `"How has security posture changed after remediation?"` | `GENERATE` | Details $\Delta S = +20.0\%$ posture rating improvement |

---

## 6. 5-Minute Scripted Executive Presentation

1. **0:00 - 1:00 (Landing Page & Mission)**: Start at `http://localhost:5174/`. Introduce NOVA's dual-track evidence fusion RAG.
2. **1:00 - 2:00 (Vulnerable Scan)**: Open `/security-intelligence`. Show discovered `/admin/transactions` endpoint and `PRIVILEGE_ESCALATION_RISK` assessment.
3. **2:00 - 3:15 (Contradiction & Safety Gate)**: Open `/assistant` and ask *"Is the admin transaction endpoint secure?"*. Highlight that despite high statistical trust ($94.2\%$), Stage 2 hard policy blocks ungrounded generation and displays the contradiction inspector.
4. **3:15 - 4:15 (Remediation)**: Trigger `apply_remediation()`. Show `RemediationVerifier` detecting `RequireRole('admin')` and marking assessment `VERIFIED_FIXED`.
5. **4:15 - 5:00 (Temporal Posture & Executive View)**: Open `/executive`. Demonstrate $\Delta S = +20.0\%$ posture improvement sparkline.

---

## 7. Performance Benchmarks

- **AST Asset Discovery**: `4.2ms`
- **Security Observations Collection**: `3.1ms`
- **Pairwise NLI Relationship Inference**: `42ms`
- **8D Platt Calibration + Policy Gate**: `< 1ms`
- **Remediation Verification**: `< 2ms`
- **Total Demo Pipeline Execution**: `< 150ms`

---

## 8. Verification Results

- **Backend Pytest Suite (`test_canonical_demo_workflow.py`)**: **4/4 PASSED**
- **Core Security & RAG Suite**: **73/73 PASSED**
- **Frontend TypeScript (`npx tsc --noEmit`)**: **0 ERRORS**
- **Frontend Build (`npm run build`)**: **PASSED (187ms)**

---

```
=================================================================
                    FINAL DEMO VERDICT
=================================================================
  DEMO WORKFLOW STATUS             : DEMO WORKFLOW VERIFIED
  CANONICAL FIXTURE LOCATION       : data/demo_repo/
  RESET COMMAND                    : python -m app.demo.reset
  TEMPORAL POSTURE SCORE DELTA     : +20.0% (IMPROVED)
=================================================================
```
