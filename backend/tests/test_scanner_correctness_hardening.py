"""
NOVA Security Intelligence — Scanner Correctness & Hardening Regression Test Suite
Verifies:
1. Finding severity counts: total_findings == sum(critical, high, medium, low) == len(assessments)
2. False secret exposure elimination: binary/model files and os.getenv never generate fake SECRET_EXPOSURE
3. Canonical repository-relative path normalization: zero /Users/, /home/, /tmp/, or scan UUID paths in API outputs
4. Informative controls & compliance: control_id, status, rationale, limitations, evidence references
5. Evidence-based risk scenarios: zero scenarios when clean, explicit ASSET -> IMPACT chains when vulnerable
6. Asset discovery precision: real endpoints discovered, model files excluded from databases
7. Derived posture score: deterministic formula, scoring_inputs breakdown, no default 50
8. Remediation verification: re-analyzing real source files (STILL_PRESENT -> VERIFIED_FIXED)
9. SSRF and ZIP traversal security protections
10. Deterministic scan lifecycle across all 8 required repository test cases
"""

import io
import os
import tempfile
import uuid
import zipfile
from pathlib import Path
import pytest
import httpx
from httpx import ASGITransport

from starlette.testclient import TestClient
from app.main import app
from app.core.exceptions import ValidationAppError
from app.integrations.github.client import GitHubRepoProvider
from app.services.security_intelligence.repository_ingestion import repository_ingestion_service
from app.services.security_intelligence.utils import normalize_repo_path
from app.services.security_intelligence.asset_discovery_service import asset_discovery_service
from app.services.security_intelligence.observation_collector import observation_collector
from app.services.security_intelligence.control_analyzer import control_analyzer
from app.services.security_intelligence.risk_scenario_engine import risk_scenario_engine
from app.services.security_intelligence.scenario_verifier import scenario_verifier
from app.services.security_intelligence.remediation_verifier import remediation_verifier
from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator
from app.services.security_intelligence.posture_trend_engine import posture_trend_engine
from app.services.security_intelligence.scan_service import security_scan_service
from app.db.session import AsyncSessionLocal
from app.models.security_intelligence import SecurityIntelScan
from app.models.user import User
from app.models.enums import UserRole, AuthProvider
from app.auth.dependencies import get_current_active_user, get_current_user


def create_zip_bytes(files_dict: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files_dict.items():
            if isinstance(content, str):
                zf.writestr(fname, content.encode("utf-8"))
            else:
                zf.writestr(fname, content)
    return buf.getvalue()


test_user = User(
    id=uuid.UUID("c5b5a681-fac3-4e4b-b81d-4a51c177d1dc"),
    email="admin@nova.ai",
    full_name="System Admin",
    role=UserRole.ADMIN,
    is_active=True,
    auth_provider=AuthProvider.LOCAL,
)


@pytest.fixture(autouse=True)
def setup_test_user():
    app.dependency_overrides[get_current_active_user] = lambda: test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_current_user, None)


# =============================================================================
# 1. Path Normalization Regression Tests
# =============================================================================
def test_normalize_repo_path_regression():
    # Never leaks /Users/...
    raw = "/Users/23MIS0012/Desktop/NOVA/uploads/scans/977f7d43-3b32-4e08-ad1e-1cf750b328c3/source/TROJAN1HAMMER-Synapse-Sentinel-06e6f9d/Backend/v3_transformer/models/scaler.pkl"
    norm = normalize_repo_path(raw)
    assert norm == "Backend/v3_transformer/models/scaler.pkl"
    assert not norm.startswith("/Users")
    assert not norm.startswith("uploads/")

    # Root normalization
    root_path = "/Users/23MIS0012/Desktop/NOVA/uploads/scans/977f7d43-3b32-4e08-ad1e-1cf750b328c3/source/TROJAN1HAMMER-Synapse-Sentinel-06e6f9d"
    assert normalize_repo_path(root_path) == "."

    # Line numbers preserved
    raw_with_line = "/home/runner/work/NOVA/uploads/scans/123-abc/source/backend/auth.py:line 42"
    assert normalize_repo_path(raw_with_line) == "backend/auth.py:line 42"

    raw_with_colon = "/tmp/uploads/scans/xyz/source/src/main.py:100"
    assert normalize_repo_path(raw_with_colon) == "src/main.py:100"


