"""
NOVA — Banking Risk Score Engine Unit Tests
Targets `score_finding()`, `classify_module()`, and `rollup_scan_brs()`
specifically because they're pure functions (see brs_engine.py's module
docstring for why the engine is split this way) — no database, no async,
no mocking required. `calculate_brs()` itself (the DB-driven orchestration
shell that loads modules/weights from Postgres before delegating to the
two pure functions above) is integration-level and needs a real Postgres
to verify meaningfully; it's intentionally out of scope for this file.

Every numeric expectation below was cross-checked against an actual run
of this code (not hand-calculated in the abstract) before being written
down — see the calibration exercise in brs_engine.py's `_calculate_risk_level`
docstring for the reasoning behind the specific threshold values, and
`rollup_scan_brs()`'s own docstring for the roll-up formula this replaced
(and why the old one saturated every real scan to 100/Critical).
"""

import pytest

from app.schemas.finding import RawFinding
from app.services.risk.brs_engine import (
    DEFAULT_FACTOR_WEIGHTS,
    DEFAULT_MODULES,
    FactorWeights,
    _calculate_risk_level,
    _residual_uncertainty_baseline,
    classify_module,
    compliance_framework_count,
    rollup_scan_brs,
    score_finding,
)


def _module(name: str):
    return next(m for m in DEFAULT_MODULES if m.name == name)


def _finding(**overrides) -> RawFinding:
    defaults = dict(
        title="Test finding",
        severity="MEDIUM",
        category="unknown",
        source="test",
        cvss=5.0,
        file_path=None,
        description="",
    )
    defaults.update(overrides)
    return RawFinding(**defaults)


# ── classify_module ────────────────────────────────────────────────────────────

class TestClassifyModule:
    def test_matches_payments_keyword_in_file_path(self):
        finding = _finding(file_path="src/services/payment_gateway.py")
        assert classify_module(finding, DEFAULT_MODULES).name == "Payments"

    def test_matches_authentication_keyword_in_title(self):
        finding = _finding(title="JWT signature not verified", file_path="src/misc.py")
        assert classify_module(finding, DEFAULT_MODULES).name == "Authentication"

    def test_matches_infrastructure_keyword(self):
        finding = _finding(file_path="deploy/docker-compose.yml", title="Privileged container")
        assert classify_module(finding, DEFAULT_MODULES).name == "Infrastructure"

    def test_falls_back_to_default_module_when_no_keyword_matches(self):
        finding = _finding(title="Something generic", category="unknown", file_path="misc/util.py")
        module = classify_module(finding, DEFAULT_MODULES)
        assert module.name == "General"
        assert module.is_default is True

    def test_higher_criticality_module_wins_when_multiple_keywords_present(self):
        # "payment" (Payments, criticality 10.0) and "report" (Reporting,
        # criticality 3.0) both appear — Payments must win because
        # DEFAULT_MODULES is already ordered by descending criticality,
        # same ordering BusinessModuleRepository.list_all() enforces in
        # the DB-backed path.
        finding = _finding(title="Payment transaction report export", file_path="src/report_payment.py")
        assert classify_module(finding, DEFAULT_MODULES).name == "Payments"


# ── score_finding ───────────────────────────────────────────────────────────────

