"""
Comprehensive Test Suite for Implicit Semantic Security Contradiction & False-Contradiction Reasoning

Test Cases:
Group 1 (10 Implicit Contradiction Cases):
1. Allows database bypass vs Validates authorization tokens -> CONTRADICTS
2. Accepts unsanitized input vs Sanitizes all user input -> CONTRADICTS
3. Transmits credentials in plaintext vs Encrypts credentials in transit -> CONTRADICTS
4. Does not verify certificates vs Validates TLS certificates -> CONTRADICTS
5. Exposes API without authentication vs Requires authenticated access -> CONTRADICTS
6. Stores passwords in plaintext vs Stores salted password hashes -> CONTRADICTS
7. Fails CSRF validation vs Validates CSRF tokens -> CONTRADICTS
8. Secret embedded in source vs Secret loaded from secure vault -> CONTRADICTS
9. Allows arbitrary file access vs Restricts file access -> CONTRADICTS
10. Authorization can be bypassed vs Authorization is enforced -> CONTRADICTS

Group 2 (10 False-Contradiction / Complementary Cases):
1. v1.2 is vulnerable vs v1.4 fixes the vulnerability -> RELATED / SUPPORTS
2. SQL injection exists vs Use parameterized queries -> SUPPORTS
3. Authentication is missing vs Add authentication middleware -> SUPPORTS
4. Package is vulnerable vs Upgrade package to patched release -> SUPPORTS
5. XSS vulnerability in profile vs Escaping user bio input remediates XSS -> SUPPORTS
6. Hardcoded secret exposed vs Load secret from environment variables -> SUPPORTS
7. Missing rate limiting vs Apply rate limiter decorator -> SUPPORTS
8. Docker runs as root vs Add non-root USER instruction -> SUPPORTS
9. Path traversal flaw vs Validate path with abspath -> SUPPORTS
10. Open redirect vulnerability vs Restrict redirect parameter to relative URLs -> SUPPORTS
"""

import pytest
from unittest.mock import patch
from app.services.ai.nli_engine import nli_engine


@pytest.fixture(autouse=True)
def bypass_cache_and_rerank():
    with patch("app.services.ai.nli_engine.response_cache.get_cached", return_value=None), \
         patch("app.services.ai.nli_engine.response_cache.set_cached", return_value=None), \
         patch("app.services.ai.nli_engine.rerank_manager.rerank", return_value=[0.85]):
        yield


# =============================================================================
# GROUP 1: 10 IMPLICIT CONTRADICTION CASES
# =============================================================================

