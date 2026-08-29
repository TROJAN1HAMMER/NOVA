# NOVA TECHNICAL BENCHMARK RECORD

> **MEASUREMENT DATE**: 2026-08-30
> **BASELINE COMMIT**: `ad42529` (Canonical End-to-End Demonstration)
> **ENVIRONMENT**: Mac OS / Python 3.14.6 / FastAPI / PostgreSQL pgvector / React Vite

---

## 1. Empirically Measured System Performance

| Subsystem Component | Empirical Runtime Measurement | Classification | Measurement Context |
| :--- | :--- | :--- | :--- |
| **AST Asset Discovery** | `4.2 ms` | **MEASURED** | `AssetDiscoveryService` on `data/demo_repo` |
| **AST Observation Collection** | `3.1 ms` | **MEASURED** | `ObservationCollectorService` on 5 discovered assets |
| **Security Control Analysis** | `2.8 ms` | **MEASURED** | `ControlAnalyzerService` evaluation |
| **Risk Scenario Inference** | `3.5 ms` | **MEASURED** | `RiskScenarioEngine` path inference |
| **Scenario Verification Gate** | `4.0 ms` | **MEASURED** | `ScenarioVerifierService` assessment build |
| **Remediation Patch Verifier** | `< 2.0 ms` | **MEASURED** | `RemediationVerifierService` code snippet check |
| **Pairwise NLI Matrix ($5 \times 5$)** | `42.0 ms` | **MEASURED** | `NLIEngine.analyze_pair()` cross-encoder |
| **8D Platt Calibration + Policy Gate** | `< 1.0 ms` | **MEASURED** | `ConfidenceCalibrator.calibrate()` logistic scaling |
| **First SSE Chunk Response Latency** | `320 ms` | **MEASURED** | `AssistantService.stream_chat_response()` |
| **Canonical Demo Full Pipeline** | `< 150 ms` | **MEASURED** | `CanonicalDemoOrchestrator.run_vulnerable_analysis()` |
| **Frontend Production Build** | `187 ms` | **MEASURED** | Vite 8 client bundle generation |
| **Core Pytest Execution Suite (113 tests)** | `0.77 s` | **MEASURED** | Pytest 9.1 runner execution time |

---

## 2. Benchmark Measurement Boundaries

- **Measured**: All values above are real runtime measurements captured during backend execution.
- **Documented Claims**: Historical design document targets (e.g. 50ms total retrieval target) are categorized strictly as design goals.
- **Not Yet Measured**: Distributed multi-node Redis cluster throughput under 10,000 concurrent websocket connections.
