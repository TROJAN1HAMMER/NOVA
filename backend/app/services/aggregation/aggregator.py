"""
NOVA — Security Scan Findings Aggregator
Aggregates and deduplicates raw finding results emitted by all 9 scanners:
  - Static Code Analysis (Semgrep, ast-grep, Joern)
  - Dependency Vulnerabilities (pip-audit, OSV, NVD)
  - Infrastructure & Configurations (Secrets, Docker, YAML)
"""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from app.services.aggregation.enrichment import enrich_finding
from app.services.compliance.compliance_mapper import get_compliance_mapper
from app.services.risk.brs_engine import (
    _calculate_risk_level,
    _residual_uncertainty_baseline,
    rollup_scan_brs,
)


def _deduplication_key(finding: Dict[str, Any]) -> str:
    """Generate a canonical key for finding deduplication across multi-tool scanner outputs."""
    cve = finding.get("cve")
    package = finding.get("package")
    if cve and package:
        return f"dep:{package}:{cve}".lower()

    file_path = finding.get("file_path") or ""
    line_number = finding.get("line_number")
    category = finding.get("category") or "unknown"
    title = finding.get("title") or ""

    if file_path and line_number is not None:
        return f"loc:{file_path}:{line_number}:{category}".lower()
    elif file_path:
        return f"file:{file_path}:{category}:{title}".lower()

    return f"gen:{category}:{title}".lower()


SEVERITY_RANKS = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "INFO": 1,
    "UNKNOWN": 0,
}


def aggregate_scanner_results(
    scanner_results: List[Dict[str, Any]],
    *,
    modules: Optional[List[Any]] = None,
    factor_weights: Optional[Any] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int], float, str, Dict[str, Any]]:
    """Aggregate, deduplicate, and enrich findings across all scanner outputs.

    Returns:
      (enriched_findings, severity_summary, scan_brs, scan_risk_level, compliance_summary)
    """
    total_tools = len(scanner_results) if scanner_results else 1
    successful_tools = 0
    grouped_findings: Dict[str, Dict[str, Any]] = {}

    for res in scanner_results:
        if not isinstance(res, dict):
            continue
        if res.get("success", True):
            successful_tools += 1

        scanner_name = res.get("scanner") or "unknown"
        findings = res.get("findings") or []

        for f in findings:
            if not isinstance(f, dict):
                continue

            f_copy = dict(f)
            key = _deduplication_key(f_copy)

            if key not in grouped_findings:
                f_copy["sources"] = [scanner_name]
                f_copy["source"] = scanner_name
                f_copy["occurrence_count"] = 1
                grouped_findings[key] = f_copy
            else:
                existing = grouped_findings[key]
                existing["occurrence_count"] = existing.get("occurrence_count", 1) + 1
                if scanner_name not in existing.get("sources", []):
                    existing.setdefault("sources", []).append(scanner_name)

                # Keep highest severity & CVSS
                existing_sev = str(existing.get("severity", "UNKNOWN")).upper()
                new_sev = str(f_copy.get("severity", "UNKNOWN")).upper()
                if SEVERITY_RANKS.get(new_sev, 0) > SEVERITY_RANKS.get(existing_sev, 0):
                    existing["severity"] = new_sev

                existing["cvss"] = max(
                    float(existing.get("cvss", 0.0) or 0.0),
                    float(f_copy.get("cvss", 0.0) or 0.0),
                )

    # Enrich each deduplicated finding
    enriched_findings: List[Dict[str, Any]] = []
    severity_counts = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
        "INFO": 0,
        "total": 0,
    }

    brs_scores: List[float] = []

    for f_data in grouped_findings.values():
        enriched = enrich_finding(
            f_data,
            modules=modules,
            factor_weights=factor_weights,
        )
        enriched_findings.append(enriched)

        sev = str(enriched.get("severity", "INFO")).upper()
        if sev in severity_counts:
            severity_counts[sev] += 1
        else:
            severity_counts[sev] = 1
        severity_counts["total"] += 1

        brs = enriched.get("brs", 0.0)
        brs_scores.append(brs)

    # Roll up scan-level BRS
    if not enriched_findings:
        coverage_ratio = float(successful_tools) / float(total_tools) if total_tools > 0 else 1.0
        scan_brs = _residual_uncertainty_baseline(coverage_ratio)
    else:
        scan_brs = rollup_scan_brs(brs_scores)

    scan_risk_level = _calculate_risk_level(scan_brs)

    # Compliance summary
    comp_mapper = get_compliance_mapper()
    finding_objs = [SimpleNamespace(**f) if isinstance(f, dict) else f for f in enriched_findings]
    compliance_summary = comp_mapper.summarize_compliance(finding_objs)

    return (
        enriched_findings,
        severity_counts,
        scan_brs,
        scan_risk_level,
        compliance_summary,
    )