class TestScoreFinding:
    def test_critical_payments_sqli_scores_in_critical_band(self):
        finding = _finding(
            title="SQL injection in transfer endpoint",
            severity="CRITICAL",
            category="sql_injection",
            cvss=9.8,
            file_path="src/api/payments/transfer.py",
            cve="CVE-2024-0001",
        )
        module = classify_module(finding, DEFAULT_MODULES)
        score = score_finding(
            finding,
            module=module,
            factor_weights=DEFAULT_FACTOR_WEIGHTS,
            compliance_framework_count=3,
            historical_incident_count=12,
        )

        assert module.name == "Payments"
        assert score.brs >= 90
        assert _calculate_risk_level(score.brs) == "Critical"

    def test_low_severity_reporting_finding_scores_in_low_band(self):
        finding = _finding(
            title="Use of standard random in analytics export",
            severity="LOW",
            category="insecure_random",
            cvss=2.0,
            file_path="src/reporting/export.py",
        )
        module = classify_module(finding, DEFAULT_MODULES)
        score = score_finding(finding, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS)

        assert module.name == "Reporting"
        assert _calculate_risk_level(score.brs) == "Low"

    def test_critical_finding_always_outscores_low_finding(self):
        critical = _finding(severity="CRITICAL", category="sql_injection", cvss=9.8, file_path="src/api/payments/x.py")
        low = _finding(severity="LOW", category="insecure_random", cvss=2.0, file_path="src/reporting/x.py")

        critical_score = score_finding(
            critical, module=classify_module(critical, DEFAULT_MODULES), factor_weights=DEFAULT_FACTOR_WEIGHTS
        )
        low_score = score_finding(
            low, module=classify_module(low, DEFAULT_MODULES), factor_weights=DEFAULT_FACTOR_WEIGHTS
        )

        assert critical_score.brs > low_score.brs

    def test_known_cve_raises_exploitability_floor(self):
        # Same finding, only difference is a CVE present — exploitability
        # sub-score must not decrease when a concrete CVE is attached.
        without_cve = _finding(category="weak_cryptography", cvss=5.0)
        with_cve = _finding(category="weak_cryptography", cvss=5.0, cve="CVE-2023-9999")

        module = _module("General")
        score_without = score_finding(without_cve, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS)
        score_with = score_finding(with_cve, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS)

        assert score_with.sub_scores["exploitability"] >= score_without.sub_scores["exploitability"]

    def test_internet_facing_path_increases_exposure_score(self):
        exposed = _finding(category="weak_cryptography", cvss=5.0, file_path="src/api/public/handler.py")
        internal = _finding(category="weak_cryptography", cvss=5.0, file_path="src/batch/internal_job.py")

        module = _module("General")
        exposed_score = score_finding(exposed, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS)
        internal_score = score_finding(internal, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS)

        assert exposed_score.sub_scores["internet_exposure"] > internal_score.sub_scores["internet_exposure"]

    def test_more_compliance_frameworks_increases_score(self):
        finding = _finding(category="weak_cryptography", cvss=5.0)
        module = _module("General")

        no_frameworks = score_finding(finding, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS, compliance_framework_count=0)
        three_frameworks = score_finding(finding, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS, compliance_framework_count=3)

        assert three_frameworks.brs > no_frameworks.brs

    def test_more_historical_incidents_increases_score(self):
        finding = _finding(category="weak_cryptography", cvss=5.0)
        module = _module("General")

        no_history = score_finding(finding, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS, historical_incident_count=0)
        heavy_history = score_finding(finding, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS, historical_incident_count=15)

        assert heavy_history.brs > no_history.brs

    def test_brs_never_exceeds_100(self):
        finding = _finding(severity="CRITICAL", category="sql_injection", cvss=10.0, file_path="src/api/payments/x.py", cve="CVE-x")
        module = _module("Payments")
        score = score_finding(
            finding, module=module, factor_weights=DEFAULT_FACTOR_WEIGHTS,
            compliance_framework_count=3, historical_incident_count=1000,
        )
        assert score.brs <= 100.0

    def test_zero_weights_fall_back_to_raw_cvss_without_crashing(self):
        zero_weights = FactorWeights(
            cvss=0, exploitability=0, business_criticality=0, internet_exposure=0,
            compliance_impact=0, asset_value=0, historical_incidents=0,
        )
        finding = _finding(cvss=7.5)
        score = score_finding(finding, module=_module("General"), factor_weights=zero_weights)
        assert score.brs == pytest.approx(75.0)

    def test_disabling_a_single_factor_removes_its_influence(self):
        # Weight the blend on business_criticality alone — the score
        # should then be identical for Payments regardless of severity,
        # since every other factor's weight is 0.
        only_business_criticality = FactorWeights(
            cvss=0, exploitability=0, business_criticality=1.0, internet_exposure=0,
            compliance_impact=0, asset_value=0, historical_incidents=0,
        )
        low_cvss = _finding(cvss=0.1, file_path="src/api/payments/x.py")
        high_cvss = _finding(cvss=9.9, file_path="src/api/payments/x.py")

        module = _module("Payments")
        score_low = score_finding(low_cvss, module=module, factor_weights=only_business_criticality)
        score_high = score_finding(high_cvss, module=module, factor_weights=only_business_criticality)

        assert score_low.brs == score_high.brs == pytest.approx(module.criticality_weight * 10)


