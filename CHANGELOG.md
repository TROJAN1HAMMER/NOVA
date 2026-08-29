# Changelog

All notable changes to NOVA are documented in this file.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project does not yet follow strict semantic versioning tags — entries are grouped by release milestone instead.

## [Unreleased]

### Added

**Flutter Mobile Application**
- A new native Android/iOS client (`mobile/`) consuming the existing FastAPI backend, with no backend changes required to support it.
- Riverpod state management, `go_router` with backend-role-aware redirects, Dio-based API client with JWT refresh interceptor, and `freezed`/`json_serializable` models mirroring backend Pydantic schemas field-for-field.
- Fully wired against live endpoints: authentication, dashboard analytics, repositories, scan submission, and scan queue/detail.
- Clearly labeled placeholder screens (Risk, Findings, Compliance, Reports, Executive, Architecture, Notifications) for areas where the backend does not yet expose a matching endpoint — documented in `mobile/docs/backend_gaps.md`.

**Retrieval-Augmented Generation (RAG) Knowledge Layer**
- **Knowledge Base** — document upload (PDF/Markdown/text), content-hash deduplication, filename-based versioning, heading/section/page-aware chunking, and local ONNX embeddings (`BAAI/bge-small-en-v1.5`) into a PostgreSQL/pgvector index.
- **AI Assistant** — a streaming, citation-backed chat panel over the knowledge base, with retrieve → rerank (`Xenova/ms-marco-MiniLM-L-6-v2`) → confidence-gate → generate pipeline. Refuses to answer rather than guessing when nothing sufficiently relevant is retrieved.
- **Finding Intelligence** — a per-finding, citation-backed deep-dive (plain-English explanation, business/technical impact, remediation, verification steps, code example) grounded in the same knowledge base, layered on top of NOVA's own deterministic CWE/OWASP/MITRE/compliance identifiers.
- **Executive Intelligence** — evidence-grounded answers to portfolio-level questions, combining a deterministic scan-history snapshot with knowledge-base retrieval, exportable to PDF.
- **Production hardening** — Redis-backed response/embedding/rerank caching, per-user per-endpoint rate limiting, search analytics, a feedback-collection endpoint, a benchmark suite, and extended `/health/ready` checks for the vector index and embedding/rerank models.

**Interactive Architecture Visualization**
- A 3D, explorable system-architecture diagram (React Three Fiber), available both publicly (`/architecture`, no login) and inside the authenticated dashboard (`/dashboard/architecture`), sharing one underlying component.

**Executive Reporting**
- PDF export for Executive Intelligence Q&A sessions, alongside the existing executive/technical scan-report PDFs.

### Changed

**Terminology — Attack Surface Exposure**
- The module formerly named "Zero-Day Prediction" (`backend/app/services/risk/zero_day_predictor.py`) is renamed to **Attack Surface Exposure** (`attack_surface_exposure.py`). The rename is not cosmetic: the old name claimed a predictive capability — forecasting undiscovered vulnerabilities — that a weighted-heuristic model cannot actually support. The renamed module's own documentation is explicit that it measures a composite index of exposure factors (dependency count, known-CVE density, dependency staleness, risky package categories, configuration risk, code vulnerability density) correlated with exposure to undisclosed vulnerabilities, and does not forecast any specific future exploit.
- Database columns, API response fields, and the PDF report generator were updated to match (migration `0010_rename_zero_day_to_attack_surface_exposure.py`). One leftover overclaiming phrase in the PDF technical-report template ("zero-day forecast vectors") has been corrected to "confirmed CVEs and high attack-surface exposure."

**Documentation overhaul**
- `README.md` fully rewritten to reflect the current state of the platform: the RAG knowledge layer, the Flutter mobile client, the Interactive Architecture Visualization, and corrected Attack Surface Exposure terminology. Restructured for a mixed audience (contributors, reviewers, and banking/fintech evaluators), with a clear split between implemented functionality and roadmap items.
- Regulatory compliance mapping (PCI DSS v4.0 / RBI IT Framework 2021 / SWIFT CSP) documentation now explicitly states these are NOVA's own illustrative control mappings for continuous self-assessment, not a certified regulator/QSA attestation.
- `backend/.env.example` expanded to cover every setting `app/config.py` actually reads (AI provider gateway, S3 report storage, OAuth2/LDAP/SAML SSO, NVD API key) — previously incomplete.

**Banking Risk Score**
- Continued refinement of the 7-factor weighted-average model and the residual-uncertainty baseline for zero-finding scans (see `docs/brs_audit_report.md` for the audit trail behind these adjustments).

### Fixed

- Removed stale compiled Python bytecode (`__pycache__/*.pyc`) that had been accidentally committed to git, including cached bytecode from the now-deleted `zero_day_predictor.py` module.
- `backend/.env` (a real, locally-modified environment file) was tracked in git; it has been removed from tracking and the repository now relies on `backend/.env.example` as the documented template, per standard practice.

### Security

- Audited the full repository for committed secrets (API keys, JWT/app secrets, database/Redis credentials, private keys, OAuth secrets). None were found — all matches on secret-like patterns were either intentional test-fixture data (`payload_generator.py`'s synthetic vulnerable-code samples) or obvious local-development placeholders (e.g. `change-me`, `NOVA_secret`). `backend/.env` is nonetheless untracked going forward as a defense-in-depth measure (see Fixed, above).

---

## Milestone history (pre-changelog)

The entries below summarize prior work that predates this file, reconstructed from commit history and design docs for context:

- **Initial platform**: RBAC/SSO authentication, a 9-scanner static/dependency/config/secret/container security pipeline with cross-tool aggregation, the Banking Risk Score and (then-named) Zero-Day Prediction engines, regulatory compliance mapping, multi-format report generation, and Helm/Kubernetes deployment tooling.
- **RAG Milestone 1 — Knowledge Base**: document ingestion infrastructure (upload, chunking, local embeddings, pgvector storage) with no LLM calls yet.
- **RAG Milestone 2 — AI Assistant**: grounded, streaming Q&A over the knowledge base.
- **RAG Milestone 3 — Finding Intelligence**: per-finding RAG-grounded explanations.
- **RAG Milestone 4 — Executive Intelligence**: evidence-grounded executive Q&A panel.
- **RAG Milestone 5 — Production Hardening**: caching, rate limiting, document versioning/dedup, search analytics, feedback collection, benchmarking, and health/monitoring endpoints across the RAG stack.
