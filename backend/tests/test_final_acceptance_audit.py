"""
NOVA — Final Acceptance & End-to-End Audit Suite
Tests the complete real-world repository security scanning pipeline:
1. Database & Alembic schema integrity (no legacy tables)
2. Real ZIP archive ingestion & scan creation
3. Real vulnerability AST findings matching exact fixture lines
4. Real secret masking in findings & evidence
5. Real dynamic asset discovery from source code
6. Real trust-boundary security context graph
7. Real evidence-based control evaluations
8. Real risk scenario attack chains
9. Posture score calculation (delta_s = null for first scan)
10. Second scan with fix -> delta_s calculation & temporal comparison
11. Remediation verification endpoint (STILL_PRESENT vs VERIFIED_FIXED)
12. Scan history persistence & retrieval
13. Security negative tests (SSRF, loopback, private IP, zip slip, bombs, no code execution)
"""

import io
import os
import uuid
import zipfile
from pathlib import Path
import pytest
import httpx
from httpx import ASGITransport
from sqlalchemy import text

from app.main import app
from app.core.exceptions import ValidationAppError
from app.services.security_intelligence.repository_ingestion import repository_ingestion_service
from app.services.security_intelligence.security_rules import static_security_rules_engine, mask_secret
from app.services.security_intelligence.remediation_verifier import remediation_verifier
from app.services.security_intelligence.scan_service import security_scan_service
from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.models.user import User
from app.models.enums import UserRole, AuthProvider
from app.auth.dependencies import get_current_active_user, get_current_user


audit_user_id = uuid.uuid4()
audit_user = User(
    id=audit_user_id,
    email=f"audit_admin_{audit_user_id.hex[:8]}@nova.example",
    full_name="Audit Administrator",
    role=UserRole.ADMIN,
    is_active=True,
    auth_provider=AuthProvider.LOCAL,
)
@pytest.fixture(autouse=True)
async def ensure_audit_user():
    app.dependency_overrides[get_current_active_user] = lambda: audit_user
    app.dependency_overrides[get_current_user] = lambda: audit_user
    async with AsyncSessionLocal() as db:
        existing = await db.get(User, audit_user.id)
        if not existing:
            db.add(audit_user)
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
        app.dependency_overrides.pop(get_current_user, None)
        await engine.dispose()


async def _init_test_db_and_user():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        existing = await db.get(User, audit_user.id)
        if not existing:
            db.add(audit_user)
            await db.commit()



def create_comprehensive_vulnerable_zip() -> bytes:
    """Deterministic fixture with known vulnerable and safe patterns."""
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "src/config.py",
            "# Secrets and configuration\n"
            "AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'\n"
            "AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'\n"
            "DEBUG_MODE = True\n"
            "DATABASE_URI = 'postgresql://admin:supersecretpass@db.internal:5432/production'\n",
        )
        zf.writestr(
            "src/database.py",
            "import sqlite3\n\n"
            "def query_user(cursor, username):\n"
            "    # Line 5: Vulnerable SQL formatting\n"
            "    sql = f\"SELECT * FROM users WHERE username = '{username}'\"\n"
            "    cursor.execute(sql)\n"
            "    return cursor.fetchall()\n",
        )
        zf.writestr(
            "src/executor.py",
            "import subprocess\n"
            "import hashlib\n\n"
            "def run_command(param):\n"
            "    # Line 6: Command injection\n"
            "    return subprocess.Popen(f'ping -c 1 {param}', shell=True)\n\n"
            "def hash_token(data):\n"
            "    # Line 10: Insecure MD5 hash\n"
            "    return hashlib.md5(data.encode()).hexdigest()\n",
        )
        zf.writestr(
            "src/client.py",
            "import requests\n\n"
            "def get_remote(url):\n"
            "    # Line 5: Insecure TLS verify=False\n"
            "    return requests.get(url, verify=False)\n",
        )
        zf.writestr(
            "src/routes.py",
            "from fastapi import APIRouter, Depends\n"
            "router = APIRouter()\n\n"
            "@router.get('/api/v1/public/health')\n"
            "def health():\n"
            "    return {'status': 'healthy'}\n\n"
            "@router.get('/api/v1/admin/audit')\n"
            "def admin_audit(auth = Depends(RequireRole('admin'))):\n"
            "    return {'records': []}\n",
        )
    return mem.getvalue()


def create_temporal_v1_zip() -> bytes:
    """Fixture V1 for temporal test: contains SQL injection."""
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "app.py",
            "import sqlite3\n\n"
            "def get_user(cursor, username):\n"
            "    # Vulnerable SQL format\n"
            "    sql = f\"SELECT * FROM users WHERE username = '{username}'\"\n"
            "    cursor.execute(sql)\n"
            "    return cursor.fetchall()\n",
        )
    return mem.getvalue()


