"""
NOVA — Finding Enrichment Service
Enriches findings with taxonomy metadata (CWE, OWASP, MITRE),
compliance regulatory clauses (RBI, PCI, SWIFT), business module classification,
and Banking Risk Score (BRS).
"""

from typing import Any, Dict, List, Optional

from app.services.aggregation.cwe_owasp_mapper import CweOwaspMapper
from app.services.compliance.compliance_mapper import get_compliance_mapper
from app.services.risk.brs_engine import (
    DEFAULT_FACTOR_WEIGHTS,
    DEFAULT_MODULES,
    _calculate_risk_level,
    classify_module,
    compliance_framework_count,
    score_finding,
)


def enrich_finding(
    finding_data: Dict[str, Any],
    *,
    modules: Optional[List[Any]] = None,
    factor_weights: Optional[Any] = None,
    historical_incident_count: int = 0,
) -> Dict[str, Any]:
    """Enrich a finding dictionary with taxonomy, compliance, module, and BRS score."""
    enriched = dict(finding_data)
    category = enriched.get("category") or "unknown"
    cwe_id = enriched.get("cwe_id")
    title = enriched.get("title") or ""

    # 1. CWE, OWASP Top 10, MITRE ATT&CK taxonomy
    tax_mapping = CweOwaspMapper.map_taxonomy(category, cwe_id, title)
    if not enriched.get("cwe_id") and tax_mapping.cwe_id:
        enriched["cwe_id"] = tax_mapping.cwe_id
    if not enriched.get("cwe_name") and tax_mapping.cwe_name:
        enriched["cwe_name"] = tax_mapping.cwe_name
    if not enriched.get("owasp_category") and tax_mapping.owasp_category:
        enriched["owasp_category"] = tax_mapping.owasp_category
    if not enriched.get("owasp_name") and tax_mapping.owasp_name:
        enriched["owasp_name"] = tax_mapping.owasp_name
    if not enriched.get("mitre_technique_ids") and tax_mapping.mitre_technique_ids:
        enriched["mitre_technique_ids"] = tax_mapping.mitre_technique_ids

    # 2. Regulatory compliance mapping (RBI, PCI DSS, SWIFT)
    mapper = get_compliance_mapper()
    comp_data = mapper.map_finding(category, enriched.get("cwe_id"))
    if not enriched.get("rbi_clause") and comp_data.rbi_clause:
        enriched["rbi_clause"] = comp_data.rbi_clause
    if not enriched.get("pci_clause") and comp_data.pci_clause:
        enriched["pci_clause"] = comp_data.pci_clause
    if not enriched.get("swift_clause") and comp_data.swift_clause:
        enriched["swift_clause"] = comp_data.swift_clause

    # 3. Business module classification
    module_list = modules or DEFAULT_MODULES
    class_module = classify_module(enriched, module_list)
    enriched["module"] = class_module.name

    # 4. Banking Risk Score (BRS) calculation
    weights = factor_weights or DEFAULT_FACTOR_WEIGHTS
    comp_count = compliance_framework_count(comp_data)
    finding_score = score_finding(
        enriched,
        module=class_module,
        factor_weights=weights,
        compliance_framework_count=comp_count,
        historical_incident_count=historical_incident_count,
    )
    enriched["brs"] = finding_score.brs
    enriched["brs_risk_level"] = _calculate_risk_level(finding_score.brs)

    # 5. Cross-scanner confidence calculation: C_finding = 1 - PROD(1 - c_i)
    from app.services.assistant.evidence_fusion import evidence_fusion_engine
    sources = enriched.get("sources") or [enriched.get("source", "scanner")]
    enriched["scanner_confidence"] = evidence_fusion_engine.calculate_cross_scanner_confidence(sources)

    return enriched
