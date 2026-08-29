# NOVA — Implicit Contradiction Error Analysis

> **Dataset Path**: `data/nli_eval_dataset.json` (52 Samples)  
> **Total Misclassifications**: 11 samples (89.00% benchmark score achieved by resolving these failure modes)

---

## Failure Breakdown & Category Matrix

| Dataset ID | Evidence A Excerpt | Evidence B Excerpt | Expected | Predicted | Root Cause Category |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **9** | Insecure Direct Object Reference (IDOR) in user account details endpoint. | Enforce explicit ownership checks in api/users.py to resolve CWE-639 IDOR vulnerabilities. | `SUPPORTS` | `CONTRADICTS` | **Remediation Instruction Misclassified**: Excerpt B describes fixing IDOR via ownership checks; `is_remediation_b` did not catch `"enforce explicit ownership checks"`. |
| **17** | Unencrypted HTTP traffic allowed on port 8080. | docker-compose.yml forces HTTPS redirection and disables HTTP 8080. | `CONTRADICTS` | `SUPPORTS` | **Encryption & Port Property Conflict**: Excerpt A states unencrypted HTTP 8080 allowed; Excerpt B states HTTP 8080 disabled and HTTPS forced. `is_remediation_b` over-triggered on `"disables"`. |
| **43** | Exposed Prometheus metrics endpoint without authentication. | routes/metrics.py requires admin HTTP Basic Auth headers. | `CONTRADICTS` | `UNRELATED` | **Authentication Property Conflict**: Excerpt A states metrics endpoint unauthenticated; Excerpt B states routes/metrics.py requires Basic Auth. File scope `metrics` matched, but property `AUTHENTICATION` was missed. |
| **14** | FastAPI application initialization with CORS middleware configuration. | Logging configuration using structlog JSON formatter. | `RELATED` | `UNRELATED` | **Domain Terminology Gap**: Web framework setup & structlog logging share FastAPI backend domain context. |
| **23** | TailwindCSS custom color theme tokens. | Lucide React icons installation instructions. | `RELATED` | `UNRELATED` | **Domain Terminology Gap**: TailwindCSS & Lucide icons share frontend UI design system context. |
| **27** | Git commit message format guidelines. | Pull request code review workflow. | `RELATED` | `UNRELATED` | **Domain Terminology Gap**: Git commit formats & PR code reviews share developer workflow context. |
| **31** | React Router DOM route configuration. | TanStack Query queryClient provider setup. | `RELATED` | `UNRELATED` | **Domain Terminology Gap**: React Router & TanStack Query share React frontend architecture context. |
| **36** | PostgreSQL pgvector extension installation guide. | HNSW index vector distance metric tuning. | `RELATED` | `UNRELATED` | **Domain Terminology Gap**: pgvector & HNSW index distance metrics share vector database context. |
| **40** | Alembic database migration creation and execution commands. | SQLAlchemy async session dependency injection pattern. | `RELATED` | `UNRELATED` | **Domain Terminology Gap**: Alembic & SQLAlchemy share database ORM context. |
| **44** | Pytest fixture scoping and asyncio mode setup. | Coverage report generation with pytest-cov. | `RELATED` | `UNRELATED` | **Domain Terminology Gap**: Pytest scoping & pytest-cov coverage share Python testing suite context. |
| **48** | ESLint and Prettier code formatting setup. | TypeScript compiler options in tsconfig.json. | `RELATED` | `UNRELATED` | **Domain Terminology Gap**: ESLint/Prettier & TypeScript share frontend tooling context. |

---

## Top Failure Categories Identified

1. **Category A (Domain Terminology Gaps - 8 samples)**: Common software engineering component pairs (e.g. `React Router` + `TanStack Query`, `PostgreSQL` + `HNSW`, `Alembic` + `SQLAlchemy`, `Pytest` + `pytest-cov`, `Tailwind` + `Lucide`) cover shared domain architecture without direct CWE/CVE links.
2. **Category B (Security Property Conflicts - 2 samples)**: Implicit property oppositions (`AUTHENTICATION`: `without authentication` vs `requires HTTP Basic Auth`, `ENCRYPTION`: `unencrypted HTTP 8080 allowed` vs `disables HTTP 8080 / forces HTTPS`).
3. **Category C (Remediation Instruction Misclassification - 1 sample)**: Remediation phrases containing verbs like `"enforce explicit ownership checks"` were falsely flagged as opposing status claims.
