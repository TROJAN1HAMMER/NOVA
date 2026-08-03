"""
NOVA — AI Input Sanitizer

Enforces the "never send raw scan results" rule structurally: this is the
only place a `RawFinding` is converted into something that may appear in a
prompt sent to any provider (local or hosted). Everything upstream of this
module (ai_engine.py's callers, the aggregator, the API) works with full
`RawFinding`/`ComplianceMappingData` objects; nothing past this module ever
sees them.

What gets dropped and why:
  - `finding.title` / `finding.description` — scanner-authored text. For
    Semgrep in particular this can echo fragments of the matched rule
    message (occasionally including matched identifiers), and for other
    scanners may reference internal naming. Replaced with a fixed,
    category-keyed generic description (`templates.get_template`) that
    conveys the same class of vulnerability without echoing anything
    scanner- or repo-specific.
  - `finding.file_path` / `finding.line_number` — repo structure/naming.
    Reduced to just the file extension (e.g. ".py"), enough to let the
    model tailor remediation to the language/ecosystem without revealing
    directory layout or file names.
  - Compliance `evidence` (finding titles, file paths) — reduced to just
    the requirement ID / clause reference.

What's kept: category, severity, CVSS, CVE ID and package name/version
(all public identifiers, not scan output) — these materially improve
explanation/remediation quality and carry no repo-specific information.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.schemas.finding import RawFinding
from app.services.ai.templates import get_template
from app.services.compliance.compliance_mapper import ComplianceMappingData


@dataclass(frozen=True)
class SanitizedFinding:
    category: str
    severity: str
    cvss: float
    generic_description: str
    file_extension: Optional[str] = None
    cve: Optional[str] = None
    package: Optional[str] = None
    package_version: Optional[str] = None
    compliance_refs: tuple[str, ...] = field(default_factory=tuple)

    def semantic_tokens(self) -> tuple[str, ...]:
        """
        The fields that define this finding's *class* of vulnerability for
        semantic-cache purposes — deliberately excludes cvss (near-continuous,
        would defeat bucketing) and includes only stable, low-cardinality
        identifiers.
        """
        parts = [self.category.lower(), self.severity.lower()]
        if self.cve:
            parts.append(self.cve.upper())
        if self.package:
            parts.append(self.package.lower())
        return tuple(parts)

    def to_prompt_fragment(self) -> str:
        lines = [
            f"Category: {self.category}",
            f"Severity: {self.severity}",
            f"CVSS Score: {self.cvss}",
        ]
        if self.cve:
            lines.append(f"CVE: {self.cve}")
        if self.package:
            version_suffix = f" {self.package_version}" if self.package_version else ""
            lines.append(f"Affected package: {self.package}{version_suffix}")
        if self.file_extension:
            lines.append(f"File type: {self.file_extension}")
        if self.compliance_refs:
            lines.append(f"Regulatory references: {', '.join(self.compliance_refs)}")
        lines.append(f"Description: {self.generic_description}")
        return "\n".join(lines)


def _file_extension(file_path: Optional[str]) -> Optional[str]:
    if not file_path:
        return None
    suffix = Path(file_path).suffix
    return suffix or None


def _compliance_refs(compliance: Optional[ComplianceMappingData]) -> tuple[str, ...]:
    if compliance is None:
        return ()
    refs = []
    if compliance.rbi_clause:
        refs.append(f"RBI:{compliance.rbi_clause}")
    if compliance.pci_clause:
        refs.append(f"PCI:{compliance.pci_clause}")
    if compliance.swift_clause:
        refs.append(f"SWIFT:{compliance.swift_clause}")
    return tuple(refs)


def sanitize_finding(
    finding: RawFinding,
    compliance: Optional[ComplianceMappingData] = None,
) -> SanitizedFinding:
    """The single conversion point from raw scan output to AI-safe context."""
    template = get_template(finding.category)
    return SanitizedFinding(
        category=finding.category or "unknown",
        severity=finding.severity,
        cvss=finding.cvss,
        generic_description=template["explanation"],
        file_extension=_file_extension(finding.file_path),
        cve=finding.cve,
        package=finding.package,
        package_version=finding.package_version,
        compliance_refs=_compliance_refs(compliance),
    )
