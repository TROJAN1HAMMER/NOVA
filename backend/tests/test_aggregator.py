"""
NOVA — Security Scan Findings Aggregator Unit Tests
Tests deduplication, severity normalization, multi-tool merging,
BRS rollup, compliance summary generation, and zero-finding residual uncertainty.
"""

import pytest

from app.services.aggregation.aggregator import (
    _deduplication_key,
    aggregate_scanner_results,
)


class TestDeduplicationKey:
    def test_cve_and_package(self):
        finding = {
            "package": "requests",
            "cve": "CVE-2023-32681",
            "category": "vulnerable_dependency",
        }
        key = _deduplication_key(finding)
        assert key == "dep:requests:cve-2023-32681"

    def test_file_path_and_line_number(self):
        finding = {
            "file_path": "app/core/config.py",
            "line_number": 42,
            "category": "hardcoded_secret",
        }
        key = _deduplication_key(finding)
        assert key == "loc:app/core/config.py:42:hardcoded_secret"

    def test_file_path_without_line_number(self):
        finding = {
            "file_path": "certs/id_rsa",
            "category": "hardcoded_secret",
            "title": "Private key committed",
        }
        key = _deduplication_key(finding)
        assert key == "file:certs/id_rsa:hardcoded_secret:private key committed"

    def test_generic_fallback(self):
        finding = {
            "category": "security_misconfiguration",
            "title": "Debug mode enabled in production",
        }
        key = _deduplication_key(finding)
        assert key == "gen:security_misconfiguration:debug mode enabled in production"


class TestAggregateScannerResults:
    def test_empty_results_zero_finding_baseline(self):
        scanner_results = [
            {"scanner": "semgrep", "success": True, "findings": []},
            {"scanner": "secrets", "success": True, "findings": []},
            {"scanner": "pip-audit", "success": True, "findings": []},
        ]
        enriched, severity_summary, scan_brs, scan_risk_level, comp_summary = (
            aggregate_scanner_results(scanner_results)
        )

        assert enriched == []
        assert severity_summary["total"] == 0
        assert severity_summary["CRITICAL"] == 0
        assert scan_brs == 5.0
        assert scan_risk_level == "Low"
        assert comp_summary["rbi_it_framework"]["status"] == "compliant"
        assert comp_summary["pci_dss_v4"]["status"] == "compliant"
        assert comp_summary["swift_csp"]["status"] == "compliant"

    def test_empty_results_partial_tool_failure_residual_uncertainty(self):
        # 1 out of 3 tools succeeded -> coverage 1/3 ~ 0.333 -> residual baseline > 5.0
        scanner_results = [
            {"scanner": "semgrep", "success": True, "findings": []},
            {"scanner": "joern", "success": False, "findings": []},
            {"scanner": "secrets", "success": False, "findings": []},
        ]
        enriched, severity_summary, scan_brs, scan_risk_level, comp_summary = (
            aggregate_scanner_results(scanner_results)
        )

        assert enriched == []
        assert scan_brs > 5.0
        assert severity_summary["total"] == 0

    def test_deduplication_merges_sources_and_takes_highest_severity(self):
        scanner_results = [
            {
                "scanner": "semgrep",
                "success": True,
                "findings": [
                    {
                        "title": "Hardcoded secret",
                        "severity": "MEDIUM",
                        "category": "hardcoded_secret",
                        "cvss": 5.0,
                        "file_path": "app/config.py",
                        "line_number": 10,
                    }
                ],
            },
            {
                "scanner": "secrets",
                "success": True,
                "findings": [
                    {
                        "title": "Hardcoded secret in config",
                        "severity": "CRITICAL",
                        "category": "hardcoded_secret",
                        "cvss": 9.5,
                        "file_path": "app/config.py",
                        "line_number": 10,
                    }
                ],
            },
        ]

        enriched, severity_summary, scan_brs, scan_risk_level, comp_summary = (
            aggregate_scanner_results(scanner_results)
        )

        assert len(enriched) == 1
        finding = enriched[0]
        assert finding["occurrence_count"] == 2
        assert "semgrep" in finding["sources"]
        assert "secrets" in finding["sources"]
        assert finding["severity"] == "CRITICAL"
        assert finding["cvss"] == 9.5
        assert severity_summary["CRITICAL"] == 1
        assert severity_summary["MEDIUM"] == 0
        assert severity_summary["total"] == 1
        assert finding["cwe_id"] == "CWE-798"
        assert finding["pci_clause"] is not None
        assert finding["brs"] > 0
        assert scan_brs > 0
        assert comp_summary["rbi_it_framework"]["violations_count"] == 1

    def test_multiple_distinct_findings_enrichment_and_scoring(self):
        scanner_results = [
            {
                "scanner": "semgrep",
                "success": True,
                "findings": [
                    {
                        "title": "SQL Injection",
                        "severity": "HIGH",
                        "category": "sql_injection",
                        "cvss": 8.5,
                        "file_path": "app/db.py",
                        "line_number": 20,
                    },
                ],
            },
            {
                "scanner": "pip-audit",
                "success": True,
                "findings": [
                    {
                        "title": "Vulnerable library",
                        "severity": "MEDIUM",
                        "category": "vulnerable_dependency",
                        "cvss": 6.0,
                        "package": "requests",
                        "cve": "CVE-2023-32681",
                    }
                ],
            },
        ]

        enriched, severity_summary, scan_brs, scan_risk_level, comp_summary = (
            aggregate_scanner_results(scanner_results)
        )

        assert len(enriched) == 2
        assert severity_summary["HIGH"] == 1
        assert severity_summary["MEDIUM"] == 1
        assert severity_summary["total"] == 2
        assert scan_brs > 0
        assert comp_summary["rbi_it_framework"]["violations_count"] == 2
        assert comp_summary["pci_dss_v4"]["violations_count"] == 2
        assert comp_summary["swift_csp"]["violations_count"] == 2