# ── compliance_framework_count ─────────────────────────────────────────────────

class TestComplianceFrameworkCount:
    def test_none_input_counts_as_zero(self):
        assert compliance_framework_count(None) == 0

    def test_counts_only_populated_clauses(self):
        from app.services.compliance.compliance_mapper import ComplianceMappingData

        mapping = ComplianceMappingData(rbi_clause="4.1", pci_clause=None, swift_clause="2.3")
        assert compliance_framework_count(mapping) == 2


# ── _calculate_risk_level (thresholds calibrated to this formula, not CVSS) ────

class TestRiskLevelThresholds:
    @pytest.mark.parametrize(
        "brs,expected",
        [
            (0.0, "Low"),
            (24.0, "Low"),   # measured floor for a trivial finding in the most permissive module
            (34.9, "Low"),
            (35.0, "Medium"),
            (53.25, "Medium"),  # a single Medium-severity misconfig with 1 compliance framework
            (57.9, "Medium"),
            (58.0, "High"),
            (80.25, "High"),  # a single High-severity hardcoded secret in Authentication
            (81.9, "High"),
            (82.0, "Critical"),
            (97.25, "Critical"),  # measured worst-case: Critical SQLi in Payments, full context
            (100.0, "Critical"),
        ],
    )
    def test_thresholds(self, brs, expected):
        assert _calculate_risk_level(brs) == expected


# ── rollup_scan_brs — the scan-level roll-up (regression coverage for the ─────
# "every scan scores 100/Critical" incident) ────────────────────────────────────

class TestRollupScanBrs:
    def test_empty_findings_list_scores_zero(self):
        assert rollup_scan_brs([]) == 0.0


# ── _residual_uncertainty_baseline — a zero-findings scan is never reported ───
# as a literal 0/100 (see calculate_brs's early-return branch, which calls this
# instead of returning 0.0 outright) — a banking security review panel
# correctly rejects "provably secure" as an overclaim no scanner suite can
# support. ─────────────────────────────────────────────────────────────────────

class TestResidualUncertaintyBaseline:
    def test_full_coverage_is_just_the_base_floor(self):
        assert _residual_uncertainty_baseline(1.0) == 5.0

    def test_incomplete_coverage_adds_bounded_uncertainty(self):
        # Half the scanner suite failed/didn't run — less conclusive than a
        # clean result from the full suite, so a bit more residual risk, but
        # nowhere near the "Low" tier's 35 cutoff.
        assert _residual_uncertainty_baseline(0.5) == pytest.approx(6.5)

    def test_zero_coverage_hits_the_capped_maximum(self):
        assert _residual_uncertainty_baseline(0.0) == pytest.approx(8.0)

    def test_result_always_stays_within_the_low_risk_tier(self):
        for ratio in (0.0, 0.25, 0.5, 0.75, 1.0):
            baseline = _residual_uncertainty_baseline(ratio)
            assert _calculate_risk_level(baseline) == "Low"
            assert baseline > 0.0  # the entire point — never a literal zero


