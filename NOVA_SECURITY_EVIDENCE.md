# NOVA Security Evidence & Multi-Scanner Fusion Specification

## Overview

NOVA unifies static code analysis findings (Semgrep, Joern, ast-grep, Secrets, Docker, YAML) and dependency vulnerabilities (pip-audit, OSV, NVD) with vector document chunks into a unified evidence fusion representation.

> **Retrieval Architecture Note**: Security finding retrieval is currently structured SQL keyword & metadata term search (`finding_service.py`), while knowledge chunk retrieval is `pgvector` dense vector search (`vector_store.py`). Both streams are fused into `UnifiedEvidenceItem` objects.

## Cross-Scanner Confidence Boosting

When multiple independent security scanners detect the same vulnerability location, NOVA applies an independent probability boost during finding enrichment (`enrichment.py`):

$$C_{\text{finding}} = 1.0 - \prod_{i=1}^N \left(1.0 - c_i\right)$$

- **Single Scanner** ($N=1$, $c_1=0.85$): $C_{\text{finding}} = 0.8500$.
- **Dual Scanners** ($N=2$, $c_1=c_2=0.85$): $C_{\text{finding}} = 0.9775$.
- **Triple Scanners** ($N=3$, $c_1=c_2=c_3=0.85$): $C_{\text{finding}} = 0.9966$.

## Context Block Provenance Formatting

When security evidence reaches the LLM, headers explicitly distinguish security finding provenance from knowledge documents:

```
[1] (Security Finding [HIGH], Location: app/auth.py:42, CWE: CWE-89, CVE: CVE-2026-1234)
Security Vulnerability [HIGH]: SQL Injection in auth handler
Description: Raw query string concatenation in login function.
Remediation: Use parameterized statements or ORM binding.

[2] (Source: Secure_Coding_Guide.pdf, Section: Database Operations, Page: 12)
Always utilize bind parameters when executing dynamic SQL queries.
```
