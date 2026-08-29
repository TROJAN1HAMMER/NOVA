# NOVA — Security Architecture Separation & Boundary Specification

> **Document Type**: Architectural Boundary Analysis  
> **Subsystem**: Independent Security Intelligence Service (`security_intelligence`)  
> **Legacy Subsystem**: Legacy Scanner & Aggregation Framework (`app.services.scanners`, `app.models.finding`)  
> **Isolation Status**: 100% DECOUPLED & VERIFIED (345 Passing Backend Tests)

---

## 1. Architectural Paradigms Comparison

| Paradigm Dimension | Legacy Security Scanner System | New Independent Security Intelligence Service |
| :--- | :--- | :--- |
| **Core Orientation** | **Scanner-centric**: Focuses on tool execution outputs (Bandit, Semgrep, Trivy, ZAP). | **Asset-centric**: Focuses on enterprise application assets, endpoints, services, and databases. |
| **Fundamental Unit** | **Scanner Finding**: Raw vulnerability strings from external tools. | **Security Observation**: Structural facts extracted from code ASTs, routing, and configurations. |
| **Analysis Pipeline** | **Multi-tool aggregation**: Overlap weighting of findings across tools. | **Context & Control Inference**: Synthesizes trust boundaries, data flows, and security controls. |
| **Vulnerability Model** | Pattern match $\to$ Vulnerability record. | Exposure + Asset + Boundary + Operation + Control Deficit $\to$ **Risk Scenario**. |
| **Confidence Scoring** | Tool overlap agreement formula ($1 - \prod (1 - w_k)$). | **Contextual Assessment Confidence**: Evaluates path completeness, control state, and verification strength. |
| **Verification Gate** | Finding created directly upon scan ingestion. | Risk Scenario $\to$ **Verification Engine** (`CANDIDATE` $\to$ `SUPPORTED` $\to$ `VERIFIED`). |
| **Result Representation** | Flat vulnerability list (`findings` table). | **Security Posture & Risk Paths** (`security_intel_assessments` table). |
| **Integration with NOVA** | Legacy SQL term search returning finding rows. | Clean **`SecurityEvidenceProvider`** producing normalized `UnifiedEvidenceItem` objects. |

---

## 2. Structural Separation Matrix

```
                      NOVA ARCHITECTURE BOUNDARY
                                   │
       ┌───────────────────────────┴───────────────────────────┐
       ▼                                                       ▼
LEGACY SCANNER SUBSYSTEM                     INDEPENDENT SECURITY INTELLIGENCE
(UNTOUCHED & ISOLATED)                       (NEW SUBSYSTEM)
• app.models.finding.Finding                 • app.models.security_intelligence.*
• app.models.scan_job.ScanJob               • app.services.security_intelligence.asset_discovery
• app.services.scan_intake                   • app.services.security_intelligence.observation_collector
• app.services.finding_service               • app.services.security_intelligence.security_context_graph
• app.tasks.aggregator_tasks                 • app.services.security_intelligence.control_analyzer
• /api/v1/scans                              • app.services.security_intelligence.risk_scenario_engine
• /api/v1/findings                           • app.services.security_intelligence.scenario_verifier
                                             • app.services.security_intelligence.remediation_verifier
                                             • app.services.security_intelligence.explanation_engine
                                             • app.services.security_intelligence.evidence_provider
                                             • /api/v1/security-intelligence/*
```

---

## 3. Zero-Coupling Code Verification

1. **No Shared Imports**: The `app.services.security_intelligence` package imports 0 modules from `app.services.scanners`, `finding_service`, or `aggregator_tasks`.
2. **No Shared Database Tables**: Stores all data in `security_intel_assets`, `security_intel_observations`, `security_intel_controls`, `security_intel_risk_scenarios`, and `security_intel_assessments`.
3. **Coexistence**: Environment settings allow `LEGACY_SECURITY=true` and `NEW_SECURITY_INTELLIGENCE=true` to operate concurrently without side effects.