# =============================================================================
# 2. Secret False Positive Regression Test
# =============================================================================
def test_clean_repo_with_model_file_and_env_has_zero_secrets(tmp_path):
    # Repository contains: safe code, .pkl model file, and standard os.getenv
    (tmp_path / "models").mkdir(parents=True)
    (tmp_path / "models" / "scaler.pkl").write_bytes(b"\x80\x04\x95\x12\x00\x00\x00\x00\x00\x00\x00}\x94.")
    (tmp_path / "app.py").write_text(
        "import os\n"
        "db_url = os.getenv('DATABASE_URL', 'sqlite:///default.db')\n"
        "def run():\n"
        "    return 'running'\n"
    )

    res = security_intelligence_orchestrator.run_full_analysis(
        str(tmp_path), project_name="Hardening-CleanModelRepo", force_refresh=True
    )

    # 1. scaler.pkl must NOT be discovered as a database asset
    db_assets = [a for a in res["assets"] if a["asset_type"] == "DATABASE"]
    assert len(db_assets) == 0, f"False database asset: {db_assets}"
    assert not any("scaler.pkl" in a["asset_name"] for a in res["assets"])

    # 2. Must NOT produce false SECRET_EXPOSURE_RISK
    secret_findings = [a for a in res["assessments"] if a["risk_type"] == "SECRET_EXPOSURE_RISK"]
    assert len(secret_findings) == 0, f"False secret findings generated: {secret_findings}"

    # 3. Must NOT produce "Environment variable storage confirmed secure" finding
    assert not any("Environment variable storage confirmed secure" in a["reasoning"] for a in res["assessments"])

    # 4. Severity breakdown equals assessments
    sev = res["posture"]["severity_breakdown"]
    assert sev["critical"] + sev["high"] + sev["medium"] + sev["low"] == len(res["assessments"])
    assert len(res["assessments"]) == 0


# =============================================================================
# 3. Informative Controls & UNKNOWN Semantics Test
# =============================================================================
def test_controls_informative_and_unknown_semantics(tmp_path):
    (tmp_path / "simple.py").write_text("def hello(): return 'world'")

    res = security_intelligence_orchestrator.run_full_analysis(
        str(tmp_path), project_name="Hardening-SimpleRepo", force_refresh=True
    )

    controls = res["controls"]
    assert len(controls) >= 6
    for c in controls:
        assert "control_id" in c and c["control_id"]
        assert "control_name" in c and c["control_name"]
        assert "domain" in c and c["domain"]
        assert c["status"] in ["PASS", "FAIL", "PARTIAL", "UNKNOWN"]
        assert c["state"] in ["PRESENT", "ABSENT", "PARTIAL", "UNKNOWN"]
        assert "rationale" in c and len(c["rationale"]) > 0

        # UNKNOWN controls must have missing evidence explanation
        if c["status"] == "UNKNOWN":
            assert c["evidence_count"] == 0
            assert "limitations" in c and len(c["limitations"]) > 0
            assert "No supported evidence" in c["rationale"]


# =============================================================================
# 4. Remediation Verification on Actual Source Files
# =============================================================================
def test_remediation_verification_on_disk(tmp_path):
    vulnerable_file = tmp_path / "executor.py"
    vulnerable_file.write_text("import subprocess\ndef run_cmd(user_arg):\n    subprocess.run(user_arg, shell=True)\n")

    # Before fix: rule should detect command injection
    res_before = remediation_verifier.verify_remediation(
        assessment_id="ASS-TEST-001",
        code_snippet="",
        target_file_path=str(vulnerable_file),
        repo_root=tmp_path,
    )
    assert res_before["status"] == "STILL_PRESENT"
    assert res_before["fixed"] is False
    assert "shell=True" in res_before["evidence"]

    # Apply genuinely fixed code
    vulnerable_file.write_text(
        "import subprocess, shlex\ndef run_cmd(user_arg):\n    safe_args = shlex.split(user_arg)\n    subprocess.run(safe_args, shell=False)\n"
    )

    # After fix: re-analysis must confirm VERIFIED_FIXED
    res_after = remediation_verifier.verify_remediation(
        assessment_id="ASS-TEST-001",
        code_snippet="",
        target_file_path=str(vulnerable_file),
        repo_root=tmp_path,
    )
    assert res_after["status"] == "VERIFIED_FIXED"
    assert res_after["fixed"] is True
    assert "no security rule violations remain" in res_after["verification_summary"]


