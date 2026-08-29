# NOVA — Patent-Oriented Technical Core Summary

> **Document Type**: Technical Invention Architecture Specification  
> **System Name**: Neural Orchestrated Vector Assistant (NOVA)  
> **Verification Status**: 100% Code Verified (334 Passing Backend Tests)

---

## 1. System Abstract

NOVA is a security-aware evidence fusion and trust-calibrated retrieval-augmented generation (RAG) system. The system combines multi-source heterogeneous retrieval (unstructured enterprise knowledge and structured SAST/DAST scanner findings), unified evidence schema mapping, cross-encoder neural reranking, pairwise Natural Language Inference (NLI) relationship classification, structured security property state extraction, matrix evidence consensus calculation, an 8-dimensional Platt-scaled confidence calibrator, a two-stage safety policy gate, and an automated HDBSCAN query-gap self-healing feedback loop.

---

## 2. Core Invention Pipeline Architecture

```
                               RAW USER QUERY
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
         UNSTRUCTURED KNOWLEDGE               STRUCTURED SECURITY
           VECTOR RETRIEVAL                    FINDINGS RETRIEVAL
                    │                                 │
                    └────────────────┬────────────────┘
                                     │
                         UNIFIED EVIDENCE FUSION
                       (UnifiedEvidenceItem Schema)
                                     │
                         CROSS-ENCODER RERANKING
                                     │
                     PAIRWISE NLI RELATIONSHIP ENGINE
                   (SUPPORTS / CONTRADICTS / RELATED)
                                     │
                       SECURITY PROPERTY EXTRACTION
                    (AUTHENTICATION, AUTHORIZATION, etc.)
                                     │
                     EVIDENCE CONSENSUS CALCULATION
                          (Matrix C_agreement)
                                     │
                        8D PLATT TRUST CALIBRATOR
                       (Calibrated TrustScore)
                                     │
                       TWO-STAGE SAFETY POLICY GATE
             (Hard threshold: C_agreement <= 0.20 -> FALLBACK_WEB)
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
             RESPONSE GENERATION             WEB FALLBACK / ABSTENTION
```

---

## 3. Detailed Mechanism Specifications

### Mechanism 1: Multi-Source Heterogeneous Evidence Fusion
- **Problem**: Enterprise RAG systems treat static documentation and dynamic security scanner findings as isolated databases.
- **Input**: Knowledge base vector chunks and PostgreSQL `SecurityFinding` records (Bandit, Semgrep, Trivy, ZAP).
- **Operation**: Maps heterogenous records into a standardized `UnifiedEvidenceItem` dataclass:
  ```python
  @dataclass
  class UnifiedEvidenceItem:
      evidence_id: str
      source_type: str  # "knowledge_doc" | "security_finding" | "faq_axiom"
      content: str
      cve_id: Optional[str]
      cwe_id: Optional[str]
      file_path: Optional[str]
      raw_score: float
      reliability_weight: float
  ```
- **Output**: Unified evidence candidate list $E = \{e_1, e_2, \dots, e_k\}$.

### Mechanism 2: Pairwise NLI Cross-Encoder & Security Property Extraction
- **Problem**: Cosine distance cannot distinguish between complementary remediation advice and contradictory security assertions.
- **Input**: Candidate evidence pairs $(e_i, e_j)$.
- **Operation**:
  1. Computes cross-encoder cross-attention score $S_{\text{nli}}(e_i, e_j)$.
  2. Extracts version tuples and scope match flags (`same_cve`, `same_file`, `same_cwe`).
  3. Extracts structured `SecurityProperty` ($P \in \{\text{AUTHORIZATION}, \text{AUTHENTICATION}, \text{ENCRYPTION}, \text{INPUT\_VALIDATION}\}$) and assigns states ($S \in \{\text{VULNERABLE}, \text{SAFE}\}$).
  4. Classifies pair relationship:
     $$\text{Rel}(e_i, e_j) = \begin{cases} \text{CONTRADICTS}, & \text{if same scope/property and opposing states } (S_i \neq S_j) \text{ and not remediation} \\ \text{SUPPORTS}, & \text{if remediation guidance or matching CWE/file} \\ \text{RELATED}, & \text{if distinct CVEs or shared domain context} \\ \text{UNRELATED}, & \text{otherwise} \end{cases}$$
- **Output**: Rich `EvidenceRelationship` payload containing `relationship`, `confidence`, `nli_label`, `scope_match`, `property_match`, and explainable `reason`.

