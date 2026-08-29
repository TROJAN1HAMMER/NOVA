# NOVA NLI Evaluation Dataset Audit Report

> **Dataset Path**: `data/nli_eval_dataset.json`  
> **Dataset Classification**: `MANUALLY LABELLED EVALUATION DATASET`  
> **Audit Status**: COMPLETED (100% Sample Verification)

---

## 1. Overview & Statistics

- **Total Samples**: 52 evidence pair examples
- **Class Distribution**:
  - `SUPPORTS`: 17 samples (32.69%)
  - `CONTRADICTS`: 13 samples (25.00%)
  - `RELATED`: 12 samples (23.08%)
  - `UNRELATED`: 10 samples (19.23%)
- **Class Imbalance**: Low-to-moderate imbalance ($17 : 13 : 12 : 10$). All 4 classes are well represented across the 52 samples.
- **Duplicate Pair Count**: **0 duplicates**. Every pair consists of distinct text excerpts.
- **Train/Test Contamination**: **None**. The dataset is strictly isolated in `data/nli_eval_dataset.json` and is never imported or referenced by production application code (`app/services/`).

---

## 2. Qualitative Sample Audit

- **Authoring Origin**: Synthetic/manually authored domain-specific cybersecurity and enterprise knowledge pairs covering CWEs (CWE-89, CWE-79, CWE-798, CWE-78, CWE-639, CWE-22, CWE-918, CWE-328, CWE-611, CWE-502, CWE-799, CWE-601, CWE-434, CWE-116, CWE-209, CWE-362, CWE-295, CWE-327, CWE-330), file paths (`auth.py`, `profile.py`, `settings.py`, `backup.py`), and general enterprise policy documents (HR vacation leave, gym membership, parking permit).
- **Structure**: Each sample provides `id`, `evidence_a` dict, `evidence_b` dict, and `expected_relationship`.

---

## 3. Data Leakage Verification

- **Code Search Verification**: Checked `app/services/` for dataset text excerpts. Result: **0 matches**.
- **Threshold Tuning**: System thresholds (e.g. `nli_score >= 0.50`, `lex_overlap > 0.05`) are standard module heuristics and not fitted to dataset record IDs.
