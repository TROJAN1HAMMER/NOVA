# NOVA Empirical Evaluation & Ablation Suite

## Benchmark Comparison (52-Sample Manually Labelled Dataset)

> **Evaluation Script**: `backend/scripts/evaluate_nli_consensus.py`  
> **Dataset**: `data/nli_eval_dataset.json` (52 Samples)

---

## Benchmark Comparison Table

| Metric | Lexical Overlap Baseline | Previous NLI Engine | Current Version & Scope Aware NLI | Absolute Improvement |
| :--- | :---: | :---: | :---: | :---: |
| **Accuracy** | 3.85% (0.0385) | 65.38% (0.6538) | **73.08% (0.7308)** | **+7.70%** |
| **Macro F1 Score** | 0.0355 | 0.5851 | **0.7035** | **+0.1184** |
| **Macro Precision** | 0.0476 | 0.6950 | **0.7971** | **+0.1021** |
| **Macro Recall** | 0.0339 | 0.6410 | **0.7360** | **+0.0950** |
| **`CONTRADICTS` Recall** | 0.00% | **23.08%** (3/13) | **84.62%** (11/13) | **+61.54%** |
| **`CONTRADICTS` F1** | 0.0000 | 0.3750 | **0.7857** | **+0.4107** |
| **`RELATED` Precision** | 0.0000 | 44.44% | **100.00%** | **+55.56%** |

---

## Per-Class Breakdown (Current Version)

- **`SUPPORTS`**: Precision = **0.9286**, Recall = **0.7647**, F1 = **0.8387** (17 Samples)
- **`CONTRADICTS`**: Precision = **0.7333**, Recall = **0.8462**, F1 = **0.7857** (13 Samples)
- **`RELATED`**: Precision = **1.0000**, Recall = **0.3333**, F1 = **0.5000** (12 Samples)
- **`UNRELATED`**: Precision = **0.5263**, Recall = **1.0000**, F1 = **0.6896** (10 Samples)