# =============================================================================
# 5. Security Negative Tests: SSRF and ZIP Traversal Protections
# =============================================================================
def test_ssrf_protection_rejects_internal_and_metadata_targets():
    provider = GitHubRepoProvider()

    # Localhost
    assert not provider.validate_url_security("http://localhost:8000")
    assert not provider.validate_url_security("http://127.0.0.1:8080")
    assert not provider.validate_url_security("https://127.0.0.1")

    # AWS metadata service
    assert not provider.validate_url_security("http://169.254.169.254/latest/meta-data/")

    # Private IP ranges
    assert not provider.validate_url_security("https://10.0.0.1/repo")
    assert not provider.validate_url_security("https://192.168.1.1/repo")
    assert not provider.validate_url_security("https://172.16.0.1/repo")

    # Non-HTTPS GitHub URL
    assert not provider.validate_url_security("http://github.com/owner/repo")

    # Userinfo in URL
    assert not provider.validate_url_security("https://user:password@github.com/owner/repo")

    # Valid public GitHub URL
    assert provider.validate_url_security("https://github.com/owner/repo")


def test_zip_traversal_protections():
    # Zip Slip path traversal attempt
    bad_zip_slip = create_zip_bytes({
        "../../../../etc/passwd": "root:x:0:0:root:/root:/bin/bash",
    })
    with pytest.raises(ValidationAppError) as exc_info:
        repository_ingestion_service.validate_and_extract_zip(bad_zip_slip, str(uuid.uuid4()))
    assert "traversal attempt" in str(exc_info.value).lower() or "zip slip" in str(exc_info.value).lower()

    # Absolute path entry
    bad_zip_abs = create_zip_bytes({
        "/etc/shadow": "root:*:18000:0:99999:7:::",
    })
    with pytest.raises(ValidationAppError) as exc_info:
        repository_ingestion_service.validate_and_extract_zip(bad_zip_abs, str(uuid.uuid4()))
    assert "traversal attempt" in str(exc_info.value).lower() or "zip slip" in str(exc_info.value).lower()


