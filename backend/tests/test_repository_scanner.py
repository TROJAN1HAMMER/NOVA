"""
NOVA — Repository Security Scanner Test Suite
Tests GitHub URL validation, ZIP slip & traversal protections, static analysis rules,
dynamic asset discovery, control evaluation, risk scenario generation, posture calculation,
remediation verification, and end-to-end scan lifecycle.
"""

import io
import os
import tarfile
import tempfile
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.exceptions import ValidationAppError
from app.integrations.github.client import GitHubRepoProvider
from app.services.security_intelligence.repository_ingestion import repository_ingestion_service
from app.services.security_intelligence.security_rules import static_security_rules_engine, mask_secret
from app.services.security_intelligence.asset_discovery_service import asset_discovery_service
from app.services.security_intelligence.observation_collector import observation_collector
from app.services.security_intelligence.control_analyzer import control_analyzer
from app.services.security_intelligence.risk_scenario_engine import risk_scenario_engine
from app.services.security_intelligence.scenario_verifier import scenario_verifier
from app.services.security_intelligence.remediation_verifier import remediation_verifier
from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator
from app.services.security_intelligence.scan_service import security_scan_service
from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.models.user import User
from app.models.enums import UserRole, AuthProvider
from app.auth.dependencies import get_current_active_user, get_current_user

test_user_id = uuid.UUID("c5b5a681-fac3-4e4b-b81d-4a51c177d1dc")
test_user = User(
    id=test_user_id,
    email="admin@nova.ai",
    full_name="Scanner Test Admin",
    role=UserRole.ADMIN,
    is_active=True,
    auth_provider=AuthProvider.LOCAL,
)
@pytest.fixture(autouse=True)
async def ensure_scanner_user():
    app.dependency_overrides[get_current_active_user] = lambda: test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.models.security_intelligence import SecurityIntelScan
        test_projects = {"FlaskDemo", "API_Test_Repo", "Octocat-Hello-World", "Private-Nova-Repo", "Private-Fintech-Core"}
        scans = (await db.execute(select(SecurityIntelScan))).scalars().all()
        for s in scans:
            if s.project_name in test_projects:
                await db.delete(s)
        await db.commit()

async def _init_test_db_and_user():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        existing = await db.get(User, test_user.id)
        if not existing:
            db.add(test_user)
            await db.commit()


client = TestClient(app)