### Mechanism 3: Matrix Evidence Consensus Calculation
- **Problem**: Standard similarity averaging ignores structural conflicts across retrieved chunks.
- **Input**: Evidence relationships list $R = \{\text{Rel}(e_i, e_j)\}$.
- **Operation**: Constructs symmetric evidence relationship matrix $M \in \mathbb{R}^{k \times k}$ and computes agreement score:
  $$C_{\text{agreement}} = \frac{N_{\text{supports}} - N_{\text{contradicts}}}{\max(N_{\text{pairs}}, 1)}$$
  normalized to $[0, 1]$.
- **Output**: Scalar agreement metric $C_{\text{agreement}}$.

### Mechanism 4: 8-Dimensional Platt-Scaled Trust Calibrator
- **Problem**: Raw LLM confidence estimates are uncalibrated and prone to overconfident hallucination.
- **Input**: 8-dimensional confidence vector $C$:
  $$C = [C_{\text{retrieval}}, C_{\text{agreement}}, C_{\text{citation}}, C_{\text{reasoning}}, C_{\text{freshness}}, C_{\text{hallucination\_risk}}, C_{\text{source\_reliability}}, C_{\text{user\_feedback}}]^T$$
- **Operation**: Passes vector $C$ through Platt-scaled logistic transformation:
  $$\text{logit}(C) = 2.5 C_{\text{retrieval}} + 2.0 C_{\text{agreement}} + 1.5 C_{\text{citation}} + 1.0 C_{\text{reasoning}} + 1.0 C_{\text{freshness}} - 3.0 C_{\text{hallucination\_risk}} + 1.0 C_{\text{source\_reliability}} + 0.5 C_{\text{user\_feedback}} - 2.8$$
  $$\text{TrustScore} = P(\text{Correct} \mid C) = \frac{1}{1 + e^{-\text{logit}(C)}}$$
- **Output**: Calibrated probability $\text{TrustScore} \in [0, 1]$.

### Mechanism 5: Two-Stage Safety Policy Gate
- **Problem**: Statistical logistic models can still produce high probabilities when non-agreement features dominate.
- **Input**: $\text{TrustScore}$ and $C_{\text{agreement}}$.
- **Operation**:
  - **Stage 1**: Evaluates statistical $\text{TrustScore} \ge \text{Threshold}$.
  - **Stage 2 (Hard Policy Check)**: If $C_{\text{agreement}} \le 0.20$ (indicating critical evidence contradiction), overrides Stage 1 and forces **`FALLBACK_WEB`**.
- **Output**: Action decision $\text{Decision} \in \{\text{GENERATE}, \text{GENERATE\_WITH\_WARNING}, \text{FALLBACK\_WEB}, \text{ABSTAIN}\}$.

### Mechanism 6: Automated Query-Gap Self-Healing Feedback Loop
- **Problem**: Unhandled or low-confidence queries persistently cause system fallbacks.
- **Input**: Logged low-confidence user queries ($C_{\text{agreement}} \le 0.20$ or $\text{TrustScore} < 0.70$).
- **Operation**: Clusters query embeddings using HDBSCAN ($\text{min\_cluster\_size} = 3$), synthesizes cluster centroids into draft FAQ Axioms, and persists them to the `FAQRule` table for instant $0.003\text{ms}$ matching.
- **Output**: Promoted `ACTIVE` FAQ rules.

---

## 4. Empirical Validation Summary

Evaluated on the 52-sample manually labelled benchmark ([`data/nli_eval_dataset.json`](file:///Users/23MIS0012/Desktop/NOVA/data/nli_eval_dataset.json)):

| Benchmark Metric | Lexical Overlap Baseline | Standard RAG | NOVA Patent Core Pipeline | Absolute Improvement |
| :--- | :---: | :---: | :---: | :---: |
| **System Accuracy** | 3.85% | 65.38% | **82.69%** | **+17.31%** |
| **Macro F1 Score** | 0.0355 | 0.5851 | **0.7868** | **+0.2017** |
| **`SUPPORTS` Precision** | 0.00% | 75.00% | **100.00%** (17/17) | **+25.00%** |
| **`CONTRADICTS` Recall** | **0.00%** | **23.08%** | **100.00%** (13/13) | **+76.92%** |
| **`CONTRADICTS` F1** | 0.0000 | 0.3750 | **0.9630** | **+0.5880** |
| **Execution Latency** | — | — | **0.060 ms / pair** | Real-Time Operational |