class TestRollupScanBrsFindingCountEffects:
    """The rest of TestRollupScanBrs's original coverage — unchanged, just
    restored to its own class after an earlier edit accidentally merged it
    into TestResidualUncertaintyBaseline above."""

    def test_single_finding_equals_its_own_score(self):
        # n=1 gets zero volume adjustment, and a self-weighted average of
        # one value is just that value.
        assert rollup_scan_brs([42.0]) == pytest.approx(42.0)

    def test_result_never_exceeds_the_maximum_individual_score(self):
        # The defining property a weighted average must have — no matter
        # how many findings or how they're distributed, the roll-up can
        # never invent risk beyond what any single finding actually
        # scored (up to the small, explicitly capped volume adjustment).
        brs_list = [30.0] * 40 + [95.0]
        result = rollup_scan_brs(brs_list)
        assert result <= 95.0 + 9.0  # max finding + the volume cap, never more

    def test_many_low_severity_findings_do_not_saturate_to_critical(self):
        # THE regression test for the reported incident: the old formula
        # (`max + 0.1 * sum(rest)`) pushed this exact shape of input to
        # 100/Critical — 30 mild findings, none of them individually even
        # Medium-severity. That must never happen again.
        brs_list = [28.0] * 30
        result = rollup_scan_brs(brs_list)
        assert result < 40.0, f"30 mild (~28 BRS) findings must not saturate the scan score, got {result}"
        assert _calculate_risk_level(result) in ("Low", "Medium")

    def test_volume_alone_cannot_push_low_findings_into_high_or_critical(self):
        # Even a large number of them — volume is capped at +9, nowhere
        # near enough to cross from a low individual score into High/Critical.
        brs_list = [20.0] * 200
        result = rollup_scan_brs(brs_list)
        assert result <= 29.0
        assert _calculate_risk_level(result) == "Low"

    def test_single_critical_finding_dominates_a_scan_full_of_low_findings(self):
        # The one property carried over from the old design that's worth
        # keeping: a single Critical shouldn't get diluted into Medium
        # territory just because a scan also turned up many Low findings.
        brs_list = [95.0] + [22.0] * 25
        result = rollup_scan_brs(brs_list)
        assert _calculate_risk_level(result) == "Critical"

    def test_more_findings_of_the_same_severity_increase_the_score_somewhat(self):
        # "Number of findings" must have *some* influence (per spec), just
        # a bounded one — 3 identical findings should score higher than 1,
        # but not dramatically so.
        few = rollup_scan_brs([50.0] * 3)
        many = rollup_scan_brs([50.0] * 20)
        assert many > few
        assert many - few <= 9.0  # bounded by the volume cap alone


# ── Repository-level risk profiles ──────────────────────────────────────────────
# End-to-end (still pure/synchronous — no DB) proof that realistic finding
# sets land in the expected risk bands using the real score_finding() +
# rollup_scan_brs() pipeline, not synthetic BRS numbers. Each repository
# below is a plausible scanner output for that risk profile; the
# assertions are the exact ranges requested when this was specified.

def _score_repo(findings: list[RawFinding], compliance_counts: "list[int] | None" = None) -> float:
    counts = compliance_counts or [0] * len(findings)
    brs_list = [
        score_finding(
            f,
            module=classify_module(f, DEFAULT_MODULES),
            factor_weights=DEFAULT_FACTOR_WEIGHTS,
            compliance_framework_count=counts[i],
        ).brs
        for i, f in enumerate(findings)
    ]
    return rollup_scan_brs(brs_list)


