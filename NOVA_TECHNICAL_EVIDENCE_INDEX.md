# NOVA TECHNICAL EVIDENCE INDEX

> **DOCUMENT TYPE**: REPRODUCIBLE TECHNICAL EVIDENCE MAPPING
> **BASELINE COMMIT**: `ad42529` (Canonical End-to-End Demonstration)
> **STATUS**: **VERIFIED & FROZEN**

---

## 1. Subsystem Evidence Mapping Table

| Claim / Mechanism | Source File & Location | Relevant Class / Function | Verification Method | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **Independent Asset Discovery** | `app/services/security_intelligence/asset_discovery_service.py` | `AssetDiscoveryService.discover_assets()` | `test_security_intelligence_service.py` | **VERIFIED** |
| **AST Security Observations** | `app/services/security_intelligence/observation_collector.py` | `ObservationCollectorService.collect_observations()` | `test_security_intelligence_service.py` | **VERIFIED** |
| **Security Context Graph** | `app/services/security_intelligence/security_context_graph.py` | `SecurityContextGraphService.build_context_graph()` | `test_security_intelligence_service.py` | **VERIFIED** |
| **Independent Control Analysis** | `app/services/security_intelligence/control_analyzer.py` | `ControlAnalyzerService.evaluate_controls()` | `test_security_intelligence_service.py` | **VERIFIED** |
| **Risk Scenario Engine** | `app/services/security_intelligence/risk_scenario_engine.py` | `RiskScenarioEngine.infer_scenarios()` | `test_security_intelligence_service.py` | **VERIFIED** |
| **Scenario Verification Gate** | `app/services/security_intelligence/scenario_verifier.py` | `ScenarioVerifierService.verify_scenarios()` | `test_security_intelligence_service.py` | **VERIFIED** |
| **Remediation Patch Verifier** | `app/services/security_intelligence/remediation_verifier.py` | `RemediationVerifierService.verify_remediation()` | `test_canonical_demo_workflow.py` | **VERIFIED** |
| **Temporal Posture Snapshot** | `app/services/security_intelligence/posture_trend_engine.py` | `PostureTrendEngine.generate_snapshot_record()` | `test_temporal_posture_engine.py` | **VERIFIED** |
| **Dual-Track Evidence Fusion** | `app/services/security_intelligence/evidence_provider.py` | `SecurityEvidenceProvider.get_security_evidence()` | `test_evidence_fusion_integration.py` | **VERIFIED** |
| **Pairwise NLI Consensus** | `app/services/ai/nli_engine.py` | `NLIEngine.analyze_pair()` | `test_nli_consensus.py` | **VERIFIED** |
| **8D Platt Calibrator** | `app/services/search_analytics/calibrator.py` | `ConfidenceCalibrator.calibrate()` | `test_safety_gate_explainability.py` | **VERIFIED** |
| **Two-Stage Safety Policy Gate** | `app/services/assistant/assistant_service.py` | `AssistantService._evaluate_trust_and_safety()` | `test_safety_gate_explainability.py` | **VERIFIED** |
| **Explainable Safety Response** | `app/services/search_analytics/calibrator.py` | `ConfidenceCalibrator.build_safety_explanation()` | `test_safety_gate_explainability.py` | **VERIFIED** |
| **Executive Radar Integration** | `app/services/analytics/executive_intelligence.py` | `ExecutiveIntelligenceService.build_evidence_snapshot()` | `test_executive_intelligence.py` | **VERIFIED** |
| **Canonical Demo Workflow** | `app/demo/orchestrator.py` | `CanonicalDemoOrchestrator.reset_demo_environment()` | `test_canonical_demo_workflow.py` | **VERIFIED** |

---

## 2. Test Verification Summary

- **Core Security & RAG Test Suites**: 113/113 PASSED (0.77s)
- **Canonical Demo Workflow Test Suite**: 4/4 PASSED (0.25s)
- **Frontend TypeScript Compilation (`npx tsc --noEmit`)**: 0 ERRORS
- **Frontend Production Build (`npm run build`)**: PASSED (187ms)
