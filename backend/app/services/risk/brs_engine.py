"""
NOVA — Banking Risk Score (BRS) Engine
Implements deterministic, multi-factor risk scoring for individual security findings
and scan-level risk score roll-up.

Risk score incorporates:
  1. CVSS base score (30%)
  2. Exploitability (15%)
  3. Business Criticality (20%)
  4. Internet Exposure (10%)
  5. Compliance Impact (10%)
  6. Asset Value (10%)
  7. Historical Incidents (5%)
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.schemas.finding import RawFinding
from app.services.compliance.compliance_mapper import ComplianceMappingData


@dataclass
class FactorWeights:
    cvss: float = 0.30
    exploitability: float = 0.15
    business_criticality: float = 0.20
    internet_exposure: float = 0.10
    compliance_impact: float = 0.10
    asset_value: float = 0.10
    historical_incidents: float = 0.05


@dataclass
class ModuleDefinition:
    name: str
    keywords: List[str]
    criticality_weight: float
    asset_value: float
    is_internet_facing_default: bool = False
    is_default: bool = False
    description: Optional[str] = None


@dataclass
class FindingScore:
    brs: float
    sub_scores: Dict[str, float]
    factor_weights: Dict[str, float]


DEFAULT_FACTOR_WEIGHTS = FactorWeights(
    cvss=0.30,
    exploitability=0.15,
    business_criticality=0.20,
    internet_exposure=0.10,
    compliance_impact=0.10,
    asset_value=0.10,
    historical_incidents=0.05,
)

# Ordered by descending criticality weight (Payments -> Auth -> Customer -> Admin -> Infra -> Reporting -> General)
DEFAULT_MODULES: List[ModuleDefinition] = [
    ModuleDefinition(
        name="Payments",
        keywords=[
            "payment",
            "pay",
            "transaction",
            "transfer",
            "remittance",
            "upi",
            "neft",
            "imps",
            "rtgs",
        ],
        criticality_weight=10.0,
        asset_value=10.0,
        is_internet_facing_default=True,
        is_default=False,
        description="Payment initiation, transfers, settlement",
    ),
    ModuleDefinition(
        name="Authentication",
        keywords=[
            "auth",
            "login",
            "jwt",
            "session",
            "oauth",
            "token",
            "password",
            "credential",
            "2fa",
            "mfa",
        ],
        criticality_weight=8.5,
        asset_value=8.0,
        is_internet_facing_default=True,
        is_default=False,
        description="Login, session management, identity",
    ),
    ModuleDefinition(
        name="Customer Data",
        keywords=[
            "customer",
            "kyc",
            "pii",
            "personal",
            "account",
            "user_data",
            "profile",
            "aadhaar",
            "pan",
        ],
        criticality_weight=7.0,
        asset_value=9.0,
        is_internet_facing_default=True,
        is_default=False,
        description="PII, KYC records, customer account data",
    ),
    ModuleDefinition(
        name="Admin",
        keywords=["admin", "management", "superuser", "dashboard"],
        criticality_weight=5.5,
        asset_value=6.0,
        is_internet_facing_default=False,
        is_default=False,
        description="Administrative/back-office interfaces",
    ),
    ModuleDefinition(
        name="Infrastructure",
        keywords=["dockerfile", "docker-compose", ".github", "helm", "k8s", "terraform"],
        criticality_weight=5.0,
        asset_value=6.0,
        is_internet_facing_default=False,
        is_default=False,
        description="Deployment/container/CI configuration",
    ),
    ModuleDefinition(
        name="Reporting",
        keywords=["report", "audit", "log", "analytics", "statement", "export"],
        criticality_weight=3.0,
        asset_value=3.0,
        is_internet_facing_default=False,
        is_default=False,
        description="Reporting, analytics, audit trails",
    ),
    ModuleDefinition(
        name="General",
        keywords=[],
        criticality_weight=4.0,
        asset_value=4.0,
        is_internet_facing_default=False,
        is_default=True,
        description="Fallback module when no keyword matches",
    ),
]


def classify_module(
    finding: Any,
    modules: List[ModuleDefinition] = DEFAULT_MODULES,
) -> ModuleDefinition:
    """Classify a finding into a BusinessModule based on file_path, title, and category keywords.

    Modules are matched in list order (highest criticality wins).
    """
    file_path = (getattr(finding, "file_path", None) or "").lower()
    title = (getattr(finding, "title", None) or "").lower()
    category = (getattr(finding, "category", None) or "").lower()

    text_to_search = f"{file_path} {title} {category}"

    for module in modules:
        if module.is_default:
            continue
        for kw in module.keywords:
            if kw in text_to_search:
                return module

    # Return default fallback module
    for module in modules:
        if module.is_default:
            return module

    return modules[-1]


def compliance_framework_count(mapping: Optional[Any]) -> int:
    """Count populated regulatory framework clauses (RBI, PCI, SWIFT)."""
    if mapping is None:
        return 0
    count = 0
    for attr in ("rbi_clause", "pci_clause", "swift_clause"):
        val = getattr(mapping, attr, None)
        if val and str(val).strip():
            count += 1
    return count


def _calculate_risk_level(brs: float) -> str:
    """Classify BRS numeric score into discrete risk tiers: Low (<35), Medium (35-57.9), High (58-81.9), Critical (>=82)."""
    if brs < 35.0:
        return "Low"
    elif brs < 58.0:
        return "Medium"
    elif brs < 82.0:
        return "High"
    else:
        return "Critical"


def _residual_uncertainty_baseline(coverage_ratio: float) -> float:
    """Compute base floor for zero-finding scans based on scanner suite coverage."""
    clamped = max(0.0, min(1.0, float(coverage_ratio)))
    return 5.0 + 3.0 * (1.0 - clamped)


def score_finding(
    finding: Any,
    *,
    module: ModuleDefinition,
    factor_weights: FactorWeights = DEFAULT_FACTOR_WEIGHTS,
    compliance_framework_count: int = 0,
    historical_incident_count: int = 0,
) -> FindingScore:
    """Calculate the Banking Risk Score (0-100) for a single finding."""
    cvss = float(getattr(finding, "cvss", 0.0) or 0.0)
    severity = str(getattr(finding, "severity", "MEDIUM") or "MEDIUM").upper()
    category = str(getattr(finding, "category", "") or "").lower()
    cve = getattr(finding, "cve", None)
    file_path = str(getattr(finding, "file_path", "") or "").lower()
    title = str(getattr(finding, "title", "") or "").lower()

    # 1. CVSS Sub-score (0-10)
    sub_cvss = max(0.0, min(10.0, cvss))

    # 2. Exploitability Sub-score (0-10)
    if severity == "CRITICAL":
        sub_exploit = 9.5
    elif severity == "HIGH":
        sub_exploit = 7.5
    elif severity == "MEDIUM":
        sub_exploit = 5.0
    elif severity == "LOW":
        sub_exploit = 2.5
    else:
        sub_exploit = 1.0

    if category in ("sql_injection", "command_injection", "unsafe_deserialization", "path_traversal"):
        sub_exploit = min(10.0, sub_exploit + 0.3)

    if cve:
        sub_exploit = max(sub_exploit, 7.5)

    # 3. Business Criticality Sub-score (0-10)
    sub_criticality = float(module.criticality_weight)

    # 4. Internet Exposure Sub-score (0-10)
    base_exposure = 7.0 if module.is_internet_facing_default else 3.0
    path_text = f"{file_path} {title}"
    if any(k in path_text for k in ("public", "api", "route", "endpoint", "webhook", "controller", "handler", "gateway", "views")):
        sub_exposure = min(10.0, base_exposure + 2.5)
    elif any(k in path_text for k in ("internal", "batch", "job", "migration", "scripts", "offline")):
        sub_exposure = max(1.0, base_exposure - 2.0)
    else:
        sub_exposure = base_exposure

    # 5. Compliance Impact Sub-score (0-10)
    sub_compliance = min(10.0, compliance_framework_count * 3.3333333333333335)

    # 6. Asset Value Sub-score (0-10)
    sub_asset = float(module.asset_value)

    # 7. Historical Incidents Sub-score (0-10)
    sub_incidents = min(10.0, historical_incident_count * 0.8)

    sub_scores = {
        "cvss": round(sub_cvss, 2),
        "exploitability": round(sub_exploit, 2),
        "business_criticality": round(sub_criticality, 2),
        "internet_exposure": round(sub_exposure, 2),
        "compliance_impact": round(sub_compliance, 2),
        "asset_value": round(sub_asset, 2),
        "historical_incidents": round(sub_incidents, 2),
    }

    weights_dict = {
        "cvss": factor_weights.cvss,
        "exploitability": factor_weights.exploitability,
        "business_criticality": factor_weights.business_criticality,
        "internet_exposure": factor_weights.internet_exposure,
        "compliance_impact": factor_weights.compliance_impact,
        "asset_value": factor_weights.asset_value,
        "historical_incidents": factor_weights.historical_incidents,
    }

    total_weight = sum(weights_dict.values())
    if total_weight == 0:
        brs = sub_cvss * 10.0
    else:
        weighted_sum = sum(sub_scores[k] * weights_dict[k] for k in weights_dict)
        brs = (weighted_sum / total_weight) * 10.0

    brs = min(100.0, max(0.0, brs))
    return FindingScore(brs=round(brs, 2), sub_scores=sub_scores, factor_weights=weights_dict)


def rollup_scan_brs(brs_scores: List[float]) -> float:
    """Aggregate individual finding BRS scores into a scan-level Banking Risk Score.

    Combines the maximum finding score (80%) and self-weighted average (20%),
    plus a bounded volume adjustment capped at +9.0.
    """
    if not brs_scores:
        return 0.0
    if len(brs_scores) == 1:
        return float(brs_scores[0])

    max_score = max(brs_scores)
    sum_scores = sum(brs_scores)
    if sum_scores == 0:
        return 0.0

    self_weighted_avg = sum(s * s for s in brs_scores) / sum_scores
    base_score = 0.80 * max_score + 0.20 * self_weighted_avg

    n = len(brs_scores)
    volume_adjustment = min(9.0, 1.7 * math.log(n))

    final_score = base_score + volume_adjustment
    final_score = min(100.0, min(max_score + 9.0, final_score))
    return round(final_score, 2)