def test_implicit_c1_database_bypass_vs_validates_authorization():
    item_a = {"source_id": "1", "excerpt": "auth.py line 42 allows full database bypass.", "file_path": "auth.py"}
    item_b = {"source_id": "2", "excerpt": "auth.py line 42 validates user authorization tokens.", "file_path": "auth.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"
    assert rel.property_match is True


def test_implicit_c2_accepts_unsanitized_vs_sanitizes_user_input():
    item_a = {"source_id": "1", "excerpt": "endpoint accepts unsanitized input.", "file_path": "input.py"}
    item_b = {"source_id": "2", "excerpt": "endpoint sanitizes all user input.", "file_path": "input.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_implicit_c3_plaintext_vs_encrypts_credentials():
    item_a = {"source_id": "1", "excerpt": "service transmits credentials in plaintext.", "file_path": "net.py"}
    item_b = {"source_id": "2", "excerpt": "service encrypts credentials in transit.", "file_path": "net.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_implicit_c4_does_not_verify_certificates_vs_validates_tls():
    item_a = {"source_id": "1", "excerpt": "client does not verify certificates.", "file_path": "fetch.py"}
    item_b = {"source_id": "2", "excerpt": "client validates TLS certificates.", "file_path": "fetch.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_implicit_c5_exposes_api_without_auth_vs_requires_authenticated_access():
    item_a = {"source_id": "1", "excerpt": "exposes API endpoint without authentication.", "file_path": "api.py"}
    item_b = {"source_id": "2", "excerpt": "api.py requires authenticated access.", "file_path": "api.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_implicit_c6_plaintext_passwords_vs_salted_hashes():
    item_a = {"source_id": "1", "excerpt": "database stores passwords in plaintext.", "file_path": "db.py"}
    item_b = {"source_id": "2", "excerpt": "db.py stores salted password hashes.", "file_path": "db.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_implicit_c7_fails_csrf_vs_validates_csrf():
    item_a = {"source_id": "1", "excerpt": "endpoint fails CSRF validation.", "file_path": "csrf.py"}
    item_b = {"source_id": "2", "excerpt": "csrf.py validates CSRF tokens.", "file_path": "csrf.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_implicit_c8_embedded_secret_vs_loaded_from_vault():
    item_a = {"source_id": "1", "excerpt": "secret embedded in source code.", "file_path": "config.py"}
    item_b = {"source_id": "2", "excerpt": "config.py loaded from secure vault.", "file_path": "config.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_implicit_c9_allows_arbitrary_file_access_vs_restricts():
    item_a = {"source_id": "1", "excerpt": "handler allows arbitrary file access.", "file_path": "files.py"}
    item_b = {"source_id": "2", "excerpt": "files.py restricts file access.", "file_path": "files.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_implicit_c10_bypassed_authorization_vs_enforced():
    item_a = {"source_id": "1", "excerpt": "authorization can be bypassed.", "file_path": "authz.py"}
    item_b = {"source_id": "2", "excerpt": "authorization is enforced in authz.py.", "file_path": "authz.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


# =============================================================================
# GROUP 2: 10 FALSE-CONTRADICTION / COMPLEMENTARY CASES
# =============================================================================

def test_false_c1_version_vulnerable_vs_fixed():
    item_a = {"source_id": "1", "excerpt": "v1.2 is vulnerable."}
    item_b = {"source_id": "2", "excerpt": "v1.4 fixes the vulnerability."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship in ["RELATED", "SUPPORTS"]


def test_false_c2_sql_injection_exists_vs_use_parameterized():
    item_a = {"source_id": "1", "excerpt": "SQL injection vulnerability exists in auth.py."}
    item_b = {"source_id": "2", "excerpt": "To fix SQL injection, use parameterized queries in auth.py."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"


def test_false_c3_authentication_missing_vs_add_middleware():
    item_a = {"source_id": "1", "excerpt": "Authentication is missing on admin routes."}
    item_b = {"source_id": "2", "excerpt": "To resolve, add authentication middleware to admin routes."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"


def test_false_c4_package_vulnerable_vs_upgrade_patched():
    item_a = {"source_id": "1", "excerpt": "Package PyYAML is vulnerable."}
    item_b = {"source_id": "2", "excerpt": "Upgrade PyYAML package to patched release v5.4."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship in ["RELATED", "SUPPORTS"]


def test_false_c5_xss_vulnerability_vs_escaping_remediation():
    item_a = {"source_id": "1", "excerpt": "XSS vulnerability in user profile bio."}
    item_b = {"source_id": "2", "excerpt": "Escaping user bio input remediates XSS."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"


def test_false_c6_hardcoded_secret_vs_load_env():
    item_a = {"source_id": "1", "excerpt": "Hardcoded secret exposed in settings.py."}
    item_b = {"source_id": "2", "excerpt": "Load secret from environment variables to remediate."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"


def test_false_c7_missing_rate_limiting_vs_apply_limiter():
    item_a = {"source_id": "1", "excerpt": "Missing rate limiting on auth API."}
    item_b = {"source_id": "2", "excerpt": "Apply rate limiter decorator to auth API."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"


def test_false_c8_docker_root_vs_add_user():
    item_a = {"source_id": "1", "excerpt": "Docker container runs as root user."}
    item_b = {"source_id": "2", "excerpt": "Add non-root USER instruction to Dockerfile."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"


def test_false_c9_path_traversal_vs_validate_abspath():
    item_a = {"source_id": "1", "excerpt": "Path traversal flaw in file download."}
    item_b = {"source_id": "2", "excerpt": "Validate file path with abspath to remediate."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"


def test_false_c10_open_redirect_vs_restrict_relative():
    item_a = {"source_id": "1", "excerpt": "Open redirect vulnerability in login parameter."}
    item_b = {"source_id": "2", "excerpt": "To fix, restrict redirect parameter to relative URLs."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"
