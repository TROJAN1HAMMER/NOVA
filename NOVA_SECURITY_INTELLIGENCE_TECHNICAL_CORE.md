# NOVA — Security Intelligence Technical Core Specification

> **Document Type**: Technical Implementation Reference  
> **Subsystem**: Independent Security Intelligence Service (`security_intelligence`)  
> **Notice**: Documents technical code mechanisms. Contains 0 legal novelty or patentability assertions.

---

## 1. Subsystem Architecture Overview

The Security Intelligence Service is an asset-centric, observation-driven security evaluation engine. It operates independently of external static/dynamic security scanner tools by extracting structural code facts, establishing trust boundary data flows, evaluating security control states, inferring multi-factor risk scenarios, verifying scenarios through an evidence gate, and providing normalized security evidence to NOVA's Assistant RAG framework.

---

## 2. Implemented Core Mechanisms

### 1. Independent Asset Discovery Engine ([`asset_discovery_service.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/asset_discovery_service.py))
- **Function**: Scans repository structures to construct an `AssetRegistry`.
- **Entity**: `SecurityIntelAsset` (`asset_name`, `asset_type`, `criticality`, `location`, `attributes`).
- **Asset Types**: `APPLICATION`, `API`, `ENDPOINT`, `DATABASE`, `SERVICE`, `MODULE`.

### 2. Structural Security Observation Collector ([`observation_collector.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/observation_collector.py))
- **Function**: Extracts non-vulnerability security facts from ASTs and configuration files.
- **Observation Types**: `PUBLIC_ENDPOINT`, `USER_CONTROLLED_INPUT`, `DATABASE_ACCESS`, `SECRET_USAGE`, `AUTHENTICATION_BOUNDARY`, `AUTHORIZATION_BOUNDARY`, `PRIVILEGED_OPERATION`, `TRUST_BOUNDARY`.

### 3. Security Context & Trust Boundary Modeling ([`security_context_graph.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/security_context_graph.py))
- **Function**: Maps application layers (`INTERNET` $\to$ `PUBLIC_API` $\to$ `APPLICATION` $\to$ `DATABASE`) and traces data flow paths crossing trust boundaries.

### 4. Independent Security Control Analyzer ([`control_analyzer.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/control_analyzer.py))
- **Function**: Evaluates security control presence and effectiveness.
- **States**: `PRESENT`, `ABSENT`, `PARTIAL`, `BYPASSED`, `UNKNOWN`.
- **Control Types**: `AUTHENTICATION`, `AUTHORIZATION`, `INPUT_VALIDATION`, `ENCRYPTION`, `SECRET_MANAGEMENT`.

### 5. Multi-Factor Risk Scenario Engine ([`risk_scenario_engine.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/risk_scenario_engine.py))
- **Function**: Synthesizes facts to infer risk scenarios:
  $$\text{Exposure Signal} + \text{Asset Context} + \text{Trust Boundary Crossing} + \text{Control Deficit} \implies \text{Risk Scenario}$$
- **Scenario Types**: `PRIVILEGE_ESCALATION_RISK`, `UNPROTECTED_ENDPOINT_RISK`, `SECRET_EXPOSURE_RISK`.

### 6. Contextual Scenario Verification Gate ([`scenario_verifier.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/scenario_verifier.py))
- **Function**: Evaluates candidate scenarios against verified controls to produce `SecurityIntelAssessment` records.
- **Verification States**: `CANDIDATE` $\to$ `SUPPORTED` $\to$ `VERIFIED` / `DISMISSED`.

### 7. Change-Aware Remediation Verifier ([`remediation_verifier.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/remediation_verifier.py))
- **Function**: Re-analyzes updated code patches to verify if a previously identified risk scenario has been resolved (`VERIFIED_FIXED`).

### 8. Explainable Security Summary Engine ([`explanation_engine.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/explanation_engine.py))
- **Function**: Generates structured explanations detailing WHY a risk was identified, WHICH assets are involved, WHAT attack path exists, and WHAT remediates it.

### 9. Normalized Evidence Provider ([`evidence_provider.py`](file:///Users/23MIS0012/Desktop/NOVA/backend/app/services/security_intelligence/evidence_provider.py))
- **Function**: Exposes `SecurityEvidenceProvider` returning normalized `UnifiedEvidenceItem` objects to NOVA's Assistant RAG framework.