# Fixture Helper to Create Test ZIPs
def create_test_zip(files_dict: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files_dict.items():
            zf.writestr(filename, content)
    return buf.getvalue()


# 1. GitHub URL Validation Tests
def test_github_url_validation_valid():
    owner, repo = repository_ingestion_service.validate_github_url("https://github.com/facebook/react")
    assert owner == "facebook"
    assert repo == "react"

    owner2, repo2 = repository_ingestion_service.validate_github_url("https://github.com/fastapi/fastapi.git")
    assert owner2 == "fastapi"
    assert repo2 == "fastapi"


def test_github_url_validation_rejections():
    # Reject non-https
    with pytest.raises(ValidationAppError, match="Only secure HTTPS"):
        repository_ingestion_service.validate_github_url("http://github.com/owner/repo")

    # Reject shell metacharacters
    with pytest.raises(ValidationAppError, match="Invalid characters"):
        repository_ingestion_service.validate_github_url("https://github.com/owner/repo;rm -rf /")

    # Reject non-github host
    with pytest.raises(ValidationAppError, match="Only repositories on 'github.com'"):
        repository_ingestion_service.validate_github_url("https://gitlab.com/owner/repo")

    # Reject credentials
    with pytest.raises(ValidationAppError, match="Embedded credentials"):
        repository_ingestion_service.validate_github_url("https://user:pass@github.com/owner/repo")

    # Reject SSRF / private IP
    with pytest.raises(ValidationAppError, match="Private or internal network"):
        repository_ingestion_service.validate_github_url("https://github.com/127.0.0.1/repo")


# 2. ZIP Security & Traversal Protection Tests
def test_zip_slip_protection():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # Malicious Zip Slip path
        zf.writestr("../../../etc/passwd", "malicious_content")
    bad_zip_data = buf.getvalue()

    with pytest.raises(ValidationAppError, match="Zip Slip"):
        repository_ingestion_service.validate_and_extract_zip(bad_zip_data, f"test-{uuid.uuid4()}")


def test_corrupted_zip_rejection():
    with pytest.raises(ValidationAppError):
        repository_ingestion_service.validate_and_extract_zip(b"NOT_A_ZIP_HEADER", f"test-{uuid.uuid4()}")


def test_safe_zip_extraction(tmp_path):
    files = {
        "app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): return {'status': 'ok'}",
        "requirements.txt": "fastapi==0.100.0\nuvicorn==0.23.0\n",
    }
    zip_bytes = create_test_zip(files)
    scan_id = f"test-safe-{uuid.uuid4()}"

    extracted_root = repository_ingestion_service.validate_and_extract_zip(zip_bytes, scan_id)
    assert extracted_root.exists()
    assert (extracted_root / "app" / "main.py").exists()

    # Cleanup
    repository_ingestion_service.cleanup_workspace(scan_id)


# 3. Static Security Rules Tests
def test_static_rules_secret_detection(tmp_path):
    vuln_file = tmp_path / "config.py"
    vuln_file.write_text("""
AWS_ACCESS_KEY = "AKIA1234567890ABCDEF"
STRIPE_SECRET_KEY = "sk_live_123456789abcdef"
DB_URL = "postgresql://admin:supersecret123@db.prod.internal/main"
""", encoding="utf-8")

    findings = static_security_rules_engine.analyze_file(vuln_file, tmp_path)
    assert len(findings) >= 2
    rule_ids = {f.rule_id for f in findings}
    assert "SEC001_AWS_CREDENTIAL" in rule_ids
    assert "SEC004_DATABASE_CREDENTIALS" in rule_ids

    # Verify secret is masked in snippet and reasoning
    aws_finding = next(f for f in findings if f.rule_id == "SEC001_AWS_CREDENTIAL")
    assert "AKIA" in aws_finding.code_snippet
    assert "AKIA1234567890ABCDEF" not in aws_finding.code_snippet  # Must be masked!


def test_static_rules_injection_detection(tmp_path):
    vuln_file = tmp_path / "service.py"
    vuln_file.write_text("""
import os
import subprocess

def run_command(user_cmd):
    return subprocess.Popen(user_cmd, shell=True)

def raw_sql_query(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)

def unsafe_eval(expr):
    return eval(expr)
""", encoding="utf-8")

    findings = static_security_rules_engine.analyze_file(vuln_file, tmp_path)
    rule_ids = {f.rule_id for f in findings}
    assert "INJ001_SQL_INJECTION" in rule_ids
    assert "INJ002_COMMAND_INJECTION" in rule_ids
    assert "INJ003_DYNAMIC_EVAL" in rule_ids


def test_static_rules_crypto_and_config(tmp_path):
    vuln_file = tmp_path / "crypto_utils.py"
    vuln_file.write_text("""
import hashlib
import requests

def hash_data(val):
    return hashlib.md5(val.encode()).hexdigest()

def fetch_data(url):
    return requests.get(url, verify=False)
""", encoding="utf-8")

    findings = static_security_rules_engine.analyze_file(vuln_file, tmp_path)
    rule_ids = {f.rule_id for f in findings}
    assert "CRY001_WEAK_HASH" in rule_ids
    assert "CFG001_TLS_VERIFY_DISABLED" in rule_ids


# 4. Dynamic Asset Discovery on Fixture Repository
def test_dynamic_asset_discovery(tmp_path):
    # Setup fixture directory
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "auth.py").write_text("@router.post('/api/v1/auth/login')\ndef login(): pass", encoding="utf-8")
    (tmp_path / "api" / "admin.py").write_text("@router.get('/api/v1/admin/users')\ndef list_users(): pass", encoding="utf-8")
    (tmp_path / "db.py").write_text("import sqlalchemy\nDATABASE_URL = 'postgresql://localhost:5432/test'", encoding="utf-8")
    (tmp_path / "integrations.py").write_text("import boto3\ns3 = boto3.client('s3')", encoding="utf-8")

    assets = asset_discovery_service.discover_assets(str(tmp_path))
    asset_types = {a.asset_type for a in assets}
    assert "APPLICATION" in asset_types
    assert "API" in asset_types or "ENDPOINT" in asset_types
    assert "DATABASE" in asset_types
    assert "SERVICE" in asset_types


