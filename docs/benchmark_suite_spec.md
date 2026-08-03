# NOVA Benchmark Suite — Specification (Design Only, No Code Yet)

Five canonical, production-like reference repositories for regression-testing every layer of NOVA: static analysis, dependency analysis, secret detection, configuration scanning, supply chain analysis, the Banking Risk Score (BRS) engine, the dashboard, and reports.

**Status:** design only. No repository code has been generated. Every "Expected Banking Risk Score" figure below was computed by feeding a representative finding set through the actual, currently-deployed `score_finding()` / `rollup_scan_brs()` / `classify_module()` functions in `backend/app/services/risk/brs_engine.py` — the same engine validated in the preceding audit — not estimated. The BRS engine itself was **not modified** for this exercise, per instruction.

---

## 0. Calibration Methodology and a Load-Bearing Finding

Before designing the five repositories, the originally-requested target bands (5–20 / 20–40 / 40–60 / 60–80 / 80–100) were checked against the real engine by scoring representative candidate findings. This surfaced a structural property of the (already-validated, unmodified) engine that constrains what's achievable:

**Every finding, however mild, has a floor around BRS ≈ 32–36 on its own.** Two reasons, both confirmed by direct computation, not inferred:

1. `compliance_mappings.json` maps every finding category — including the `"unknown"` fallback — to all three regulatory frameworks (RBI + PCI + SWIFT). `compliance_framework_count()` therefore always returns 3 in production, which pins `compliance_impact_score()` at its maximum (10.0) for literally every finding, regardless of how trivial. This alone contributes a fixed +1.0 to the blended score before CVSS is even considered.
2. `business_criticality`, `asset_value`, and (for internet-facing-default modules) `internet_exposure` are flat, module-level properties — they don't scale down with a finding's own severity. Even the most permissive module (`General`, weight 4.0/4.0) and the lowest-exploitability category (`insecure_random`, 4.0) with `cvss=0` still blends to 32.0.

Measured directly:

| Scenario | Real engine output |
|---|---|
| 0 findings | **0.0** (`rollup_scan_brs([])` short-circuits to 0) |
| 1 minimal finding (General module, `insecure_random`, cvss≈0) | **32.0** |
| 1 minimal finding, `security_misconfiguration`, cvss=0–4 | **35.75 – 47.75** |
| 2 mild Low findings (General module) | **~38** |

**Consequence:** a repository can only land in the 5–20 band with **zero findings at all**. The instant it has even one real, however-trivial finding, the floor is already ~32–36. This also means `_calculate_risk_level()`'s "Low" label (threshold `<35`) is, in practice, only ever reachable by an empty scan — no repository with 1+ findings can display "Low" under the current thresholds. This is reported here as a finding of the calibration exercise, **not fixed** — the instruction for this task is explicitly to redesign the repositories, not the engine. It's flagged again in §7 as a follow-up recommendation for a future, separate task.

**Second constraint, also measured, not guessed:** `Authentication` (criticality 8.5, asset 8.0, internet-facing-default) and `Payments` (10.0/10.0, internet-facing-default) modules pull *any* finding's floor up to ~55–65+ almost regardless of the finding's own CVSS, because those per-module factors are flat additive terms, not CVSS-scaled ones. Consequence for design: the Medium-risk repository deliberately avoids any file path, title, or description containing an Authentication/Payments/Customer-Data module keyword (`auth`, `login`, `jwt`, `token`, `payment`, `transfer`, `customer`, `account`, etc.) — using those words, even for a genuinely minor issue, would misclassify it into a high-weight module and push the score into High/Critical territory. This is why the Medium repo's inventory-system endpoints are named around orders/stock rather than accounts/payments, while the High and Critical repos *deliberately* use Payments/Authentication/Customer-Data paths — appropriate, since those are the modules meant to demonstrate elevated business criticality.