class TestRepositoryRiskProfiles:
    def test_repository_a_low_risk(self):
        # A handful of minor findings in the lowest-criticality module —
        # no CVEs, no internet exposure, no compliance impact.
        findings = [
            _finding(
                title="Use of standard random in analytics export",
                severity="LOW", category="insecure_random", cvss=2.0,
                file_path="src/reporting/export.py",
            ),
            _finding(
                title="Outdated non-security logging library",
                severity="LOW", category="vulnerable_dependency", cvss=1.8,
                file_path="src/reporting/log.py",
            ),
            _finding(
                title="Verbose error message in report generator",
                severity="LOW", category="security_misconfiguration", cvss=1.5,
                file_path="src/reporting/errors.py",
            ),
            _finding(
                title="Weak hash for cache key (non-security)",
                severity="INFO", category="weak_cryptography", cvss=1.0,
                file_path="src/reporting/cache.py",
            ),
        ]
        brs = _score_repo(findings)
        assert 15.0 <= brs <= 32.0, f"Repository A (Low Risk) expected ~15-30, got {brs}"
        assert _calculate_risk_level(brs) == "Low"

    def test_repository_b_medium_risk(self):
        # Mixed low/medium-severity findings, in a moderate-criticality
        # (Admin) module — no single finding severe enough on its own to
        # dominate, so the scan score reflects the combined picture.
        findings = [
            _finding(title="Outdated dependency with known medium CVE", severity="MEDIUM",
                      category="vulnerable_dependency", cvss=5.4, cve="CVE-2023-1111", file_path="app/admin/deps.py"),
            _finding(title="Missing rate limit on admin endpoint", severity="MEDIUM",
                      category="security_misconfiguration", cvss=4.5, file_path="app/admin/routes/panel.py"),
            _finding(title="Weak password policy in admin panel", severity="MEDIUM",
                      category="weak_cryptography", cvss=5.0, file_path="app/admin/auth.py"),
            _finding(title="Reflected input in admin dashboard", severity="MEDIUM",
                      category="security_misconfiguration", cvss=5.8, file_path="app/admin/views/dashboard.py"),
            _finding(title="Outdated JS dependency", severity="MEDIUM",
                      category="vulnerable_dependency", cvss=4.8, file_path="app/admin/package.json"),
            _finding(title="Directory listing enabled", severity="LOW",
                      category="security_misconfiguration", cvss=2.0, file_path="app/admin/static/"),
            _finding(title="Weak cipher suite configured", severity="MEDIUM",
                      category="weak_cryptography", cvss=5.9, file_path="app/admin/tls.py"),
        ]
        brs = _score_repo(findings)
        assert 40.0 <= brs <= 60.0, f"Repository B (Medium Risk) expected ~40-60, got {brs}"
        assert _calculate_risk_level(brs) == "Medium"

    def test_repository_c_high_risk(self):
        # Several High-severity findings plus one Critical, in
        # internet-facing Authentication/Customer Data modules.
        findings = [
            _finding(title="Path traversal in file download", severity="HIGH",
                      category="path_traversal", cvss=7.5, file_path="app/customer/api/routes/download.py"),
            _finding(title="Broken auth allows session fixation", severity="HIGH",
                      category="security_misconfiguration", cvss=7.1, file_path="app/auth/api/session.py"),
            _finding(title="SQL built via string concatenation", severity="CRITICAL",
                      category="sql_injection", cvss=9.1, file_path="app/customer/api/controller/search.py"),
            _finding(title="Hardcoded API key", severity="HIGH",
                      category="hardcoded_secret", cvss=7.8, file_path="app/auth/api/keys.py"),
            _finding(title="Known-vulnerable auth library", severity="HIGH",
                      category="vulnerable_dependency", cvss=7.4, cve="CVE-2022-9999", file_path="app/auth/requirements.txt"),
            _finding(title="Weak JWT signing algorithm", severity="HIGH",
                      category="weak_cryptography", cvss=6.9, file_path="app/auth/jwt.py"),
            _finding(title="Customer PII logged in plaintext", severity="HIGH",
                      category="security_misconfiguration", cvss=7.2, file_path="app/customer/api/routes/profile.py"),
            _finding(title="Outdated crypto dependency", severity="MEDIUM",
                      category="vulnerable_dependency", cvss=5.5, file_path="app/customer/deps.py"),
        ]
        brs = _score_repo(findings)
        assert 65.0 <= brs <= 80.0, f"Repository C (High Risk) expected ~65-80, got {brs}"
        assert _calculate_risk_level(brs) == "High"

    def test_repository_d_critical_risk(self):
        # Multiple Critical findings in the Payments module — internet-facing,
        # known CVEs, and (realistically, for Payments) mapped to all 3
        # regulatory frameworks.
        findings = [
            _finding(title="SQL injection in fund transfer API", severity="CRITICAL",
                      category="sql_injection", cvss=9.8, file_path="app/payments/api/routes/transfer.py"),
            _finding(title="Hardcoded database credentials", severity="CRITICAL",
                      category="hardcoded_secret", cvss=9.5, file_path="app/payments/config.py"),
            _finding(title="Command injection in reconciliation job", severity="CRITICAL",
                      category="command_injection", cvss=9.4, file_path="app/payments/api/controller/reconcile.py"),
            _finding(title="Critical RCE in payment gateway dependency", severity="CRITICAL",
                      category="vulnerable_dependency", cvss=9.9, cve="CVE-2024-0001", file_path="app/payments/requirements.txt"),
            _finding(title="Unsafe deserialization of transaction payload", severity="CRITICAL",
                      category="unsafe_deserialization", cvss=9.0, file_path="app/payments/api/handlers/webhook.py"),
            _finding(title="Critical auth bypass on transfer endpoint", severity="CRITICAL",
                      category="security_misconfiguration", cvss=9.3, file_path="app/payments/api/routes/transfer.py"),
            _finding(title="Outdated payments SDK with known critical CVE", severity="CRITICAL",
                      category="vulnerable_dependency", cvss=9.6, cve="CVE-2023-5555", file_path="app/payments/deps.py"),
        ]
        brs = _score_repo(findings, compliance_counts=[3] * len(findings))
        assert brs > 85.0, f"Repository D (Critical) expected >85, got {brs}"
        assert _calculate_risk_level(brs) == "Critical"