# 5. Full End-to-End Orchestrator on Fixture Repository
def test_full_analysis_on_vulnerable_repository(tmp_path):
    (tmp_path / "main.py").write_text("""
from fastapi import FastAPI
import hashlib
app = FastAPI()

@app.get('/api/v1/users')
def get_user(user_id: str):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return db.execute(query)

@app.post('/api/v1/auth/hash')
def hash_pwd(pwd: str):
    return hashlib.md5(pwd.encode()).hexdigest()
""", encoding="utf-8")

    result = security_intelligence_orchestrator.run_full_analysis(str(tmp_path), project_name="VulnerableApp", force_refresh=True)
    assert result["status"] == "COMPLETED"
    assert len(result["assets"]) >= 1
    assert len(result["assessments"]) >= 1

    # Posture score should reflect vulnerabilities (not hardcoded 95)
    posture = result["posture"]
    assert posture["posture_score"] < 100.0
    assert result["snapshot"]["unresolved_risks_count"] >= 1


# 6. Remediation Verification
def test_remediation_verification_workflow():
    # Vulnerable snippet
    vuln_code = "def query(user_id): return db.execute(f'SELECT * FROM users WHERE id={user_id}')"
    res_vuln = remediation_verifier.verify_remediation("ass-101", vuln_code)
    assert res_vuln["fixed"] is False
    assert res_vuln["status"] in ["OPEN", "STILL_PRESENT"]

    # Fixed snippet with structural parameterization & authorization
    fixed_code = "@router.post('/role', dependencies=[Depends(RequireRole('admin'))])\ndef update_role(): pass"
    res_fixed = remediation_verifier.verify_remediation("ass-101", fixed_code)
    assert res_fixed["fixed"] is True
    assert res_fixed["status"] == "VERIFIED_FIXED"


# 7. Scan Service Job Execution & Database Persistence
@pytest.mark.asyncio
async def test_scan_service_zip_lifecycle():
    await _init_test_db_and_user()

    zip_bytes = create_test_zip({
        "app.py": "from flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef index(): return 'hello'",
        "requirements.txt": "flask==2.3.0",
    })

    async with AsyncSessionLocal() as db:
        scan = await security_scan_service.create_scan_job(
            db=db,
            project_name="FlaskDemo",
            source_type="ZIP",
            source_identifier="flask_app.zip",
        )
        scan_id = scan.id

    # Execute scan
    results = await security_scan_service.execute_scan(scan_id, zip_bytes=zip_bytes)
    assert results["status"] == "COMPLETED"

    async with AsyncSessionLocal() as db:
        loaded_scan = await security_scan_service.get_scan(db, scan_id)
        assert loaded_scan is not None
        assert loaded_scan.status == "COMPLETED"
        assert loaded_scan.progress == 100
        assert loaded_scan.posture_score is not None
        assert loaded_scan.result_summary is not None
        assert loaded_scan.result_summary["total_assets"] >= 1


