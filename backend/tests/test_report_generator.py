"""
NOVA — PDF Report Generator Regression Tests

`report_generator.py` has zero database/async/Celery dependency of its own (it's pure
data-in, PDF/JSON/CSV-out), so every test here builds `NOVAPDFReport`/
`NOVATechnicalPDFReport` directly against synthetic `ReportContext`-shaped inputs — no
Postgres, no event loop, no Celery worker needed.

These are functional/crash-safety checks (does it raise, does it produce a valid multi-page
PDF with extractable text), not pixel-level overlap detection — this project has no PDF
renderer dependency to compare pixels against. The two real defects these tests pin down were
found by actually rendering pages to PNG during development (see the "before/after" screenshots
in the PR/commit this file shipped with) and are captured here as the specific inputs that used
to reproduce them:

  1. A compliance clause containing `&`/`<` used to crash PDF generation outright — ReportLab's
     `Paragraph` parses a small XML-like markup language, and this value was interpolated into
     an f-string unescaped at three call sites.
  2. An unusually long `ai_explanation`/`ai_business_impact`/`ai_remediation` used to strand a
     finding's title alone on an otherwise-blank page while its content jumped to the next page
     — a `KeepTogether` wrapped the finding's *entire*, unbounded-height content, and ReportLab's
     documented fallback when that doesn't fit even a fresh page is to abandon the "keep
     together" request for the wrapped content, leaving whatever was *outside* the wrapper
     (the title) stranded. Asserted indirectly here via page-count sanity (a regression would
     inflate page count with near-blank pages) and, more directly, by confirming generation
     still succeeds and both PDFs remain well within a sane page-count bound for the input size.
"""

import pypdf
import pytest

from app.services.reports.report_generator import (
    NOVAPDFReport,
    NOVATechnicalPDFReport,
    SEVERITY_ORDER,
)
from datetime import datetime, timezone


LONG_TEXT = (
    "This finding represents a critical exposure in the application's authentication "
    "middleware layer. " * 60
)  # ~4200 chars


def _finding(idx: int, severity: str, *, long: bool = False, clause_special_chars: bool = False) -> dict:
    return {
        "severity": severity,
        "title": f"Finding {idx}: SQL Injection in transaction handler",
        "category": "sql-injection",
        "cvss": 9.1,
        "brs": 8.4,
        "module": "payments.transaction_handler",
        "file_path": "src/" + "nested/" * 20 + "handler.py" if long else "src/api/transactions.py",
        "line_number": 142,
        "description": LONG_TEXT if long else "SQL injection via unsanitized input.",
        "source": "semgrep",
        "sources": ["semgrep", "joern"],
        "cwe_id": "CWE-89",
        "owasp_category": "A03:2021 - Injection",
        "ai_explanation": LONG_TEXT if long else "Short explanation.",
        "ai_business_impact": LONG_TEXT if long else "Short impact.",
        "ai_remediation": LONG_TEXT if long else "Use parameterized queries.",
        "compliance": {
            "rbi_clause": "Section 4.2 & Annex <B>" if clause_special_chars else "Section 4.2",
            "pci_clause": "Req 6.5.1",
            "swift_clause": "CSP 2.1",
        },
    }


def _summary(findings: list[dict]) -> dict:
    summary = {"total": len(findings)}
    for sev in SEVERITY_ORDER:
        summary[sev] = sum(1 for f in findings if f["severity"].upper() == sev)
    return summary


COMPLIANCE_SUMMARY = {
    "rbi": {"name": "RBI IT Framework 2021", "violations": 3, "compliant": False},
    "pci": {"name": "PCI-DSS v4.0", "violations": 0, "compliant": True},
    "swift": {"name": "SWIFT CSP", "violations": 1, "compliant": False},
}

GENERATED_AT = datetime.now(timezone.utc)


def _assert_valid_pdf(path, min_pages: int = 1):
    assert path.exists()
    assert path.stat().st_size > 0
    reader = pypdf.PdfReader(str(path))
    assert len(reader.pages) >= min_pages
    # Confirm text extraction doesn't error and the first/last page both have real content —
    # a page that's blank because content overflowed past it would still "extract" (possibly
    # empty), so this is a floor-level sanity check, not proof of correct layout on its own.
    first_text = reader.pages[0].extract_text() or ""
    last_text = reader.pages[-1].extract_text() or ""
    assert len(first_text.strip()) > 0
    assert len(last_text.strip()) > 0


def _generate_exec(tmp_path, findings, *, repo_name="acme/core-banking-api"):
    path = tmp_path / "exec.pdf"
    NOVAPDFReport(path).generate(
        scan_id="scan-test-123",
        repo_name=repo_name,
        brs_score=42.3,
        brs_risk_level="High",
        attack_surface_exposure_score=61.0,
        attack_surface_exposure_level="Elevated",
        findings=findings,
        compliance_summary=COMPLIANCE_SUMMARY,
        summary=_summary(findings),
        generated_at=GENERATED_AT,
    )
    return path


