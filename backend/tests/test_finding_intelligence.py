"""
NOVA — Finding Intelligence Unit Tests
Targets the pure functions in
app/services/finding_intelligence/intelligence_service.py — no database,
no ONNX model, no LLM call required. `build_intelligence` itself is
integration-level (real DB + real local models + optionally a real LLM)
and covered by the manual testing walkthrough instead.
"""

import json

import pytest

from app.models.finding import Finding
from app.schemas.finding import RawFinding
from app.services.finding_intelligence.intelligence_service import (
    Citation,
    build_context_block,
    build_retrieval_query,
    build_why_detected,
    parse_generated_explanation,
)


def _finding(**overrides) -> Finding:
    defaults = dict(
        title="Hardcoded database password",
        severity="CRITICAL",
        category="hardcoded_secret",
        source="semgrep",
        sources=["semgrep", "secrets"],
        cvss=9.1,
        file_path="app/core/config.py",
        line_number=42,
        description="A hardcoded credential was found in source code.",
        package=None,
        package_version=None,
        cve=None,
        cwe_id="CWE-798",
        cwe_name="Use of Hard-coded Credentials",
        owasp_category="A07",
        owasp_name="Identification and Authentication Failures",
        mitre_technique_ids=["T1552"],
        pci_clause="PCI-DSS 8.2.1",
        rbi_clause="RBI IT Framework 4.2",
        swift_clause="SWIFT CSP 2.1",
    )
    defaults.update(overrides)
    return Finding(**defaults)


def _raw(finding: Finding) -> RawFinding:
    return RawFinding(
        title=finding.title,
        severity=finding.severity,
        category=finding.category,
        source=finding.source,
        cvss=finding.cvss,
        file_path=finding.file_path,
        line_number=finding.line_number,
        description=finding.description,
        package=finding.package,
        package_version=finding.package_version,
        cve=finding.cve,
    )


class TestBuildWhyDetected:
    def test_includes_scanner_severity_category(self):
        text = build_why_detected(_finding())
        assert "semgrep" in text
        assert "secrets" in text
        assert "critical" in text.lower()
        assert "hardcoded_secret" in text

    def test_includes_cwe_when_present(self):
        text = build_why_detected(_finding())
        assert "CWE-798" in text
        assert "Use of Hard-coded Credentials" in text

    def test_omits_cwe_when_absent(self):
        text = build_why_detected(_finding(cwe_id=None, cwe_name=None))
        assert "CWE" not in text

    def test_includes_cve_when_present(self):
        text = build_why_detected(_finding(cve="CVE-2023-1234"))
        assert "CVE-2023-1234" in text

    def test_includes_file_and_line(self):
        text = build_why_detected(_finding())
        assert "app/core/config.py:42" in text

    def test_omits_line_when_file_has_no_line_number(self):
        text = build_why_detected(_finding(line_number=None))
        assert "app/core/config.py" in text
        assert ":42" not in text

    def test_deduplicates_sources(self):
        text = build_why_detected(_finding(sources=["semgrep", "semgrep"]))
        assert text.count("semgrep") == 1


class TestBuildRetrievalQuery:
    def test_includes_cwe_and_owasp_name(self):
        finding = _finding()
        query = build_retrieval_query(_raw(finding), finding)
        assert "CWE-798" in query
        assert "Use of Hard-coded Credentials" in query
        assert "Identification and Authentication Failures" in query

    def test_excludes_verbose_compliance_clause_text_and_mitre_ids(self):
        # Deliberately dropped from THIS query (see build_retrieval_query's
        # docstring) — verbose clause prose and opaque MITRE IDs measurably
        # hurt the cross-encoder reranker's score in testing. They're still
        # shown in full in the deterministic response fields and in the
        # generation prompt elsewhere — just not fed into this query.
        finding = _finding()
        query = build_retrieval_query(_raw(finding), finding)
        assert finding.pci_clause not in query
        assert finding.rbi_clause not in query
        assert finding.swift_clause not in query
        assert "T1552" not in query

    def test_never_includes_raw_title_or_description(self):
        # The sanitized fragment substitutes a category-templated generic
        # description — the raw scanner-authored title/description must
        # never reach this query (same boundary app/services/ai/sanitizer.py
        # enforces for the LLM-facing path).
        finding = _finding(title="super secret internal repo naming leak")
        query = build_retrieval_query(_raw(finding), finding)
        assert "super secret internal repo naming leak" not in query

    def test_falls_back_to_category_when_no_cwe(self):
        finding = _finding(cwe_id=None, cwe_name=None, owasp_category=None, owasp_name=None)
        query = build_retrieval_query(_raw(finding), finding)
        assert "hardcoded secret" in query

    def test_includes_package_when_present(self):
        finding = _finding(package="requests", package_version="2.25.0")
        query = build_retrieval_query(_raw(finding), finding)
        assert "requests package" in query


def _citation(**overrides) -> Citation:
    defaults = dict(
        document_id="doc-1",
        filename="owasp-top10.pdf",
        page_number=12,
        section_path="A03 Injection",
        heading="A03 Injection",
        similarity_score=0.8,
        rerank_score=4.1,
        excerpt="Injection flaws occur when untrusted data is sent to an interpreter.",
    )
    defaults.update(overrides)
    return Citation(**defaults)


class TestBuildContextBlock:
    def test_numbers_and_includes_source_details(self):
        block = build_context_block([_citation()])
        assert "[1]" in block
        assert "Source: owasp-top10.pdf" in block
        assert "Section: A03 Injection" in block
        assert "Page: 12" in block
        assert "Injection flaws occur" in block

    def test_empty_list_yields_empty_block(self):
        assert build_context_block([]) == ""


class TestParseGeneratedExplanation:
    def test_parses_plain_json(self):
        payload = json.dumps({"plain_english_explanation": "It's bad.", "code_example": None})
        parsed = parse_generated_explanation(payload)
        assert parsed["plain_english_explanation"] == "It's bad."
        assert parsed["code_example"] is None

    def test_strips_markdown_code_fences(self):
        payload = "```json\n" + json.dumps({"business_impact": "Costly."}) + "\n```"
        parsed = parse_generated_explanation(payload)
        assert parsed["business_impact"] == "Costly."

    def test_raises_on_malformed_json(self):
        with pytest.raises(json.JSONDecodeError):
            parse_generated_explanation("not json at all")

    def test_raises_when_top_level_is_not_an_object(self):
        with pytest.raises(json.JSONDecodeError):
            parse_generated_explanation("[1, 2, 3]")