# 8. REST API Scan Upload Test
@pytest.mark.asyncio
async def test_api_scan_upload():
    await _init_test_db_and_user()
    import httpx
    from httpx import ASGITransport

    zip_bytes = create_test_zip({
        "server.py": "import os\nprint('Server started')",
        "requirements.txt": "requests==2.28.1",
    })

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/security-intelligence/scans/upload",
            files={"file": ("test_repo.zip", zip_bytes, "application/zip")},
            data={"project_name": "API_Test_Repo"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "scan" in data
        scan_info = data["scan"]
        assert scan_info["status"] == "COMPLETED"
        assert scan_info["project_name"] == "API_Test_Repo"
        assert scan_info["posture_score"] is not None

        # Retrieve scan results
        scan_id = scan_info["id"]
        res_results = await ac.get(f"/api/v1/security-intelligence/scans/{scan_id}/results")
        assert res_results.status_code == 200
        res_data = res_results.json()
        assert res_data["status"] == "COMPLETED"
        assert "results" in res_data
        assert "assets" in res_data["results"]


@pytest.mark.asyncio
async def test_api_list_scans():
    await _init_test_db_and_user()
    import httpx
    from httpx import ASGITransport

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/security-intelligence/scans")
        assert res.status_code == 200
        data = res.json()
        assert "scans" in data
        assert "count" in data
        assert isinstance(data["scans"], list)


@pytest.mark.asyncio
async def test_api_github_scan_public_e2e():
    """Verify live public GitHub ingestion, AST analysis, and result completion."""
    await _init_test_db_and_user()
    import httpx
    from httpx import ASGITransport

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/security-intelligence/scans/github",
            json={
                "repo_url": "https://github.com/octocat/Hello-World",
                "branch": "master",
                "project_name": "Octocat-Hello-World",
            },
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert "scan" in data
        scan = data["scan"]
        if scan["status"] == "FAILED" and "rate limit" in (scan.get("error_message") or "").lower():
            pytest.skip("GitHub API rate limit reached for unauthenticated test calls")
        assert scan["status"] == "COMPLETED"
        assert scan["progress"] == 100
        assert scan["posture_score"] is not None

        # Verify results endpoint
        scan_id = scan["id"]
        results_resp = await ac.get(f"/api/v1/security-intelligence/scans/{scan_id}/results")
        assert results_resp.status_code == 200
        results = results_resp.json()["results"]
        assert "assets" in results
        assert "controls" in results
        assert "posture" in results


def create_test_tar_gz(files_dict: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for filename, content in files_dict.items():
            content_bytes = content.encode("utf-8") if isinstance(content, str) else content
            ti = tarfile.TarInfo(name=filename)
            ti.size = len(content_bytes)
            tar.addfile(ti, io.BytesIO(content_bytes))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_api_github_scan_private_clean_rejection():
    """Verify private/inaccessible GitHub repositories fail cleanly with actionable user error."""
    await _init_test_db_and_user()
    import httpx
    from httpx import ASGITransport

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/security-intelligence/scans/github",
            json={
                "repo_url": "https://github.com/trojan1hammer/nova",
                "branch": "main",
                "project_name": "Private-Nova-Repo",
            },
        )
        assert res.status_code == 201, res.text
        data = res.json()
        assert "scan" in data
        scan = data["scan"]
        assert scan["status"] == "FAILED"
        err = (scan.get("error_message") or "").lower()
        assert "private" in err or "could not be accessed" in err or "read access" in err or "rate limit" in err


@pytest.mark.asyncio
async def test_github_provider_authenticated_private_download_and_extract(tmp_path):
    """
    Test authenticated private repository archive download and extraction.
    Verifies that:
    1. Authorization Bearer header is sent to api.github.com
    2. HTTP 302 redirect to storage is followed
    3. Authorization header is STRIPPED on the storage download redirect
    4. Archive is downloaded and returned
    """
    import httpx
    from httpx import MockTransport

    tar_bytes = create_test_tar_gz({
        "my-repo/app.py": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/api')\ndef api(): pass",
        "my-repo/README.md": "# Private Enterprise Repo",
    })

    captured_headers: dict = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        captured_headers[url_str] = dict(request.headers)

        if "api.github.com/repos/enterprise/private-service/tarball" in url_str:
            return httpx.Response(
                302,
                headers={"Location": "https://codeload.github.com/enterprise/private-service/legacy.tar.gz?token=signed123"},
            )
        elif "api.github.com/repos/enterprise/private-service" in url_str:
            return httpx.Response(200, json={"private": True, "default_branch": "main", "name": "private-service"})
        elif "codeload.github.com" in url_str:
            return httpx.Response(200, content=tar_bytes)
        return httpx.Response(404)

    _RealAsyncClient = httpx.AsyncClient

    with patch("app.integrations.github.client.httpx.AsyncClient", side_effect=lambda **kwargs: _RealAsyncClient(transport=MockTransport(mock_handler))):
        provider = GitHubRepoProvider(token="ghp_test_enterprise_token_12345")
        archive_path = await provider.download_archive(
            "https://github.com/enterprise/private-service",
            ref=None,
            dest_dir=tmp_path / "downloads",
        )
        assert archive_path.exists()
        assert archive_path.stat().st_size > 0

        # Verify Authorization header was sent to api.github.com
        meta_call = next((k for k in captured_headers if "api.github.com/repos/enterprise/private-service" in k and "tarball" not in k), None)
        assert meta_call is not None
        assert "authorization" in captured_headers[meta_call]
        assert captured_headers[meta_call]["authorization"] == "Bearer ghp_test_enterprise_token_12345"

        # Verify Authorization header was STRIPPED on redirect to codeload
        codeload_call = next((k for k in captured_headers if "codeload.github.com" in k), None)
        assert codeload_call is not None
        assert "authorization" not in captured_headers[codeload_call]


@pytest.mark.asyncio
async def test_github_provider_private_repo_missing_token_actionable_error():
    """Verify private repo without token gives clear actionable message."""
    import httpx
    from httpx import MockTransport

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    _RealAsyncClient = httpx.AsyncClient

    with patch("app.integrations.github.client.httpx.AsyncClient", side_effect=lambda **kwargs: _RealAsyncClient(transport=MockTransport(mock_handler))):
        provider = GitHubRepoProvider(token=None)
        with pytest.raises(ValidationAppError, match="This repository is private and NOVA does not have GitHub read access configured."):
            await provider.get_repo_metadata("enterprise", "private-service")


@pytest.mark.asyncio
async def test_github_provider_token_lacks_permission_actionable_error():
    """Verify private repo with token that lacks permission gives clear actionable message."""
    import httpx
    from httpx import MockTransport

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    _RealAsyncClient = httpx.AsyncClient

    with patch("app.integrations.github.client.httpx.AsyncClient", side_effect=lambda **kwargs: _RealAsyncClient(transport=MockTransport(mock_handler))):
        provider = GitHubRepoProvider(token="ghp_low_privilege_token")
        with pytest.raises(ValidationAppError, match="GitHub repository could not be accessed with the configured NOVA GitHub credentials."):
            await provider.get_repo_metadata("enterprise", "forbidden-service")


@pytest.mark.asyncio
async def test_github_provider_rate_limit_actionable_error():
    """Verify rate limit gives actionable message."""
    import httpx
    from httpx import MockTransport

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, json={"message": "API rate limit exceeded"})

    _RealAsyncClient = httpx.AsyncClient

    with patch("app.integrations.github.client.httpx.AsyncClient", side_effect=lambda **kwargs: _RealAsyncClient(transport=MockTransport(mock_handler))):
        provider = GitHubRepoProvider(token="ghp_token")
        with pytest.raises(ValidationAppError, match="GitHub API rate limit reached. Please try again later."):
            await provider.get_repo_metadata("enterprise", "any-repo")