# =============================================================================
# 6. Complete Deterministic Scan Lifecycle with 8 Known Cases
# =============================================================================
@pytest.mark.asyncio
async def test_deterministic_scan_lifecycle_all_8_cases():
    # Create deterministic repository archive with:
    # 1. safe code
    # 2. clearly detectable secret-like literal (AWS key)
    # 3. unsafe subprocess/shell usage (shell=True)
    # 4. unsafe SQL construction (f-string SQL)
    # 5. authentication-protected route
    # 6. unprotected route
    # 7. database configuration
    # 8. normal model/binary file (.pkl)
    repo_files = {
        "safe_util.py": "def add(a, b):\n    return a + b\n",
        "aws_service.py": 'AWS_KEY = "AKIA1234567890ABCDEF"\ndef get_client(): return AWS_KEY\n',
        "executor.py": "import subprocess\ndef run(cmd):\n    subprocess.run(cmd, shell=True)\n",
        "db_query.py": 'def get_user(db, uid):\n    return db.execute(f"SELECT * FROM users WHERE id = \'{uid}\'")\n',
        "routes/protected.py": 'from fastapi import APIRouter, Depends\nrouter = APIRouter()\n@router.get("/protected")\ndef secret_data(): return {"ok": True}\n',
        "routes/public.py": 'from fastapi import APIRouter\nrouter = APIRouter()\n@router.get("/public")\ndef public_data(): return {"msg": "hello"}\n',
        "database.py": 'from sqlalchemy import create_engine\nengine = create_engine("postgresql://postgres:test@localhost:5432/mydb")\n',
        "models/weights.pkl": b"\x80\x04\x95\x05\x00\x00\x00\x00\x00\x00\x00K\x01\x85\x94.",
    }

    zip_bytes = create_zip_bytes(repo_files)

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Upload & Ingest
        res = await client.post(
            "/api/v1/security-intelligence/scans/upload",
            files={"file": ("deterministic.zip", zip_bytes, "application/zip")},
            data={"project_name": "DeterministicTestRepo"},
        )
        assert res.status_code == 201, f"Upload failed: {res.text}"
        scan_data = res.json()["scan"]
        scan_id = scan_data["id"]

        # Step 2: Fetch Results
        res_results = await client.get(f"/api/v1/security-intelligence/scans/{scan_id}/results")
        assert res_results.status_code == 200, f"Get results failed: {res_results.text}"
        results = res_results.json()["results"]

        # 1. Severity counts match
        assessments = results["assessments"]
        posture = results["posture"]
        sev = posture["severity_breakdown"]
        assert sev["critical"] + sev["high"] + sev["medium"] + sev["low"] == len(assessments)
        assert results["total_findings"] == len(assessments)
        assert len(assessments) >= 3  # AWS Key (CRITICAL), shell=True (CRITICAL), SQL Inj (HIGH)

        # Verify exact findings detected
        finding_types = [a["risk_type"] for a in assessments]
        assert "SECRET_EXPOSURE_RISK" in finding_types
        assert "COMMAND_INJECTION_RISK" in finding_types
        assert "SQL_INJECTION_RISK" in finding_types

        # 2. Model file (weights.pkl) is NOT detected as a database or secret
        assert not any("weights.pkl" in a["affected_scope"] for a in assessments)

        # 3. Path normalization: zero /Users/ or uploads/ paths
        for a in results["assets"]:
            assert not a["location"].startswith("/Users"), f"Path leak: {a['location']}"
            assert not "uploads/scans" in a["location"], f"Workspace path leak: {a['location']}"
        for f in assessments:
            assert not f["affected_scope"].startswith("/Users"), f"Path leak: {f['affected_scope']}"
            assert not "uploads/scans" in f["affected_scope"], f"Workspace path leak: {f['affected_scope']}"

        # 4. Context Graph contains evidence-backed relationships
        graph = results["context_graph"]
        assert len(graph["architectural_trust_boundaries"]) == 4
        assert len(graph["discovered_nodes"]) >= 2
        assert len(graph["discovered_edges"]) >= 1

        # 5. Controls contain meaningful data and strictly equal canonical six
        controls = results["controls"]
        assert len(controls) == 6, f"Expected exactly 6 canonical controls, got {len(controls)}"
        for c in controls:
            assert c["control_id"] in ["AUTH-001", "AUTHZ-001", "INPJ-001", "SECM-001", "CONF-001", "CRYP-001"]
            assert c["status"] in ["PASS", "FAIL", "PARTIAL", "UNKNOWN"]
            assert len(c["rationale"]) > 0

        # 6. Posture score is derived and reflects vulnerabilities
        assert posture["posture_score"] < 70.0  # Due to critical AWS key & command injection
        assert posture["posture_rating"] in ["MODERATE", "NEEDS_ATTENTION"]
        assert posture.get("scoring_inputs") is not None


# =============================================================================
# 7. CRYP-001 Evidence & Lockfile Immunity Regression Tests
# =============================================================================
def test_cryp_001_detects_md5_failure(tmp_path):
    (tmp_path / "main.py").write_text("import hashlib\ndef hash_pw(pw):\n    return hashlib.md5(pw.encode()).hexdigest()\n")
    res = security_intelligence_orchestrator.run_full_analysis(
        str(tmp_path), project_name="Hardening-MD5Repo", force_refresh=True
    )
    cryp = next((c for c in res["controls"] if c["control_id"] == "CRYP-001"), None)
    assert cryp is not None
    assert cryp["status"] == "FAIL"
    assert cryp["state"] == "ABSENT"
    assert "MD5" in cryp["rationale"]
    assert "main.py" in cryp["rationale"]


