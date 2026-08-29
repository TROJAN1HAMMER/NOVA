# NOVA — Security Intelligence Enterprise Architecture Specification

> **Document Type**: Subsystem Integration & Data Flow Architecture  
> **Subsystem**: Independent Security Intelligence Service (`security_intelligence`)

---

## 1. Enterprise End-to-End Data Flow

```
                              ENTERPRISE SYSTEM
                                      │
                                      ▼
                           1. ASSET DISCOVERY ENGINE
                   (Repositories, APIs, Services, Data Stores)
                                      │
                                      ▼
                       2. SECURITY OBSERVATION COLLECTOR
                   (AST Facts, Routes, Boundaries, Secrets)
                                      │
                                      ▼
                        3. SECURITY CONTEXT GRAPH &
                           TRUST BOUNDARY MODELING
                   (Internet -> API -> App -> DB Data Flows)
                                      │
                                      ▼
                       4. SECURITY CONTROL ANALYZER
                (AUTHENTICATION, AUTHORIZATION, VALIDATION)
                                      │
                                      ▼
                         5. RISK SCENARIO ENGINE
                (Exposure + Asset + Control Deficit -> Risk)
                                      │
                                      ▼
                       6. SCENARIO VERIFICATION GATE
               (CANDIDATE -> SUPPORTED -> VERIFIED / DISMISSED)
                                      │
                                      ▼
                        7. SECURITY ASSESSMENT STORE
                 (Evidence Chains, Attack Paths, Remediation)
                                      │
                                      ▼
                      8. SECURITY EVIDENCE PROVIDER
                 (SecurityEvidenceProvider Interface)
                                      │
                                      ▼
                       9. NOVA UNIFIED EVIDENCE FUSION
                    (UnifiedEvidenceItem Integration)
                                      │
                                      ▼
                    10. PAIRWISE NLI RELATIONSHIP ENGINE
                        (SUPPORTS / CONTRADICTS)
                                      │
                                      ▼
                     11. CONSENSUS & 8D TRUST ENGINE
                            (Plated TrustScore)
                                      │
                                      ▼
                      12. TWO-STAGE SAFETY POLICY GATE
                      (GENERATE vs FALLBACK_WEB)
```

---

## 2. Component Responsibility Matrix

| Pipeline Phase | Module | Input Data | Transformation / Computation | Output Product |
| :--- | :--- | :--- | :--- | :--- |
| **Asset Discovery** | `asset_discovery_service.py` | Repository file tree & route configs | AST route scanning & config extraction | Discovered `SecurityIntelAsset` objects |
| **Observation Extraction**| `observation_collector.py` | Code snippets & endpoints | AST decorator & parameter analysis | Structural `SecurityIntelObservation` facts |
| **Context Graph** | `security_context_graph.py` | Observations list | Trust boundary layer mapping | `TrustBoundaryNode` & `DataFlowPath` graph |
| **Control Evaluation** | `control_analyzer.py` | Middleware & decorators | State evaluation (`PRESENT`, `ABSENT`, `PARTIAL`) | `SecurityIntelControl` status records |
| **Risk Inference** | `risk_scenario_engine.py` | Facts + Controls + Graph | Multi-factor contextual inference | `RiskScenarioInference` candidates |
| **Verification Gate** | `scenario_verifier.py` | Candidates + Controls | Evidence verification & confidence scoring | Verified `SecurityIntelAssessment` records |
| **Remediation Check** | `remediation_verifier.py` | Assessment ID + Code patch | AST pattern re-evaluation | `VERIFIED_FIXED` status update |
| **Evidence Provider** | `evidence_provider.py` | Verified Assessments | Schema mapping to `UnifiedEvidenceItem` | Normalized NOVA evidence dicts |