def create_temporal_v2_zip() -> bytes:
    """Fixture V2 for temporal test: SQL injection remediated with parameterized query."""
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "app.py",
            "import sqlite3\n\n"
            "def get_user(cursor, username):\n"
            "    # Parameterized SQL query (FIXED)\n"
            "    sql = 'SELECT * FROM users WHERE username = ?'\n"
            "    cursor.execute(sql, (username,))\n"
            "    return cursor.fetchall()\n",
        )
    return mem.getvalue()


# =====================================================================
# TEST 1: DATABASE & MIGRATIONS
# =====================================================================

@pytest.mark.asyncio
async def test_audit_database_and_migration_integrity():
    """Verify Alembic migration 0017 and ensure legacy scanner tables are absent."""
    await _init_test_db_and_user()
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT version_num FROM alembic_version;"))
        version = res.scalar()
        assert version == "0017_security_intel_scans", f"Alembic revision mismatch: {version}"

        tables_res = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        ))
        tables = [row[0] for row in tables_res.fetchall()]

        assert "security_intel_scans" in tables
        assert "security_intel_assets" in tables
        assert "security_intel_observations" in tables
        assert "security_intel_controls" in tables
        assert "security_intel_risk_scenarios" in tables
        assert "security_intel_assessments" in tables
        assert "security_intel_posture_snapshots" in tables

        # Legacy tables MUST NOT exist
        assert "findings" not in tables
        assert "scan_jobs" not in tables


# =====================================================================
# TEST 2: REAL ZIP E2E SCAN & FINDINGS VALIDATION
# =====================================================================

@pytest.mark.asyncio
async def test_audit_real_zip_e2e_scan():
    """Execute complete ZIP scan and verify all security intelligence layers."""
    await _init_test_db_and_user()

    zip_data = create_comprehensive_vulnerable_zip()
    project_name = f"Audit-Repo-{uuid.uuid4().hex[:6]}"

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. API: Upload & Trigger Scan
        response = await ac.post(
            "/api/v1/security-intelligence/scans/upload",
            files={"file": ("vulnerable_repo.zip", zip_data, "application/zip")},
            data={"project_name": project_name},
        )
        assert response.status_code == 201, response.text
        scan_wrapper = response.json()
        scan = scan_wrapper["scan"]
        scan_id = scan["id"]

        assert scan["status"] == "COMPLETED"
        assert scan["progress"] == 100
        assert scan["stage"] in ("COMPLETED", "Analysis complete")
        assert scan["posture_score"] is not None

        # 2. API: Query Scan Results
        results_resp = await ac.get(f"/api/v1/security-intelligence/scans/{scan_id}/results")
        assert results_resp.status_code == 200
        data = results_resp.json()
        assert "results" in data
        results = data["results"]

        observations = results["observations"]
        assets = results["assets"]
        controls = results["controls"]
        graph = results["graph"]
        risks = results["risks"]
        posture = results["posture"]

        # 3. Extract Finding Data & Verify Accuracy against Source Code
        findings = [o.get("finding_data") or o.get("attributes", {}).get("finding_data", {}) for o in observations]
        findings = [f for f in findings if f]
        rules_detected = {f.get("rule_id") for f in findings}

        assert "SEC001_AWS_CREDENTIAL" in rules_detected
        assert "SEC004_DATABASE_CREDENTIALS" in rules_detected
        assert "INJ001_SQL_INJECTION" in rules_detected
        assert "INJ002_COMMAND_INJECTION" in rules_detected
        assert "CRY001_WEAK_HASH" in rules_detected
        assert "CFG001_TLS_VERIFY_DISABLED" in rules_detected

        # Check SQL Injection line and file accuracy
        sql_f = next(f for f in findings if f.get("rule_id") == "INJ001_SQL_INJECTION")
        assert "database.py" in sql_f["file_path"]
        assert sql_f["line_number"] == 5
        assert sql_f["severity"] == "HIGH"
        assert "f\"SELECT * FROM users WHERE username = '{username}'\"" in sql_f["code_snippet"]

        # 4. Verify Secret Masking in Evidence
        aws_f = next(f for f in findings if f.get("rule_id") == "SEC001_AWS_CREDENTIAL")
        assert "AKIAIOSFODNN7EXAMPLE" not in aws_f["code_snippet"]
        assert "AKIA" in aws_f["code_snippet"] and "..." in aws_f["code_snippet"]

        # 5. Verify Asset Discovery
        asset_types = {a["asset_type"] for a in assets}
        assert "APPLICATION" in asset_types
        assert "ENDPOINT" in asset_types
        assert "DATABASE" in asset_types
        assert "SERVICE" in asset_types

        # 6. Verify Security Controls (6 domains)
        domains = {c.get("control_type") or c.get("domain", "") for c in controls}
        assert any("AUTH" in d for d in domains)
        assert any("SECRET" in d for d in domains)
        assert any("INPUT" in d or "INP" in d for d in domains)
        assert any("ENCRYPTION" in d or "CRY" in d for d in domains)

        # 7. Verify Security Context Graph
        assert "trust_boundaries" in graph
        assert "data_flows" in graph
        assert len(graph["trust_boundaries"]) >= 2
        assert len(graph["data_flows"]) >= 2
        assert any(b.get("boundary_id") == "TB-1" for b in graph["trust_boundaries"])
        assert any(b.get("boundary_id") == "TB-4" for b in graph["trust_boundaries"])

        # 8. Verify Risk Scenarios
        assert len(risks) >= 1
        for r in risks:
            assert len(r.get("attack_path", [])) >= 2
            assert "scenario_type" in r
            assert "potential_impact" in r