@pytest.mark.asyncio
async def test_github_provider_invalid_token_actionable_error():
    """Verify invalid token gives actionable message."""
    import httpx
    from httpx import MockTransport

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    _RealAsyncClient = httpx.AsyncClient

    with patch("app.integrations.github.client.httpx.AsyncClient", side_effect=lambda **kwargs: _RealAsyncClient(transport=MockTransport(mock_handler))):
        provider = GitHubRepoProvider(token="ghp_expired_token")
        with pytest.raises(ValidationAppError, match="Configured NOVA GitHub credential is invalid or expired."):
            await provider.get_repo_metadata("enterprise", "any-repo")


@pytest.mark.asyncio
async def test_github_provider_ssrf_redirect_blocked(tmp_path):
    """Verify redirects to non-whitelisted domains or internal IPs are blocked."""
    import httpx
    from httpx import MockTransport

    _RealAsyncClient = httpx.AsyncClient

    # Test SSRF redirect to AWS metadata endpoint
    def mock_ssrf_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "tarball" in url_str:
            return httpx.Response(302, headers={"Location": "https://169.254.169.254/latest/meta-data"})
        return httpx.Response(200, json={"private": False, "default_branch": "main"})

    with patch("app.integrations.github.client.httpx.AsyncClient", side_effect=lambda **kwargs: _RealAsyncClient(transport=MockTransport(mock_ssrf_handler))):
        provider = GitHubRepoProvider()
        with pytest.raises(ValidationAppError, match="Redirect to private or internal network destination is prohibited."):
            await provider.download_archive("https://github.com/org/repo", ref="main", dest_dir=tmp_path / "downloads")

    # Test redirect to untrusted domain
    def mock_evil_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "tarball" in url_str:
            return httpx.Response(302, headers={"Location": "https://attacker.evil.com/payload.tar.gz"})
        return httpx.Response(200, json={"private": False, "default_branch": "main"})

    with patch("app.integrations.github.client.httpx.AsyncClient", side_effect=lambda **kwargs: _RealAsyncClient(transport=MockTransport(mock_evil_handler))):
        provider = GitHubRepoProvider()
        with pytest.raises(ValidationAppError, match="Prohibited redirect target domain: attacker.evil.com"):
            await provider.download_archive("https://github.com/org/repo", ref="main", dest_dir=tmp_path / "downloads")


