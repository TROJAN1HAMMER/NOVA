"""
NOVA — Unit & Integration Tests for Scanner Adapters
Tests all 9 scanner adapters and their fallback mechanisms against synthetic codebases and benchmark suites.
"""

import os
import tempfile
from pathlib import Path

import pytest

from app.scanners import (
    AstGrepScanner,
    DockerScanner,
    JoernScanner,
    NvdScanner,
    OsvScanner,
    PipAuditScanner,
    SecretsScanner,
    SemgrepScanner,
    YamlScanner,
    get_all_scanners,
    get_scanner,
    run_all_scanners,
)


@pytest.fixture
def temp_repo():
    """Create a temporary directory for test code fixtures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ── 1. Semgrep Scanner Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_semgrep_scanner_detects_sqli_and_os_system(temp_repo):
    vuln_file = temp_repo / "app" / "api.py"
    vuln_file.parent.mkdir(parents=True, exist_ok=True)
    vuln_file.write_text(
        'import os, sqlite3\n\n'
        'def get_user(user_id):\n'
        '    cursor = sqlite3.connect("db.sqlite").cursor()\n'
        '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        '    os.system(f"echo Accessed {user_id}")\n',
        encoding="utf-8",
    )

    scanner = SemgrepScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "semgrep"
    assert res["success"] is True
    findings = res["findings"]
    categories = [f["category"] for f in findings]
    assert "sql_injection" in categories
    assert "command_injection" in categories


@pytest.mark.asyncio
async def test_semgrep_scanner_detects_weak_crypto_and_pickle(temp_repo):
    vuln_file = temp_repo / "app" / "utils.py"
    vuln_file.parent.mkdir(parents=True, exist_ok=True)
    vuln_file.write_text(
        'import hashlib, pickle\n\n'
        'def hash_pass(pwd):\n'
        '    return hashlib.md5(pwd.encode()).hexdigest()\n\n'
        'def load_state(data):\n'
        '    return pickle.loads(data)\n',
        encoding="utf-8",
    )

    scanner = SemgrepScanner()
    res = await scanner.scan(temp_repo)
    findings = res["findings"]
    categories = [f["category"] for f in findings]
    assert "weak_cryptography" in categories
    assert "unsafe_deserialization" in categories


@pytest.mark.asyncio
async def test_semgrep_scanner_clean_repo_yields_zero_findings(temp_repo):
    clean_file = temp_repo / "app" / "clean.py"
    clean_file.parent.mkdir(parents=True, exist_ok=True)
    clean_file.write_text(
        'def add(a: int, b: int) -> int:\n'
        '    return a + b\n',
        encoding="utf-8",
    )

    scanner = SemgrepScanner()
    res = await scanner.scan(temp_repo)
    assert res["success"] is True
    assert len(res["findings"]) == 0


# ── 2. ast-grep Scanner Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ast_grep_scanner_detects_unrestricted_upload(temp_repo):
    vuln_file = temp_repo / "app" / "upload.py"
    vuln_file.parent.mkdir(parents=True, exist_ok=True)
    vuln_file.write_text(
        'import os\n'
        'def handle_upload(file):\n'
        '    with open(f"/uploads/{file.filename}", "wb") as f:\n'
        '        f.write(file.read())\n',
        encoding="utf-8",
    )

    scanner = AstGrepScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "ast-grep"
    assert res["success"] is True
    assert len(res["findings"]) >= 1
    assert any("upload" in f["title"].lower() for f in res["findings"])


# ── 3. Joern Scanner Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_joern_scanner_handles_unavailable_cli_gracefully(temp_repo):
    scanner = JoernScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "joern"
    # When Joern is not installed, it gracefully returns success=False without crashing
    assert res["success"] is False
    assert res["findings"] == []
    assert "not installed" in res.get("error", "").lower()


# ── 4. pip-audit Scanner Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pip_audit_scanner_detects_vulnerable_requirements(temp_repo):
    req_file = temp_repo / "requirements.txt"
    req_file.write_text(
        "flask==2.2.3\n"
        "pyyaml==5.3.1\n"
        "requests==2.31.0\n",
        encoding="utf-8",
    )

    scanner = PipAuditScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "pip-audit"
    assert res["success"] is True
    findings = res["findings"]
    cves = [f.get("cve") for f in findings]
    assert "CVE-2023-30861" in cves  # Flask
    assert "CVE-2020-14343" in cves  # PyYAML
    assert "CVE-2024-35195" in cves  # requests


@pytest.mark.asyncio
async def test_pip_audit_scanner_clean_requirements(temp_repo):
    req_file = temp_repo / "requirements.txt"
    req_file.write_text(
        "fastapi==0.115.0\n"
        "pydantic==2.9.0\n"
        "uvicorn==0.30.6\n",
        encoding="utf-8",
    )

    scanner = PipAuditScanner()
    res = await scanner.scan(temp_repo)
    assert res["success"] is True
    assert len(res["findings"]) == 0


# ── 5. OSV Scanner Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_osv_scanner_detects_node_lodash_vulnerability(temp_repo):
    pkg_json = temp_repo / "package.json"
    pkg_json.write_text(
        '{\n'
        '  "name": "demo-app",\n'
        '  "dependencies": {\n'
        '    "lodash": "4.17.11"\n'
        '  }\n'
        '}\n',
        encoding="utf-8",
    )

    scanner = OsvScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "osv"
    assert res["success"] is True
    findings = res["findings"]
    assert any(f.get("cve") == "CVE-2019-10744" for f in findings)


# ── 6. NVD Scanner Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nvd_scanner_basic(temp_repo):
    scanner = NvdScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "nvd"
    assert res["success"] is True
    assert isinstance(res["findings"], list)


# ── 7. Secrets Scanner Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_secrets_scanner_detects_aws_keys_and_pem_certs(temp_repo):
    conf_file = temp_repo / "app" / "config.py"
    conf_file.parent.mkdir(parents=True, exist_ok=True)
    conf_file.write_text(
        'AWS_KEY = "AKIA1111222233334444"\n'
        'STRIPE_KEY = "sk_live_1234567890abcdef1234567890abcdef"\n'
        'DATABASE_URL = "postgres://postgres:supersecretpassword@localhost:5432/nova"\n',
        encoding="utf-8",
    )

    cert_file = temp_repo / "certs" / "service.pem"
    cert_file.parent.mkdir(parents=True, exist_ok=True)
    cert_file.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )

    scanner = SecretsScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "secrets"
    assert res["success"] is True
    findings = res["findings"]
    titles = [f["title"] for f in findings]
    assert any("AWS" in t for t in titles)
    assert any("Private key" in t for t in titles)
    assert any("database password" in t.lower() for t in titles)


# ── 8. Docker Scanner Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_docker_scanner_detects_root_user_and_privileged_compose(temp_repo):
    dockerfile = temp_repo / "Dockerfile"
    dockerfile.write_text(
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
        "USER root\n"
        "CMD [\"python\", \"main.py\"]\n",
        encoding="utf-8",
    )

    compose = temp_repo / "docker-compose.yml"
    compose.write_text(
        "services:\n"
        "  app:\n"
        "    build: .\n"
        "    privileged: true\n",
        encoding="utf-8",
    )

    scanner = DockerScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "docker"
    assert res["success"] is True
    findings = res["findings"]
    assert any("root" in f["title"].lower() for f in findings)
    assert any("privileged" in f["title"].lower() for f in findings)


# ── 9. YAML Scanner Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_yaml_scanner_detects_pull_request_target_and_k8s_root(temp_repo):
    ci_file = temp_repo / ".github" / "workflows" / "ci.yml"
    ci_file.parent.mkdir(parents=True, exist_ok=True)
    ci_file.write_text(
        "name: CI\n"
        "on:\n"
        "  pull_request_target:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )

    k8s_file = temp_repo / "k8s" / "deployment.yaml"
    k8s_file.parent.mkdir(parents=True, exist_ok=True)
    k8s_file.write_text(
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      hostNetwork: true\n"
        "      securityContext:\n"
        "        privileged: true\n"
        "        runAsUser: 0\n",
        encoding="utf-8",
    )

    scanner = YamlScanner()
    res = await scanner.scan(temp_repo)
    assert res["scanner"] == "yaml"
    assert res["success"] is True
    findings = res["findings"]
    titles = [f["title"] for f in findings]
    assert any("pull_request_target" in t for t in titles)
    assert any("unpinned" in t.lower() for t in titles)
    assert any("runAsUser: 0" in t for t in titles)
    assert any("hostNetwork" in t for t in titles)


# ── 10. Registry & Parallel Scan Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_scanner_registry_and_run_all_scanners(temp_repo):
    all_scanners = get_all_scanners()
    assert len(all_scanners) == 9

    semgrep = get_scanner("semgrep")
    assert isinstance(semgrep, SemgrepScanner)

    with pytest.raises(ValueError):
        get_scanner("non_existent_scanner")

    results = await run_all_scanners(temp_repo)
    assert len(results) == 9
    scanner_names = {r["scanner"] for r in results}
    assert scanner_names == {"semgrep", "ast-grep", "joern", "pip-audit", "osv", "nvd", "secrets", "docker", "yaml"}


# ── 11. Benchmark Suite Payloads Integration ──────────────────────────────────


@pytest.mark.asyncio
async def test_scanners_against_benchmark_very_low_risk(temp_repo):
    from app.utils.payload_generator import VERY_LOW_RISK_FILES

    for fpath, content in VERY_LOW_RISK_FILES.items():
        dst = temp_repo / fpath
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")

    results = await run_all_scanners(temp_repo)
    # The clean repo should produce 0 security findings across all scanners
    total_findings = sum(len(r["findings"]) for r in results)
    assert total_findings == 0, f"Expected 0 findings in very-low-risk, got {total_findings}"


@pytest.mark.asyncio
async def test_scanners_against_benchmark_critical_risk(temp_repo):
    from app.utils.payload_generator import CRITICAL_RISK_FILES
    from app.services.aggregation.aggregator import aggregate_scanner_results

    for fpath, content in CRITICAL_RISK_FILES.items():
        dst = temp_repo / fpath
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")

    results = await run_all_scanners(temp_repo)
    findings, severity_counts, scan_brs, scan_risk_level, compliance_summary = aggregate_scanner_results(results)

    assert len(findings) >= 15
    assert severity_counts["CRITICAL"] >= 8
    assert severity_counts["HIGH"] >= 3
    assert scan_brs > 0.0
    assert compliance_summary is not None