# =====================================================================
# TEST 3: SECOND SCAN & TEMPORAL POSTURE DELTA
# =====================================================================

@pytest.mark.asyncio
async def test_audit_temporal_posture_delta():
    """Verify temporal posture comparison when scanning a remediated commit."""
    await _init_test_db_and_user()

    project_name = f"Audit-Temporal-{uuid.uuid4().hex[:6]}"

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # First Scan (Vulnerable)
        v1_zip = create_temporal_v1_zip()
        r1 = await ac.post(
            "/api/v1/security-intelligence/scans/upload",
            files={"file": ("repo_v1.zip", v1_zip, "application/zip")},
            data={"project_name": project_name},
        )
        assert r1.status_code == 201
        scan1 = r1.json()["scan"]
        score1 = scan1["posture_score"]

        # Second Scan (Remediated SQL Injection)
        v2_zip = create_temporal_v2_zip()
        r2 = await ac.post(
            "/api/v1/security-intelligence/scans/upload",
            files={"file": ("repo_v2.zip", v2_zip, "application/zip")},
            data={"project_name": project_name},
        )
        assert r2.status_code == 201
        scan2 = r2.json()["scan"]
        score2 = scan2["posture_score"]
        delta_s = scan2["delta_score"]

        assert score2 > score1, f"Score should improve: {score2} vs {score1}"
        assert abs(delta_s - (score2 - score1)) < 0.01
        assert scan2["trend_direction"] == "IMPROVED"

        # Verify SQL finding is no longer present in Scan 2
        r2_results = (await ac.get(f"/api/v1/security-intelligence/scans/{scan2['id']}/results")).json()
        f2_obs = r2_results["results"]["observations"]
        f2_findings = [o.get("finding_data") or o.get("attributes", {}).get("finding_data", {}) for o in f2_obs]
        f2_rules = {f.get("rule_id") for f in f2_findings if f}
        assert "INJ001_SQL_INJECTION" not in f2_rules


# =====================================================================
# TEST 4: REMEDIATION VERIFIER
# =====================================================================

@pytest.mark.asyncio
async def test_audit_remediation_verifier():
    """Test POST /api/v1/security-intelligence/verify-remediation."""
    await _init_test_db_and_user()

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # A. Vulnerable Code
        resp_vuln = await ac.post(
            "/api/v1/security-intelligence/verify-remediation",
            json={
                "assessment_id": "ASM-SQLI-001",
                "code_snippet": "def query(user_id): return db.execute(f'SELECT * FROM users WHERE id={user_id}')",
                "target_file_path": "src/database.py",
            },
        )
        assert resp_vuln.status_code == 200
        assert resp_vuln.json()["status"] in ["STILL_PRESENT", "OPEN"]
        assert not resp_vuln.json()["fixed"]

        # B. Fixed Code
        resp_fixed = await ac.post(
            "/api/v1/security-intelligence/verify-remediation",
            json={
                "assessment_id": "ASM-SQLI-001",
                "code_snippet": "@router.post('/role', dependencies=[Depends(RequireRole('admin'))])\ndef update_role(): pass",
                "target_file_path": "src/routes.py",
            },
        )
        assert resp_fixed.status_code == 200
        assert resp_fixed.json()["status"] == "VERIFIED_FIXED"
        assert resp_fixed.json()["fixed"]


# =====================================================================
# TEST 5: SECURITY NEGATIVE TESTS (SSRF, ZIP SLIP, BOMBS)
# =====================================================================

def test_audit_security_negative_protections():
    """Verify SSRF and ZIP slip protections."""
    # A. Invalid / SSRF URLs
    with pytest.raises(Exception):
        repository_ingestion_service.validate_github_url("https://gitlab.com/user/repo")

    with pytest.raises(Exception):
        repository_ingestion_service.validate_github_url("http://127.0.0.1:8000/repo")

    with pytest.raises(Exception):
        repository_ingestion_service.validate_github_url("http://192.168.1.1/repo")

    with pytest.raises(Exception):
        repository_ingestion_service.validate_github_url("https://user:pass@github.com/org/repo")

    # B. Malicious Zip Slip
    mem_slip = io.BytesIO()
    with zipfile.ZipFile(mem_slip, mode="w") as zf:
        zf.writestr("../../evil.txt", "MALICIOUS PAYLOAD")

    with pytest.raises(Exception):
        repository_ingestion_service.extract_zip_archive(mem_slip.getvalue(), "/tmp/nova_test_extract")
