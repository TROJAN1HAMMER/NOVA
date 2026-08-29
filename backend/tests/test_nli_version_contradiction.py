"""
Comprehensive Edge-Case Test Suite for Version-Aware & Security Contradiction NLI Reasoning

Test Matrix:
A. Same Version Contradiction ("X v1.2 vulnerable" vs "X v1.2 patched") -> CONTRADICTS
B. Different Version Upgrade ("X v1.2 vulnerable" vs "X v1.4 patched") -> RELATED / SUPPORTS
C. Same CVE Contradiction ("CVE-1234 affects X" vs "CVE-1234 does not affect X") -> CONTRADICTS
D. Distinct CVEs ("CVE-1234" vs "CVE-9999") -> Not automatically contradictory
E. Remediation Guide ("SQL injection detected" vs "Parameterized queries prevent SQL injection") -> SUPPORTS
F. Unrelated Policy ("Security finding" vs "Employee leave policy") -> UNRELATED
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
# GROUP 1: 10 VERSION-AWARE TEST CASES
# =============================================================================

def test_version_v1_same_version_contradiction():
    item_a = {"source_id": "1", "excerpt": "Package PyYAML v5.3 is vulnerable to remote code execution."}
    item_b = {"source_id": "2", "excerpt": "PyYAML v5.3 is safe and not vulnerable to code execution."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_version_v2_different_version_upgrade_path():
    item_a = {"source_id": "1", "excerpt": "Package PyYAML v5.3 is vulnerable to remote code execution."}
    item_b = {"source_id": "2", "excerpt": "PyYAML v5.4 fixes the remote code execution flaw."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship in ["RELATED", "SUPPORTS"]


def test_version_v3_affected_vs_fixed_version():
    item_a = {"source_id": "1", "excerpt": "requests version 2.18.0 contains a high severity vulnerability."}
    item_b = {"source_id": "2", "excerpt": "requests 2.18.0 is safe and has zero vulnerabilities."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_version_v4_upgrade_remediation_guidance():
    item_a = {"source_id": "1", "excerpt": "requests 2.18.0 is vulnerable."}
    item_b = {"source_id": "2", "excerpt": "Upgrade requests to version 2.20.0 or later."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship in ["RELATED", "SUPPORTS"]


def test_version_v5_comparison_operator_vulnerable_before():
    item_a = {"source_id": "1", "excerpt": "Library X is vulnerable before v1.4."}
    item_b = {"source_id": "2", "excerpt": "Library X is safe and not vulnerable before v1.4."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_version_v6_comparison_operator_fixed_in():
    item_a = {"source_id": "1", "excerpt": "Library X is vulnerable before v1.4."}
    item_b = {"source_id": "2", "excerpt": "Library X v1.4 contains the security patch."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship in ["RELATED", "SUPPORTS"]


def test_version_v7_same_major_minor_patch_exact_match():
    item_a = {"source_id": "1", "excerpt": "Django 3.2.1 is unpatched against header injection."}
    item_b = {"source_id": "2", "excerpt": "Django 3.2.1 is patched and secure."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_version_v8_different_patch_releases():
    item_a = {"source_id": "1", "excerpt": "Django 3.2.1 is unpatched against header injection."}
    item_b = {"source_id": "2", "excerpt": "Django 3.2.5 remediates header injection."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship in ["RELATED", "SUPPORTS"]


def test_version_v9_no_version_vs_explicit_version():
    item_a = {"source_id": "1", "excerpt": "OpenSSL is vulnerable to Heartbleed."}
    item_b = {"source_id": "2", "excerpt": "OpenSSL 1.0.1g fixes Heartbleed vulnerability."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship in ["RELATED", "SUPPORTS"]


def test_version_v10_explicit_same_version_different_words():
    item_a = {"source_id": "1", "excerpt": "Nginx v1.18.0 allows unencrypted HTTP traffic."}
    item_b = {"source_id": "2", "excerpt": "Nginx v1.18.0 restricts traffic strictly to HTTPS."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


# =============================================================================
# GROUP 2: 10 SECURITY STATUS TEST CASES
# =============================================================================

def test_status_s1_vulnerable_vs_secure_same_file():
    item_a = {"source_id": "1", "excerpt": "Critical unpatched SQL injection in auth.py line 42.", "file_path": "auth.py"}
    item_b = {"source_id": "2", "excerpt": "auth.py line 42 is secure and not vulnerable.", "file_path": "auth.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s2_exposed_vs_restricted():
    item_a = {"source_id": "1", "excerpt": "Exposed Prometheus metrics endpoint without authentication.", "file_path": "metrics.py"}
    item_b = {"source_id": "2", "excerpt": "metrics.py requires admin HTTP Basic Auth headers.", "file_path": "metrics.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s3_unquoted_vs_double_quotes():
    item_a = {"source_id": "1", "excerpt": "Unquoted Windows Search Path vulnerability in service binary.", "file_path": "win.cs"}
    item_b = {"source_id": "2", "excerpt": "win.cs path is enclosed in double quotes.", "file_path": "win.cs"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s4_missing_csrf_vs_validates_csrf():
    item_a = {"source_id": "1", "excerpt": "Missing Anti-CSRF token in password reset endpoint.", "file_path": "api/password.py"}
    item_b = {"source_id": "2", "excerpt": "api/password.py validates CSRF header token on all POST requests.", "file_path": "api/password.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s5_open_redirect_vs_relative_urls():
    item_a = {"source_id": "1", "excerpt": "Open Redirect flaw in login redirect parameter.", "file_path": "controllers/auth.js"}
    item_b = {"source_id": "2", "excerpt": "controllers/auth.js restricts redirect parameter to relative URLs only.", "file_path": "controllers/auth.js"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s6_memory_leak_vs_no_leaks():
    item_a = {"source_id": "1", "excerpt": "Memory leak in C++ parser module causing Denial of Service.", "file_path": "native/parser.cpp"}
    item_b = {"source_id": "2", "excerpt": "native/parser.cpp has no memory leaks and frees all buffers.", "file_path": "native/parser.cpp"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s7_hardcoded_secret_vs_env_vars():
    item_a = {"source_id": "1", "excerpt": "Hardcoded database password in app/config.py.", "file_path": "app/config.py"}
    item_b = {"source_id": "2", "excerpt": "app/config.py loads database password strictly from environment variables.", "file_path": "app/config.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s8_broken_access_control_vs_role_middleware():
    item_a = {"source_id": "1", "excerpt": "Broken Access Control on admin route /admin/users.", "file_path": "admin.py"}
    item_b = {"source_id": "2", "excerpt": "admin.py restricts all routes to admin role via RequireRole middleware.", "file_path": "admin.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s9_race_condition_vs_row_locking():
    item_a = {"source_id": "1", "excerpt": "Race condition in credit balance transfer handler.", "file_path": "bank.py"}
    item_b = {"source_id": "2", "excerpt": "bank.py uses SELECT FOR UPDATE row locking to prevent race conditions.", "file_path": "bank.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_status_s10_command_injection_vs_shell_false():
    item_a = {"source_id": "1", "excerpt": "Command injection vulnerability in backup script run_cmd function.", "file_path": "backup.py"}
    item_b = {"source_id": "2", "excerpt": "backup.py run_cmd function is safe from command injection as shell=False is passed.", "file_path": "backup.py"}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


# =============================================================================
# GROUP 3: 10 SAME-CVE CONTRADICTION TEST CASES
# =============================================================================

def test_cve_c1_same_cve_opposite_assertion():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-1234 vulnerability affects auth service."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-1234 does not affect auth service; system is unaffected."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_cve_c2_same_cve_patched_assertion():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-8888 vulnerability is unpatched."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-8888 is patched and fixed."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_cve_c3_same_cve_remediation_support():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-9999 SQL injection flaw detected."}
    item_b = {"source_id": "2", "excerpt": "Remediate CVE-2026-9999 by enabling input validation."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "SUPPORTS"


def test_cve_c4_same_cve_vulnerable_vs_clean():
    item_a = {"source_id": "1", "excerpt": "System is vulnerable to CVE-2025-4321."}
    item_b = {"source_id": "2", "excerpt": "System is clean and immune to CVE-2025-4321."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_cve_c5_same_cve_exploitable_vs_mitigated():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-1111 is actively exploitable."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-1111 is mitigated via firewall rule."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_cve_c6_same_cve_insecure_vs_secure():
    item_a = {"source_id": "1", "excerpt": "Insecure SSL setup allows CVE-2024-0001."}
    item_b = {"source_id": "2", "excerpt": "Secure SSL setup prevents CVE-2024-0001."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_cve_c7_same_cve_critical_flaw_vs_safe():
    item_a = {"source_id": "1", "excerpt": "Critical flaw CVE-2026-7777 found in parser."}
    item_b = {"source_id": "2", "excerpt": "Parser is safe from CVE-2026-7777."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_cve_c8_same_cve_unpatched_vs_fixed():
    item_a = {"source_id": "1", "excerpt": "Unpatched flaw CVE-2026-5555."}
    item_b = {"source_id": "2", "excerpt": "Fixed flaw CVE-2026-5555."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_cve_c9_same_cve_exposure_vs_immune():
    item_a = {"source_id": "1", "excerpt": "Data exposure risk CVE-2026-3333."}
    item_b = {"source_id": "2", "excerpt": "System is immune to CVE-2026-3333."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


def test_cve_c10_same_cve_bug_vs_remediated():
    item_a = {"source_id": "1", "excerpt": "Security bug CVE-2026-2222 present."}
    item_b = {"source_id": "2", "excerpt": "Security bug CVE-2026-2222 remediated."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"


# =============================================================================
# GROUP 4: 10 DIFFERENT-CVE NON-CONTRADICTION TEST CASES
# =============================================================================

def test_diff_cve_d1_distinct_cves_related_domain():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-1111 SQL injection vulnerability."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-9999 XSS vulnerability."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"
    assert rel.relationship in ["RELATED", "UNRELATED"]


def test_diff_cve_d2_distinct_cves_vulnerable_and_patched():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-1001 is vulnerable."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-2002 is patched."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"


def test_diff_cve_d3_distinct_cves_same_component():
    item_a = {"source_id": "1", "excerpt": "PostgreSQL flaw CVE-2024-1111."}
    item_b = {"source_id": "2", "excerpt": "PostgreSQL fix for CVE-2024-2222."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"


def test_diff_cve_d4_distinct_cves_unrelated_topics():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-0001 in OpenSSL."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-9999 in Linux Kernel."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"


def test_diff_cve_d5_cve_vs_general_policy():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-1234 vulnerability."}
    item_b = {"source_id": "2", "excerpt": "Employee annual leave policy."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "UNRELATED"


def test_diff_cve_d6_distinct_cves_auth_module():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-1234 in auth module."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-5678 in payment module."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"


def test_diff_cve_d7_distinct_cves_docker_and_nginx():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-1122 in Docker image."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-3344 in Nginx web server."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"


def test_diff_cve_d8_distinct_cves_python_and_redis():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-5544 in Python 3.10."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-6677 in Redis server."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"


def test_diff_cve_d9_distinct_cves_jwt_and_session():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-8811 in JWT library."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-9922 in Session store."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"


def test_diff_cve_d10_distinct_cves_crypto_and_parser():
    item_a = {"source_id": "1", "excerpt": "CVE-2026-1414 in AES crypto."}
    item_b = {"source_id": "2", "excerpt": "CVE-2026-2525 in XML parser."}
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship != "CONTRADICTS"