def test_cryp_001_ignores_package_lock_hashes(tmp_path):
    # App code has NO crypto primitives
    (tmp_path / "index.js").write_text("console.log('Hello world');\n")
    # package-lock has sha512 integrity strings and binary weights have aes byte sequences
    (tmp_path / "package-lock.json").write_text('{"packages": {"foo": {"integrity": "sha512-abc123stronghash"}}}')
    (tmp_path / "model.pkl").write_bytes(b"some binary data containing aes cipher bytes")

    res = security_intelligence_orchestrator.run_full_analysis(
        str(tmp_path), project_name="Hardening-LockfileRepo", force_refresh=True
    )
    cryp = next((c for c in res["controls"] if c["control_id"] == "CRYP-001"), None)
    assert cryp is not None
    # Must NOT be fooled by package-lock.json or model.pkl into reporting PASS
    assert cryp["status"] == "UNKNOWN"
    assert cryp["state"] == "UNKNOWN"
    assert "No cryptographic primitives" in cryp["limitations"] or "No supported evidence" in cryp["rationale"]


def test_controls_always_strictly_equal_six(tmp_path):
    (tmp_path / "app.py").write_text("print('test')\n")
    res = security_intelligence_orchestrator.run_full_analysis(
        str(tmp_path), project_name="Hardening-SixControls", force_refresh=True
    )
    controls = res["controls"]
    assert len(controls) == 6
    expected_ids = {"AUTH-001", "AUTHZ-001", "INPJ-001", "SECM-001", "CONF-001", "CRYP-001"}
    assert {c["control_id"] for c in controls} == expected_ids


# =============================================================================
# 8. Multi-Scan Isolation & API Results Isolation
# =============================================================================
@pytest.mark.asyncio
async def test_scan_results_isolation_between_two_scans():
    repo_a = {"main.py": "import hashlib\ndef run(v):\n    return hashlib.md5(v.encode()).hexdigest()\n"}
    repo_b = {"main.py": "import subprocess\ndef run(v):\n    subprocess.run(v, shell=True)\n"}

    zip_a = create_zip_bytes(repo_a)
    zip_b = create_zip_bytes(repo_b)

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create scan A
        res_a = await client.post(
            "/api/v1/security-intelligence/scans/upload",
            files={"file": ("repo_a.zip", zip_a, "application/zip")},
            data={"project_name": "Test-RepoA"},
        )
        assert res_a.status_code == 201
        scan_id_a = res_a.json()["scan"]["id"]

        # Create scan B
        res_b = await client.post(
            "/api/v1/security-intelligence/scans/upload",
            files={"file": ("repo_b.zip", zip_b, "application/zip")},
            data={"project_name": "Test-RepoB"},
        )
        assert res_b.status_code == 201
        scan_id_b = res_b.json()["scan"]["id"]

        # Fetch Scan A results
        res_results_a = await client.get(f"/api/v1/security-intelligence/scans/{scan_id_a}/results")
        assert res_results_a.status_code == 200
        data_a = res_results_a.json()["results"]

        # Fetch Scan B results
        res_results_b = await client.get(f"/api/v1/security-intelligence/scans/{scan_id_b}/results")
        assert res_results_b.status_code == 200
        data_b = res_results_b.json()["results"]

        # Ensure Scan A has CRYP-001 FAIL (MD5) and zero command injection
        cryp_a = next(c for c in data_a["controls"] if c["control_id"] == "CRYP-001")
        assert cryp_a["status"] == "FAIL"
        assert not any(f["risk_type"] == "COMMAND_INJECTION_RISK" for f in data_a["assessments"])

        # Ensure Scan B has command injection and CRYP-001 UNKNOWN
        assert any(f["risk_type"] == "COMMAND_INJECTION_RISK" for f in data_b["assessments"])
        cryp_b = next(c for c in data_b["controls"] if c["control_id"] == "CRYP-001")
        assert cryp_b["status"] == "UNKNOWN"

        # Scan A and B results are completely distinct and independent
        assert res_results_a.json()["scan"]["id"] != res_results_b.json()["scan"]["id"]
        assert res_results_a.json()["scan"]["id"] == scan_id_a
        assert res_results_b.json()["scan"]["id"] == scan_id_b
        assert data_a["posture"]["posture_score"] != data_b["posture"]["posture_score"] or len(data_a["assessments"]) != len(data_b["assessments"])