@pytest.mark.asyncio
async def test_api_github_scan_authenticated_private_e2e_mocked():
    """Verify full end-to-end scan pipeline for an authenticated private GitHub repository."""
    await _init_test_db_and_user()
    import httpx
    from httpx import ASGITransport, MockTransport

    tar_bytes = create_test_tar_gz({
        "internal-fintech/server.py": (
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "@app.post('/api/admin/users')\n"
            "def manage_users(): pass\n"
        ),
        "internal-fintech/requirements.txt": "fastapi==0.110.0\nuvicorn==0.27.0\n",
    })

    def mock_github_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "tarball" in url_str:
            return httpx.Response(
                302,
                headers={"Location": "https://codeload.github.com/internal-fintech/core/legacy.tar.gz?token=abc"},
            )
        elif "api.github.com/repos/internal-fintech/core" in url_str:
            return httpx.Response(200, json={"private": True, "default_branch": "main", "name": "core"})
        elif "codeload.github.com" in url_str:
            return httpx.Response(200, content=tar_bytes)
        return httpx.Response(404)

    _RealAsyncClient = httpx.AsyncClient

    async with _RealAsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.integrations.github.client.httpx.AsyncClient", side_effect=lambda **kwargs: _RealAsyncClient(transport=MockTransport(mock_github_handler), **{k: v for k, v in kwargs.items() if k not in ("transport", "follow_redirects")})):
            res = await ac.post(
                "/api/v1/security-intelligence/scans/github",
                json={
                    "repo_url": "https://github.com/internal-fintech/core",
                    "project_name": "Private-Fintech-Core",
                },
            )
            assert res.status_code == 201, res.text
            data = res.json()
            assert "scan" in data
            scan = data["scan"]
            assert scan["status"] == "COMPLETED"
            assert scan["progress"] == 100
            assert scan["posture_score"] is not None
            assert scan["posture_rating"] is not None

            # Retrieve results
            scan_id = scan["id"]
            results_resp = await ac.get(f"/api/v1/security-intelligence/scans/{scan_id}/results")
            assert results_resp.status_code == 200
            results = results_resp.json()["results"]
            assert "assets" in results
            assert len(results["assets"]) > 0
            assert "posture" in results
