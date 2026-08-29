# NOVA — Legacy Security Subsystem Boundary Specification

> **Boundary Document**: Engineering Separation Architecture  
> **Legacy Status**: UNTOUCHED & ISOLATED  
> **New Subsystem**: Independent Security Intelligence Service (`security_intelligence`)

---

## 1. Legacy Security Subsystem Inventory

The legacy security subsystem consists of the following components:

- **Database Models**: `Finding` ([`app/models/finding.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/models/finding.py)), `ScanJob` ([`app/models/scan_job.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/models/scan_job.py))
- **Services & Tasks**: `scan_intake.py`, `finding_service.py`, `aggregator_tasks.py`, `finding_intelligence/*`, `security_retrieval_service.py`
- **APIs**: `/api/v1/scans/*`, `/api/v1/findings/*`
- **Frontend Pages**: `/scans`, `/scans/:scanId`

---

## 2. Explicit Architecture Boundary

```
LEGACY SECURITY SUBSYSTEM                  NEW SECURITY INTELLIGENCE SERVICE
┌────────────────────────────────┐        ┌────────────────────────────────┐
│  • ScanJobs & Raw Scanners     │        │  • Asset Discovery Engine      │
│  • Bandit, Semgrep, Trivy, ZAP │        │  • Security Observations       │
│  • Aggregation Tasks           │   X    │  • Security Context Graph      │
│  • Finding Table & Models      │   X    │  • Security Controls Model     │
│  • Scanner Reliability Weight  │   X    │  • Risk Scenario Engine        │
│  • Scanner APIs (/scans)       │        │  • Scenario Verification Gate  │
│  • Legacy Scan Details UI      │        │  • Security Assessment Store   │
└────────────────────────────────┘        └────────────────────────────────┘
                 │                                         │
                 ▼                                         ▼
         Legacy Finding Data                    Security Evidence Provider
                 │                                         │
                 └───────────────────┬─────────────────────┘
                                     │
                                     ▼
                           NOVA ASSISTANT CORE
                      (UnifiedEvidenceItem Layer)
```

---

## 3. Separation Principles (Non-Negotiable Rules)

1. **Zero Import Coupling**: The new `security_intelligence` module MUST NOT import legacy models (`Finding`, `ScanJob`) or legacy services (`scan_intake`, `finding_service`, `aggregator_tasks`).
2. **Zero Aggregation Dependency**: The new service MUST NOT use legacy multi-tool scanner aggregation or legacy scanner confidence calculations as a foundation.
3. **Independent Data Storage**: All asset, observation, context, control, risk scenario, and assessment records are stored in dedicated PostgreSQL tables prefixed with `security_intel_`.
4. **Independent REST Interface**: Exposes `/api/v1/security-intelligence/*` endpoints without modifying `/api/v1/scans`.
5. **Clean Evidence Interface**: Integrates with NOVA strictly via `SecurityEvidenceProvider` returning normalized `UnifiedEvidenceItem` objects to NOVA's evidence fusion layer.