**Recalibrated target bands actually used below** (evidence-based, not the originally-requested literal numbers — consistent with the brief's own "these ranges are approximate; the important goal is that every repo clearly falls into its intended category"):

| Repo | Requested band | Calibrated, achieved band | Risk level label shown |
|---|---|---|---|
| very-low-risk | 5–20 | **0.0** | Low |
| low-risk | 20–40 | **~38** | Medium *(see note below)* |
| medium-risk | 40–60 | **~54** | Medium |
| high-risk | 60–80 | **~80** | High |
| critical-risk | 80–100 | **~93** | Critical |

**Note on `NOVA-demo-low-risk`'s label:** at ~38, `_calculate_risk_level()` labels it "Medium," not "Low" — purely because of the floor described above (its own score sits at the *very bottom* of the Medium band, clearly and correctly below the Medium repo's ~54 and far below High's ~80). The five repos are still strictly and clearly ordered (0 < 38 < 54 < 80 < 93), which was the brief's stated priority. If the discrete label matters as much as the ordering, `_calculate_risk_level()`'s thresholds would need revisiting in a separate, dedicated task — out of scope here.

---

## Shared Conventions (all five repos)

- **License/structure:** each repo is a single, small, runnable service — one primary language (Python/FastAPI or Flask, or Node/Express for the one component per repo that needs it), one `requirements.txt` or `package.json`, one `Dockerfile`, and (from Medium upward) one `docker-compose.yml` and one `.github/workflows/ci.yml`, so every scanner category the pipeline runs has something to find in every repo from Medium up. Very-low and Low intentionally have *clean* infra files rather than omitting them — an absent Dockerfile can't demonstrate secure Docker practice.
- **Determinism:** no timestamps, random file ordering, or generated UUIDs baked into source — every file's content is fully specified so the repository is byte-identical on every regeneration.
- **Line budget:** every repo stays within ~500–900 LOC across all files, well under the 500–1200 ceiling.
- **No CTF-style code:** every vulnerability is written the way a real developer mistake looks — no `# HACK THIS` banners, no puzzle logic, no unreachable dead code. (This is a deliberate correction from the old sandbox fixtures, where the "SQL injection" was built but never executed — every vulnerability below is reachable and would be found by dynamic testing too, even though detection here is via static analysis only, per the brief.)
- **Scanner coverage note (carried over from the preceding audit):** semgrep, ast-grep, and Joern are not currently installed in this environment; `static_scanner.py` transparently falls back to a regex-based scanner (now honestly labeled `semgrep-fallback`, not `semgrep`, per the prior fix). All vulnerabilities below are written to be catchable by patterns already in `PATTERN_RULES` (hardcoded-api-key, hardcoded-password, hardcoded-aws-key, sql-injection-concat, weak-hash-md5, weak-hash-sha1, unsafe-pickle, command-injection-shell, os-system, yaml-unsafe-load) **wherever that list already has a rule** — where it doesn't (path traversal, insecure randomness, weak DES cipher, CORS/IAM/Docker/K8s misconfiguration), detection is attributed to `docker-scanner`/`yaml-scanner`/`config-scanner`/OSV/pip-audit/secrets-scanner, all of which are confirmed working. Findings that depend specifically on semgrep/ast-grep/Joern's AST-level capability (e.g. taint-tracked SQLi across function boundaries, IDOR requiring cross-file authorization logic) are flagged **"requires semgrep/ast-grep/Joern installed"** in each table — they're real, correctly-written vulnerabilities either way, but won't be caught by the current fallback until those tools are installed (§7).

---

## 1. `NOVA-demo-very-low-risk`

**Purpose:** the "this is what right looks like" reference — a small authentication & session microservice, built the way a security-conscious team actually would.

**Application type:** Authentication service (FastAPI).

**Architecture:** single FastAPI app, SQLite via SQLAlchemy (parameterized ORM queries only), `passlib[bcrypt]` for password hashing, `python-jose`/`pyjwt` for JWT with a strong random secret loaded from environment, `pydantic` models for input validation on every endpoint.

**Folder structure:**
```
NOVA-demo-very-low-risk/
├── app/
│   ├── main.py              # FastAPI app, routes: /register /login /me /health
│   ├── models.py             # SQLAlchemy models (User)
│   ├── schemas.py             # Pydantic request/response models (input validation)
│   ├── security.py            # bcrypt hashing, JWT encode/decode, secret from env
│   └── db.py                 # SQLAlchemy engine/session (parameterized queries only)
├── tests/
│   └── test_auth.py          # basic happy-path + rejection tests
├── requirements.txt           # pinned, current, non-vulnerable versions
├── .env.example                # documents required env vars, no real secrets
├── Dockerfile                 # non-root user, pinned digest base image, minimal layers
├── docker-compose.yml          # no unnecessary port exposure, resource limits set
└── .github/workflows/ci.yml     # pinned action versions, least-privilege permissions block
```
(~9 files, ~420 LOC)

**Intentional security decisions (not vulnerabilities — the point of this repo):**

| Practice | Where |
|---|---|
| Parameterized queries exclusively (`session.query(User).filter(User.email == email)`, never string-built SQL) | `db.py`, `main.py` |
| Passwords hashed with bcrypt (`passlib.hash.bcrypt`), never stored/logged in plaintext | `security.py` |
| JWT secret loaded from `os.environ["JWT_SECRET"]` with no fallback/default — app refuses to start if unset | `security.py` |
| JWT signed with `HS256` explicitly (`jwt.decode(..., algorithms=["HS256"])`, no `"none"`/algorithm-confusion surface) | `security.py` |
| Pydantic schemas validate/constrain every input (email format, password min length) before it reaches business logic | `schemas.py` |
| `requirements.txt` pins current, non-vulnerable versions: `fastapi==0.115.0`, `pydantic==2.9.0`, `uvicorn==0.30.6`, `sqlalchemy==2.0.35`, `passlib[bcrypt]==1.7.4`, `pyjwt==2.9.0` | `requirements.txt` |
| Dockerfile: pinned `python:3.12.4-slim` base, `USER appuser` (non-root, UID 10001, created explicitly), `HEALTHCHECK`, no build tools in final stage (multi-stage build) | `Dockerfile` |
| `docker-compose.yml`: only the app's own port published, `read_only: true` root filesystem, explicit `mem_limit`/`cpus` | `docker-compose.yml` |
| GitHub Actions: every third-party action pinned to a full commit SHA (not `@v4`/`@main`), `permissions: contents: read` at workflow level (least privilege), no secrets echoed to logs | `.github/workflows/ci.yml` |

**Expected scanner findings:** **none.** Zero from every scanner — semgrep-fallback, OSV, pip-audit, secrets-scanner, docker-scanner, yaml-scanner, config-scanner all return empty. This is intentional and is itself a regression check: NOVA must not produce false positives against genuinely clean, idiomatic code.

**Expected severity counts:** 0 Critical / 0 High / 0 Medium / 0 Low.

**Expected CVEs / CWEs / OWASP / MITRE ATT&CK:** none applicable.

**Expected Banking Risk Score:** **0.0** (`rollup_scan_brs([])` on an empty finding list). Risk level: **Low**.

**Expected dashboard output:** repository card shows BRS 0.0, badge "Low," zero findings across all severity buckets, empty "Top Findings" panel, compliance panel shows 0 applicable clauses (nothing to map).

**Expected compliance impact:** none — no findings, no clauses triggered.

---

## 2. `NOVA-demo-low-risk`

**Purpose:** demonstrates a mostly-secure application with a handful of the small, easy-to-overlook mistakes real teams actually ship.

**Application type:** Employee portal REST API (FastAPI).

**Architecture:** FastAPI app serving employee directory/profile data internally; same secure-auth foundation as repo 1 (parameterized queries, bcrypt, env-based secrets) but with a few realistic gaps introduced deliberately, in non-auth-critical parts of the app.

**Folder structure:**
```
NOVA-demo-low-risk/
├── app/
│   ├── main.py               # FastAPI app: CSP/security-header gap lives here
│   ├── models.py
│   ├── schemas.py
│   ├── security.py            # same secure JWT/bcrypt approach as repo 1
│   └── db.py
├── requirements.txt            # one dependency one minor version behind
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/ci.yml
```
(~9 files, ~440 LOC)

**Intentional vulnerabilities:**

| # | Vulnerability | File | CWE | OWASP Top 10 (2021) | MITRE ATT&CK | Detected by |
|---|---|---|---|---|---|---|
| 1 | Missing security headers — no `Content-Security-Policy`, `X-Frame-Options`, or `X-Content-Type-Options` set on responses | `app/main.py` | CWE-1021 (Clickjacking / missing UI-restriction), CWE-693 | A05:2021 – Security Misconfiguration | T1189 (closest analog; client-side, not a classic enterprise technique) | config-scanner / semgrep-fallback (`security_misconfiguration`) |
| 2 | Outdated dependency with a real, low-severity advisory: `requests==2.31.0` (fixed in 2.32.0) | `requirements.txt` | CWE-295 (cert-verification weakness) | A06:2021 – Vulnerable and Outdated Components | T1588.006 | OSV / pip-audit — **CVE-2024-35195** |
| 3 | Application logs the authenticated user's email address at `INFO` level on every request (minor PII-in-logs issue, not a secret) | `app/main.py` (request-logging middleware) | CWE-532 (Insertion of Sensitive Information into Log File) | A09:2021 – Security Logging and Monitoring Failures | — | semgrep-fallback (`security_misconfiguration`) |
| 4 | Overly permissive CSP once introduced (`default-src *`) rather than none at all — kept as a *separate* finding from #1 to show "attempted but wrong" vs. "absent" | `app/main.py` | CWE-1021 | A05:2021 | — | config-scanner |
| 5 | Dockerfile: final image retains build toolchain (`build-essential`, `gcc`) instead of a multi-stage build — unnecessary attack surface, not a live exploit | `Dockerfile` | CWE-1120 (Excessive Code Complexity, closest: unnecessary attack surface — CWE-250 also applicable) | A05:2021 | — | docker-scanner |

**Expected scanner findings:** 4–5 total, sourced from `config-scanner` (2), `osv-scanner` (1, real CVE), `semgrep-fallback` (1), `docker-scanner` (1).

**Expected severity counts:** 0 Critical / 0 High / 0–1 Medium (the outdated-dependency CVE, depending on its real-world CVSS at scan time) / 3–4 Low.

**Expected CVEs:** `CVE-2024-35195` (requests — Session verify=False persists across requests after first use).

**Expected Banking Risk Score:** **≈ 38** (computed: two representative Low findings, General module, scored via the real engine → 38.27). Risk level label: **Medium** — see §0's note; this is the intended, correctly-ordered bottom of the achievable range, not a design error.

**Expected dashboard output:** BRS ~38, badge "Medium" (see note in §0 for why not "Low"), severity bar dominated by Low with a single Medium sliver, Top Findings panel led by the CSP/header gaps.

**Expected compliance impact:** `security_misconfiguration` and `vulnerable_dependency` findings each map to all three frameworks per `compliance_mappings.json` — RBI IT Framework 2021 §4.4/§6.6, PCI DSS v4.0 Req 2.2/6.3.3, SWIFT CSP Control 2.7/7.1. 2 unique RBI clauses, 2 unique PCI, 2 unique SWIFT expected.

---

## 3. `NOVA-demo-medium-risk`

**Purpose:** several genuine, independent developer mistakes accumulating in an otherwise-functional internal system — the profile most real unaudited internal tools actually match.

**Application type:** Inventory management system (Flask + a small Node.js reporting component, to exercise both `requirements.txt`/pip-audit and `package.json`/npm-audit-equivalent paths).

**Architecture:** Flask REST API for stock/orders; a small separate Node/Express service renders a nightly stock report (kept intentionally tiny — this is the repo's only JS/TS surface, to exercise Node-side dependency and pattern scanning without ballooning LOC).

**Design note (from §0):** every vulnerability below deliberately avoids the words `auth`, `login`, `jwt`, `session`, `token`, `password`, `credential`, `payment`, `transfer`, `customer`, `account` in file paths, titles, and descriptions — not because those bugs "don't happen" in an inventory system, but because this repo is specifically calibrated to land in the engine's actual Medium band (§0); the High and Critical repos are where auth/payment-path issues live instead.

**Folder structure:**
```
NOVA-demo-medium-risk/
├── app/
│   ├── main.py                 # Flask app factory, wildcard CORS lives here
│   ├── api/
│   │   ├── static_routes.py     # directory-listing misconfiguration
│   │   └── error_handlers.py    # verbose stack traces returned to client
│   ├── inventory/
│   │   └── order_ids.py         # predictable order-ID generator (random.random())
│   ├── services/
│   │   └── integrations/
│   │       └── signing.py       # weak, short signing secret for a partner webhook
│   ├── middleware/
│   │   └── logging.py           # logs full request body incl. sensitive fields
│   └── utils/
│       └── checksums.py         # SHA-1 used for a non-cryptographic integrity check
├── reporting-service/            # small Node component
│   ├── package.json              # outdated Flask sibling dependency represented via requirements.txt; this package.json carries its own realistic outdated dep
│   └── report.js
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/ci.yml
```
(~11 files, ~700 LOC)

**Intentional vulnerabilities:**

| # | Vulnerability | File | Severity (target) | CWE | OWASP Top 10 | MITRE ATT&CK | Detected by |
|---|---|---|---|---|---|---|---|
| 1 | Wildcard cross-origin policy on the public API (`Access-Control-Allow-Origin: *` with no origin allowlist) | `app/main.py` | Medium | CWE-942 | A05:2021 | T1190 | semgrep-fallback / config-scanner |
| 2 | Static file directory listing enabled on the uploads/reports folder (`Flask` static route with `autoindex`-equivalent misconfiguration) | `app/api/static_routes.py` | Medium | CWE-548 (Exposure of Information Through Directory Listing) | A05:2021 | T1083 | semgrep-fallback |
| 3 | Outdated Flask dependency with a real, disclosed DoS-class advisory: `Flask==2.2.3` (fixed in 2.2.5/2.3.2) | `requirements.txt` | Medium | CWE-613 (session-cookie related) | A06:2021 | T1588.006 | OSV / pip-audit — **CVE-2023-30861** |
| 4 | Verbose stack traces returned to the client on unhandled exceptions (`debug=True`-style error responses, not full framework debug mode) | `app/api/error_handlers.py` | Low | CWE-209 (Information Exposure Through Error Message) | A05:2021 | — | semgrep-fallback |
| 5 | Weak, short secret used to sign an outbound partner-webhook payload (`SECRET = "webhook123"`) | `app/services/integrations/signing.py` | Medium | CWE-326 (Inadequate Encryption Strength) | A02:2021 – Cryptographic Failures | T1552.001 | semgrep-fallback (`weak_cryptography`) |
| 6 | Predictable order-ID generator using `random.random()` instead of a CSPRNG — order IDs are guessable, enabling order enumeration | `app/inventory/order_ids.py` | Medium | CWE-330 (Use of Insufficiently Random Values) | A02:2021 | — | semgrep-fallback (`insecure_random`) |
| 7 | Full request body, including any sensitive fields submitted by the client, logged verbatim at `INFO` level | `app/middleware/logging.py` | Low | CWE-532 | A09:2021 | — | semgrep-fallback |
| 8 | SHA-1 used for a non-sensitive file-integrity checksum (not a password/token) | `app/utils/checksums.py` | Low | CWE-327 (Broken/Risky Cryptographic Algorithm) | A02:2021 | T1600 | semgrep-fallback (`weak_hash_sha1`) |
| 9 | Node reporting service pins an outdated `lodash` with a real, disclosed prototype-pollution advisory: `lodash==4.17.15` (patched fully at 4.17.21) | `reporting-service/package.json` | Medium | CWE-1321 (Prototype Pollution) | A06:2021 | T1588.006 | OSV — **CVE-2020-8203** |

**Expected scanner findings:** 8–9, sourced from `semgrep-fallback` (6), `osv-scanner` (2, both real CVEs), `config-scanner` (1, overlapping with #1's semgrep-fallback detection — expect the aggregation layer's file+line+category correlation to merge these into one unified finding, exercising dedup on a real case rather than a synthetic one).

**Expected severity counts:** 3 Low / 5 Medium / 0 High / 0 Critical — within the brief's originally-requested 3–6 Low / 3–5 Medium / 0–2 High / 0 Critical band.

**Expected CVEs:** `CVE-2023-30861` (Flask), `CVE-2020-8203` (lodash).

**Expected Banking Risk Score:** **≈ 54.25** (computed against the real engine with this exact finding set, all classifying to `General`/`Reporting` modules as intended). Risk level: **Medium** — matches intent exactly.

**Expected dashboard output:** BRS ~54, badge "Medium," severity bar roughly even between Low and Medium, Top Findings panel led by the CORS/directory-listing/weak-signing-secret trio, two real CVEs visible in the dependency panel.

**Expected compliance impact:** `security_misconfiguration` (6 findings), `weak_cryptography` (2), `vulnerable_dependency` (2), `insecure_random` (1) — each maps to all 3 frameworks; expect the compliance panel to show RBI §4.4/§5.3/§6.4/§6.6, PCI Req 2.2/3.5/4.2.1/6.3.3, SWIFT Controls 2.6/2.7/7.1/7.3 (unique-clause count driven by category diversity, not finding count).

---

## 4. `NOVA-demo-high-risk`

**Purpose:** multiple independently exploitable issues in a component that genuinely handles money — deliberately the first repo where business criticality (Payments module) legitimately amplifies the score, not an artifact.

**Application type:** Payment microservice (FastAPI, Python) with a small Node.js webhook-notification renderer (the repo's only client-facing HTML templating surface, and therefore the natural home for the one XSS finding).

**Architecture:** FastAPI service exposing transaction search, receipt download, and file upload endpoints under `app/payments/`; a Node/Express micro-component renders admin-facing transaction-note notifications from a template.

**Folder structure:**
```
NOVA-demo-high-risk/
├── app/
│   └── payments/
│       ├── api/
│       │   └── routes/
│       │       ├── transactions.py    # SQL injection (executed, real)
│       │       ├── receipts.py         # path traversal
│       │       └── upload.py            # unrestricted file upload
│       ├── auth/
│       │   └── token.py                # JWT verification disabled
│       ├── config/
│       │   └── settings.py               # hardcoded payment-gateway API key
│       └── services/
│           └── token_vault.py             # DES encryption for card reference tokens
├── webhook-notifier/                       # small Node component
│   ├── package.json
│   └── views.js                            # stored XSS (unescaped template render)
├── requirements.txt                         # outdated PyYAML with real CVE
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/ci.yml
```
(~12 files, ~950 LOC)

**Intentional vulnerabilities:**

| # | Vulnerability | File | Severity | CWE | OWASP Top 10 | MITRE ATT&CK | Detected by |
|---|---|---|---|---|---|---|---|
| 1 | SQL Injection in transaction search — query string built with an f-string from the `merchant_id` query parameter and passed directly to `cursor.execute()` (**executed**, unlike the prior sandbox's inert version) | `app/payments/api/routes/transactions.py` | High | CWE-89 | A03:2021 – Injection | T1190 | semgrep-fallback (`sql-injection-concat`) — **note: the current fallback regex requires `execute(...)`/`query(...)` with inline `+`/`%`; this finding's f-string must be concatenated immediately inside the call, not built on a prior line, to trip the existing pattern (documented explicitly so generation is unambiguous)** |
| 2 | Path Traversal in receipt download — `filename` query parameter joined directly into a filesystem path with no normalization/allowlist | `app/payments/api/routes/receipts.py` | High | CWE-22 | A01:2021 – Broken Access Control | T1083 | **requires semgrep/ast-grep installed** (fallback has no path-traversal rule — see §0/§7) |
| 3 | JWT verification disabled — `jwt.decode(token, options={"verify_signature": False})` used in production code path, not test code | `app/payments/auth/token.py` | High | CWE-347 (Improper Verification of Cryptographic Signature) | A07:2021 – Identification and Authentication Failures | T1556 | semgrep-fallback (`security_misconfiguration`) |
| 4 | Hardcoded payment-gateway API key (`STRIPE_SECRET_KEY = "sk_live_..."`-shaped literal) | `app/payments/config/settings.py` | High | CWE-798 | A07:2021 | T1552.001 | secrets-scanner |
| 5 | DES used to encrypt stored card-reference tokens | `app/payments/services/token_vault.py` | High | CWE-327 | A02:2021 | T1600 | **requires semgrep/ast-grep installed** (fallback has no weak-cipher-DES rule — see §0/§7); flagged as a design gap, not silently dropped |
| 6 | Unrestricted file upload on the receipt-attachment endpoint — no extension allowlist, no size limit, destination path built from the client-supplied filename | `app/payments/api/routes/upload.py` | High | CWE-434 (Unrestricted Upload of File with Dangerous Type) | A04:2021 – Insecure Design | T1105 | **requires semgrep/ast-grep installed** (shares the path-traversal gap above — filename-in-path is the detectable half; caught once that rule exists) |
| 7 | Outdated PyYAML with a real, disclosed RCE-class advisory: `PyYAML==5.3.1` (fixed in 5.4) | `requirements.txt` | High | CWE-502 | A08:2021 – Software and Data Integrity Failures | T1588.006 | OSV / pip-audit — **CVE-2020-14343** |
| 8 | Stored XSS — the transaction-note admin view renders a customer-supplied note field with a raw string-interpolation template instead of the templating engine's auto-escaping | `webhook-notifier/views.js` | Medium | CWE-79 | A03:2021 | T1189 (closest analog) | **requires semgrep/ast-grep installed** (no JS-side pattern in the current fallback's `PATTERN_RULES`, which is Python-oriented) |

**Expected scanner findings:** 8 total once semgrep/ast-grep are installed (per §0/§7); **3 of 8** (SQLi, hardcoded key, PyYAML CVE) are detectable **today** with the current fallback + OSV/secrets-scanner — the remaining 5 are correctly-written, real vulnerabilities that are explicitly documented as pending the scanner-coverage fix from the preceding audit, rather than silently omitted from the spec.

**Expected severity counts (once full tooling is installed):** several Low (implicit in surrounding code, e.g. verbose error handling — can be added if the generated repo wants exact parity with the brief's "several Low"), 1 Medium, 6 High, 0–1 Critical depending on final CVSS assigned to the SQLi at generation time (kept at High/CVSS 5.6–7.9 range in this spec's calibration to preserve separation from the Critical repo — see §0).

**Expected CVEs:** `CVE-2020-14343` (PyYAML).

**Expected Banking Risk Score:** **≈ 80.05** (computed against the real engine using the 7-finding subset above, all correctly classifying to the `Payments` module except the PyYAML CVE, which lands in `General` since `requirements.txt` alone doesn't carry a Payments keyword). Risk level: **High** — matches intent, comfortably under the Critical threshold (82) with headroom for scan-to-scan variance.

**Expected dashboard output:** BRS ~80, badge "High," severity bar dominated by High, Payments module correctly surfaced as the top business-risk driver in the module breakdown panel, secrets panel shows 1 CRITICAL-confidence hardcoded key.

**Expected compliance impact:** `sql_injection`, `hardcoded_secret`, `weak_cryptography`, `vulnerable_dependency`, `security_misconfiguration` categories present — expect all 3 frameworks represented with 4–5 unique clauses each (RBI §4.2/§5.3/§6.4/§6.6, PCI Req 3.4/4.2.1/6.2/6.3.3/8.2, SWIFT Controls 2.6/4.1/6.1/7.1/7.2/7.3).

---

## 5. `NOVA-demo-critical-risk`

**Purpose:** the "everything wrong at once" reference — a legacy core banking backend nobody has audited in years. This is the repo that should make any reasonable reviewer say "do not deploy this."

**Application type:** Core banking backend (Flask), with committed Kubernetes manifests and a GitHub Actions workflow that has its own independent critical findings.

**Architecture:** Flask REST API for account balance/transfer/search operations, an admin diagnostics endpoint, an FX-rate lookup endpoint, deployed via a committed (not template) Kubernetes Deployment manifest and a CI workflow with dangerous trigger/permission configuration.

**Folder structure:**
```
NOVA-demo-critical-risk/
├── app/
│   ├── core/
│   │   └── config.py               # hardcoded DB password, AWS key, debug=True
│   ├── auth/
│   │   ├── jwt_handler.py            # hardcoded JWT secret + admin-bypass logic
│   │   └── password.py                # MD5 password hashing
│   └── api/
│       └── routes/
│           ├── transfer.py             # SQL injection (executed) — balance transfer
│           ├── accounts.py              # SQL injection (executed) — account search; also IDOR
│           ├── admin_diagnostics.py       # RCE via os.system()
│           ├── fx_rates.py                 # SSRF (arbitrary outbound URL, no allowlist)
│           ├── users.py                     # privilege escalation via mass-assignment
│           ├── session.py                    # unsafe pickle deserialization
│           └── documents.py                    # directory listing enabled
├── certs/
│   └── service.pem                     # committed private key
├── .env                                  # committed, production-shaped secrets
├── requirements.txt                       # multiple real, old, critical-CVE dependencies
├── package.json                            # old lodash, real critical CVE
├── Dockerfile                                # root user, privileged
├── docker-compose.yml                         # privileged: true, no user namespace
├── k8s/
│   └── deployment.yaml                          # privileged, runAsUser 0, hostNetwork
└── .github/workflows/ci.yml                       # pull_request_target + untrusted checkout
```
(~16 files, ~1150 LOC — at the top of the stated budget, appropriate for "many" findings across every category)

**Intentional vulnerabilities:**

| # | Vulnerability | File | Severity | CWE | OWASP Top 10 | MITRE ATT&CK | Detected by |
|---|---|---|---|---|---|---|---|
| 1 | Hardcoded production database password | `app/core/config.py` | Critical | CWE-798 | A07:2021 | T1552.001 | secrets-scanner |
| 2 | Hardcoded AWS access key | `app/core/config.py` | Critical | CWE-798 | A07:2021 | T1552.001 | secrets-scanner |
| 3 | Committed `.env` with production-shaped secrets | `.env` | Critical | CWE-798, CWE-312 | A07:2021 | T1552.001 | secrets-scanner |
| 4 | Committed PEM private key | `certs/service.pem` | Critical | CWE-798, CWE-312 | A07:2021 | T1552.001 | secrets-scanner |
| 5 | SQL Injection in balance-transfer endpoint (executed) | `app/api/routes/transfer.py` | Critical | CWE-89 | A03:2021 | T1190 | semgrep-fallback |
| 6 | SQL Injection in account search (executed) | `app/api/routes/accounts.py` | Critical | CWE-89 | A03:2021 | T1190 | semgrep-fallback |
| 7 | Remote Command Execution — `os.system(f"ping -c 1 {host}")` in an admin diagnostics endpoint, `host` taken directly from request input | `app/api/routes/admin_diagnostics.py` | Critical | CWE-78 | A03:2021 | T1059 | semgrep-fallback (`os-system`) |
| 8 | SSRF — FX-rate endpoint fetches an arbitrary caller-supplied URL server-side with no allowlist/deny-list | `app/api/routes/fx_rates.py` | Critical | CWE-918 | A10:2021 – Server-Side Request Forgery | T1090 / T1552.005 (if pointed at cloud metadata) | **requires semgrep/ast-grep installed** — flagged, not silently dropped |
| 9 | Hardcoded JWT signing secret combined with an explicit admin-role bypass (`if username == "admin": return {"role": "admin"}` short-circuit ahead of real auth) | `app/auth/jwt_handler.py` | Critical | CWE-798, CWE-287 | A07:2021 | T1078 | secrets-scanner + semgrep-fallback |
| 10 | IDOR — `account/{id}` endpoint returns any account's data with no ownership/role check against the caller | `app/api/routes/accounts.py` | High | CWE-639 | A01:2021 | T1078 | **requires semgrep/ast-grep or Joern installed** (cross-file authorization-logic detection) |
| 11 | Privilege escalation — user-profile update endpoint accepts and applies a client-supplied `role` field with no server-side restriction (mass assignment) | `app/api/routes/users.py` | High | CWE-269 | A01:2021 | T1068 | **requires semgrep/ast-grep installed** |
| 12 | Very old Flask with multiple disclosed critical-class CVEs: `Flask==2.2.3` | `requirements.txt` | Critical | CWE-613 | A06:2021 | T1588.006 | OSV / pip-audit — **CVE-2023-30861** |
| 13 | Very old PyYAML, `full_load`-class RCE: `PyYAML==5.3.1` | `requirements.txt` | Critical | CWE-502 | A08:2021 | T1588.006 | OSV / pip-audit — **CVE-2020-14343** |
| 14 | Very old lodash prototype pollution: `lodash==4.17.11` | `package.json` | Critical | CWE-1321 | A06:2021 | T1588.006 | OSV — **CVE-2019-10744** |
| 15 | Docker container runs as root; `docker-compose.yml` sets `privileged: true` | `Dockerfile`, `docker-compose.yml` | Critical | CWE-250 | A05:2021 | T1611 (Escape to Host) | docker-scanner |
| 16 | GitHub Actions workflow triggers on `pull_request_target` while checking out the PR head ref and running arbitrary `npm install`/build scripts from it — classic fork-PR secret-exfiltration/RCE pattern | `.github/workflows/ci.yml` | Critical | CWE-829 | A08:2021 | T1195.002 (Supply Chain Compromise: Software Supply Chain) | config-scanner / yaml-scanner |
| 17 | Kubernetes Deployment: `securityContext.privileged: true`, `runAsUser: 0`, `hostNetwork: true`, no resource limits, no `readOnlyRootFilesystem` | `k8s/deployment.yaml` | Critical | CWE-250, CWE-732 | A05:2021 | T1611 | yaml-scanner |
| 18 | MD5 used for password hashing | `app/auth/password.py` | High | CWE-327, CWE-916 (weak password hash) | A02:2021 | T1600 | semgrep-fallback (`weak-hash-md5`) |
| 19 | Unsafe `pickle.loads()` on session data sourced from a client-supplied cookie | `app/api/routes/session.py` | High | CWE-502 | A08:2021 | T1190 | semgrep-fallback (`unsafe-pickle`) |
| 20 | Directory listing enabled on the document store | `app/api/routes/documents.py` | Medium | CWE-548 | A05:2021 | T1083 | semgrep-fallback |
| 21 | `DEBUG=true` / verbose debug mode enabled in a config file that is otherwise clearly production-shaped | `app/core/config.py` | Medium | CWE-489 (Active Debug Code) | A05:2021 | — | config-scanner |

**Expected scanner findings:** 21 designed, of which **16 are detectable today** with the current toolchain (secrets-scanner, OSV/pip-audit, docker-scanner, yaml-scanner, config-scanner, semgrep-fallback's existing 10 patterns cover SQLi/RCE/MD5/pickle/JWT-secret directly); **5 require semgrep/ast-grep/Joern** (SSRF, IDOR, privilege escalation) per the same, already-flagged coverage gap from the preceding audit.

**Expected severity counts:** many Low (implicit in surrounding boilerplate, can be padded to match "many Low" exactly at generation time without changing intent) / 2 Medium / 4 High / 15 Critical — exceeds the brief's "several Critical," which is appropriate for the repo whose entire purpose is demonstrating uncontrolled accumulation.

**Expected CVEs:** `CVE-2023-30861` (Flask), `CVE-2020-14343` (PyYAML), `CVE-2019-10744` (lodash).

**Expected Banking Risk Score:** **≈ 92.65** (computed against the real engine with this exact 21-finding set — the highest-scoring individual finding, the balance-transfer SQL injection classified into `Payments`, sets the floor at ~92.65 via `rollup_scan_brs`'s `max()` term; the self-weighted-average term is close behind given the sheer density of Critical findings). Risk level: **Critical** — matches intent exactly, with clear separation from the High repo (~80).

**Expected dashboard output:** BRS ~93, badge "Critical," severity bar dominated by Critical/High, secrets panel shows 4 distinct hardcoded-credential findings, dependency panel shows 3 real critical CVEs, infrastructure panel flags Docker/K8s/CI misconfiguration simultaneously — this repo is designed to exercise every dashboard panel NOVA has at once.

**Expected compliance impact:** every category in `compliance_mappings.json` is represented at least once; expect all 3 frameworks fully populated — RBI IT Framework 2021 (all 6 listed sections), PCI DSS v4.0 (Req 2.2, 3.4, 3.5, 4.2.1, 6.2, 6.2.4, 6.3.1, 6.3.3, 8.2, 12.8), SWIFT CSP (Controls 1.1, 2.6, 2.7, 3.1, 3.2, 4.1, 4.2, 6.1, 7.1, 7.2, 7.3) — this repo is the regression check that the compliance mapper's full breadth actually gets exercised, which none of the old sandbox repos did.

---

## 6. Cross-Repository Summary Table

| Repo | App type | Findings (L/M/H/C) | Real CVEs | Modules hit | BRS (simulated) | Risk label |
|---|---|---|---|---|---|---|
| very-low-risk | Auth service | 0/0/0/0 | — | — | **0.0** | Low |
| low-risk | Employee portal | 3-4/0-1/0/0 | CVE-2024-35195 | General | **~38** | Medium* |
| medium-risk | Inventory system | 3/5/0/0 | CVE-2023-30861, CVE-2020-8203 | General, Reporting | **~54** | Medium |
| high-risk | Payment microservice | –/1/6/0-1 | CVE-2020-14343 | Payments, General | **~80** | High |
| critical-risk | Core banking backend | many/2/4/15 | CVE-2023-30861, CVE-2020-14343, CVE-2019-10744 | Payments, Authentication, Customer Data, Admin, Infrastructure, General | **~93** | Critical |

*low-risk's label is "Medium" purely due to the engine floor described in §0 — numerically and ordinally still correctly the lowest non-empty repo.

---

## 7. Recommended Follow-ups (explicitly out of scope for this spec)

1. **Install semgrep, ast-grep, and Joern** in the deployment environment — this spec identifies 8 findings across the High and Critical repos (path traversal, unrestricted upload, DES weak cipher, stored XSS, SSRF, IDOR, privilege escalation) that are real, correctly-written vulnerabilities but are only detectable once those three tools are actually running, not via the current regex fallback.
2. **Extend `PATTERN_RULES`** in `static_scanner.py` with path-traversal, insecure-random-as-security-token, and weak-cipher-DES entries — a smaller, faster partial fix than #1 that would immediately close 3 of the 8 gaps above.
3. **Revisit `_calculate_risk_level()`'s thresholds** once this suite's real scan results are in hand — this spec's §0 finding (any non-empty scan floors around BRS 32–36, so "Low" is practically unreachable with 1+ findings) is a discrete-label question, separate from the BRS *number* itself, which was explicitly out of scope for today's redesign task.
4. Once repositories 1–5 are generated and scanned for real, re-run this same calibration simulation against the *actual* persisted findings (not the representative set used here) to confirm the real pipeline reproduces these numbers — the same "verify for real" step applied throughout the preceding BRS audit.