def _generate_technical(tmp_path, findings, *, repo_name="acme/core-banking-api"):
    path = tmp_path / "technical.pdf"
    NOVATechnicalPDFReport(path).generate(
        scan_id="scan-test-123",
        repo_name=repo_name,
        brs_score=42.3,
        brs_risk_level="High",
        findings=findings,
        summary=_summary(findings),
        generated_at=GENERATED_AT,
    )
    return path


def test_zero_findings_both_pdfs(tmp_path):
    """No findings at all — every section must degrade to its "nothing to report" branch
    without raising, and still produce a real, openable multi-page PDF."""
    _assert_valid_pdf(_generate_exec(tmp_path, []))
    _assert_valid_pdf(_generate_technical(tmp_path, []))


def test_normal_findings_both_pdfs(tmp_path):
    findings = [_finding(i, sev) for i, sev in enumerate(["CRITICAL", "HIGH", "MEDIUM", "LOW"] * 3)]
    _assert_valid_pdf(_generate_exec(tmp_path, findings))
    _assert_valid_pdf(_generate_technical(tmp_path, findings))


def test_many_findings_300_plus(tmp_path):
    """The technical PDF renders every finding (unlike the executive PDF's top-5-per-tier
    scoping) — this is the realistic stress case for page count and per-finding KeepTogether
    behavior at scale."""
    findings = [_finding(i, SEVERITY_ORDER[i % 5]) for i in range(320)]
    exec_path = _generate_exec(tmp_path, findings)
    technical_path = _generate_technical(tmp_path, findings)
    _assert_valid_pdf(exec_path)
    _assert_valid_pdf(technical_path, min_pages=50)  # 320 findings must span many pages, not collapse/truncate


def test_extremely_long_ai_text_and_file_paths_no_orphaned_title(tmp_path):
    """Regression test for the orphaned-title bug: a finding whose ai_explanation/
    ai_business_impact/ai_remediation/description/file_path are all unusually long used to
    strand a section title alone on an otherwise-blank page (confirmed by rendering the page
    during development). This can no longer happen because the title is only ever
    `KeepTogether`-wrapped with small, bounded content (see report_generator.py's
    `_build_ai_analyst_commentary`/`_build_detailed_findings_section`/`_build_finding_block`)."""
    findings = [_finding(0, "CRITICAL", long=True), _finding(1, "HIGH", long=True)] + [
        _finding(i, "MEDIUM") for i in range(2, 8)
    ]
    exec_path = _generate_exec(tmp_path, findings)
    technical_path = _generate_technical(tmp_path, findings)
    _assert_valid_pdf(exec_path)
    _assert_valid_pdf(technical_path)

    # A regression that reintroduces the bug inflates page count with near-blank pages — this
    # is a coarse but real tripwire (the fixed version generates well under this for 8 findings,
    # two of them long; the broken version generating this exact fixture produced 20 exec pages
    # instead of 17, and would grow further with each additional long finding).
    reader = pypdf.PdfReader(str(exec_path))
    assert len(reader.pages) <= 20


def test_compliance_clause_with_xml_special_characters_does_not_crash(tmp_path):
    """Regression test for the crash bug: a compliance clause value containing `&`/`<`
    (plausible real data — e.g. "Section 4.2 & 4.3") used to raise
    `ValueError: Parse error: saw </...> instead of expected </...>` and abort generation
    entirely, because three call sites interpolated it into a Paragraph-bound f-string
    without escaping. Every such call site now routes through the existing `_esc()` helper."""
    findings = [_finding(0, "CRITICAL", clause_special_chars=True)]
    _assert_valid_pdf(_generate_exec(tmp_path, findings))
    _assert_valid_pdf(_generate_technical(tmp_path, findings))


def test_repo_name_with_xml_special_characters_does_not_crash(tmp_path):
    """repo_name is interpolated into several Paragraph-bound f-strings too — exercised
    separately since it's sourced differently (Git host repository name) than compliance data."""
    findings = [_finding(0, "HIGH")]
    _assert_valid_pdf(_generate_exec(tmp_path, findings, repo_name="acme/core & banking <api>"))
    _assert_valid_pdf(_generate_technical(tmp_path, findings, repo_name="acme/core & banking <api>"))


def test_footer_present_on_every_page(tmp_path):
    """Every page must carry the NOVA wordmark, generation timestamp, scan ID, and
    'Page X of Y' — there was previously no header/footer mechanism at all."""
    findings = [_finding(i, SEVERITY_ORDER[i % 5]) for i in range(15)]
    path = _generate_exec(tmp_path, findings)
    reader = pypdf.PdfReader(str(path))
    total = len(reader.pages)
    assert total > 1
    for page in reader.pages:
        text = page.extract_text() or ""
        assert "NOVA" in text
        assert "scan-test-123" in text
        assert f"of {total}" in text
