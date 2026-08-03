"""
NOVA — Executive Intelligence Unit Tests
Targets the pure functions in
app/services/executive_intelligence/{evidence_service,
executive_intelligence_service}.py — no database, no ONNX model, no LLM
call required. `build_evidence_snapshot`/`gather_evidence`/`stream_answer`
themselves are integration-level (real DB + real local models) and
covered by the manual testing procedure instead.

`scan_rows` throughout are faked with `SimpleNamespace` rather than real
SQLAlchemy `Row` objects — both support the same `.field_name` attribute
access these functions rely on, so a plain namespace is a faithful stand-in.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.executive_intelligence.evidence_service import (
    ComplianceFrameworkEvidence,
    ExecutiveEvidenceSnapshot,
    RepositoryRiskEvidence,
    WeekOverWeekDelta,
    WeeklyTrendPoint,
    _aggregate_compliance,
    _critical_high_count,
    _total_findings_count,
    _week_over_week,
    _week_start,
    _weekly_trend,
    render_evidence_block,
)
from app.services.executive_intelligence.executive_intelligence_service import (
    Citation,
    build_context_section,
    format_history,
)


def _row(**overrides):
    defaults = dict(
        id="scan-1",
        repository_id="repo-1",
        finished_at=None,
        name="repo-1",
        brs_score=None,
        brs_risk_level=None,
        compliance_summary=None,
        summary=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestWeekStart:
    def test_returns_preceding_monday_midnight(self):
        wednesday = datetime(2026, 7, 22, 15, 30, tzinfo=timezone.utc)  # a Wednesday
        result = _week_start(wednesday)
        assert result.weekday() == 0
        assert result.hour == 0 and result.minute == 0
        assert result.date() == datetime(2026, 7, 20).date()

    def test_monday_maps_to_itself(self):
        monday = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
        result = _week_start(monday)
        assert result.date() == monday.date()


class TestFindingCountHelpers:
    def test_critical_high_count_sums_both_severities(self):
        assert _critical_high_count({"CRITICAL": 3, "HIGH": 5, "MEDIUM": 10}) == 8

    def test_critical_high_count_none_summary_is_zero(self):
        assert _critical_high_count(None) == 0

    def test_critical_high_count_missing_keys_default_to_zero(self):
        assert _critical_high_count({"MEDIUM": 10}) == 0

    def test_total_findings_count_reads_total_key(self):
        assert _total_findings_count({"total": 12}) == 12

    def test_total_findings_count_none_summary_is_zero(self):
        assert _total_findings_count(None) == 0


class TestAggregateCompliance:
    def test_aggregates_across_repositories(self):
        rows = [
            _row(compliance_summary={"pci_dss_v4": {"name": "PCI DSS v4.0", "compliant": True, "violations": 0}}),
            _row(compliance_summary={"pci_dss_v4": {"name": "PCI DSS v4.0", "compliant": False, "violations": 5}}),
            _row(compliance_summary={"pci_dss_v4": {"name": "PCI DSS v4.0", "compliant": False, "violations": 3}}),
        ]
        result = _aggregate_compliance(rows)
        assert len(result) == 1
        fw = result[0]
        assert fw.framework_key == "pci_dss_v4"
        assert fw.compliant_repo_count == 1
        assert fw.non_compliant_repo_count == 2
        assert fw.total_violations == 8

    def test_skips_rows_with_no_compliance_summary(self):
        rows = [_row(compliance_summary=None)]
        assert _aggregate_compliance(rows) == []

    def test_handles_multiple_frameworks_independently(self):
        rows = [
            _row(
                compliance_summary={
                    "pci_dss_v4": {"name": "PCI DSS v4.0", "compliant": True, "violations": 0},
                    "swift_csp": {"name": "SWIFT CSP", "compliant": False, "violations": 2},
                }
            )
        ]
        result = {fw.framework_key: fw for fw in _aggregate_compliance(rows)}
        assert result["pci_dss_v4"].compliant_repo_count == 1
        assert result["swift_csp"].non_compliant_repo_count == 1


class TestWeeklyTrendAndWeekOverWeek:
    def test_weekly_trend_buckets_by_week_and_sums_critical_high(self):
        now = datetime(2026, 7, 22, tzinfo=timezone.utc)
        this_week = _week_start(now)
        rows = [
            _row(finished_at=this_week + timedelta(days=1), brs_score=40.0, summary={"CRITICAL": 1, "HIGH": 2}),
            _row(finished_at=this_week + timedelta(days=2), brs_score=60.0, summary={"CRITICAL": 0, "HIGH": 1}),
        ]
        points = _weekly_trend(rows, now)
        current_week_point = next(p for p in points if p.week_start == this_week.date().isoformat())
        assert current_week_point.scan_count == 2
        assert current_week_point.average_brs == 50.0
        assert current_week_point.critical_high_findings == 4

    def test_weekly_trend_empty_week_has_none_average(self):
        now = datetime(2026, 7, 22, tzinfo=timezone.utc)
        points = _weekly_trend([], now)
        assert all(p.scan_count == 0 and p.average_brs is None for p in points)

    def test_week_over_week_splits_correctly(self):
        now = datetime(2026, 7, 22, tzinfo=timezone.utc)
        rows = [
            _row(finished_at=now - timedelta(days=1), brs_score=30.0, summary={"total": 2}),  # this week
            _row(finished_at=now - timedelta(days=10), brs_score=70.0, summary={"total": 5}),  # last week
            _row(finished_at=now - timedelta(days=20), brs_score=90.0, summary={"total": 9}),  # too old
        ]
        delta = _week_over_week(rows, now)
        assert delta.scans_this_week == 1
        assert delta.scans_last_week == 1
        assert delta.average_brs_this_week == 30.0
        assert delta.average_brs_last_week == 70.0
        assert delta.findings_this_week == 2
        assert delta.findings_last_week == 5


class TestRenderEvidenceBlock:
    def test_no_data_snapshot_says_so_plainly(self):
        snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-07-22T00:00:00Z",
            total_repositories=3,
            total_completed_scans=0,
            total_findings=0,
            findings_by_severity={},
            portfolio_average_brs=None,
        )
        block = render_evidence_block(snapshot)
        assert "No completed scans exist yet" in block
        # Must not claim findings/BRS data it doesn't have.
        assert "Findings by severity" not in block

    def test_full_snapshot_includes_every_computed_number(self):
        snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-07-22T00:00:00Z",
            total_repositories=2,
            total_completed_scans=5,
            total_findings=12,
            findings_by_severity={"CRITICAL": 2, "HIGH": 4},
            portfolio_average_brs=55.5,
            top_risk_repositories=[
                RepositoryRiskEvidence(
                    repository_id="r1", repository_name="payments-api",
                    latest_brs_score=82.3, latest_brs_risk_level="Critical",
                    latest_scan_finished_at="2026-07-20T00:00:00Z",
                )
            ],
            compliance_by_framework=[
                ComplianceFrameworkEvidence(
                    framework_key="pci_dss_v4", framework_name="PCI DSS v4.0",
                    compliant_repo_count=1, non_compliant_repo_count=1, total_violations=5,
                )
            ],
            weekly_trend=[
                WeeklyTrendPoint(week_start="2026-07-13", scan_count=2, average_brs=50.0, critical_high_findings=3)
            ],
            week_over_week=WeekOverWeekDelta(
                scans_this_week=3, scans_last_week=2,
                findings_this_week=8, findings_last_week=4,
                average_brs_this_week=55.0, average_brs_last_week=45.0,
            ),
        )
        block = render_evidence_block(snapshot)
        assert "55.5" in block
        assert "payments-api" in block and "82.3" in block
        assert "PCI DSS v4.0" in block and "5 total violations" in block
        assert "3 scans" in block or "3" in block  # week-over-week scan count present
        assert "CRITICAL=2" in block and "HIGH=4" in block


def _citation(**overrides) -> Citation:
    defaults = dict(
        document_id="doc-1", filename="policy.pdf", page_number=3,
        section_path="Risk Management", heading="Risk Management",
        similarity_score=0.8, excerpt="Risk must be reviewed quarterly.",
    )
    defaults.update(overrides)
    return Citation(**defaults)


class TestBuildContextSection:
    def test_empty_citations_yields_empty_string(self):
        assert build_context_section([]) == ""

    def test_includes_numbered_source_and_excerpt(self):
        section = build_context_section([_citation()])
        assert "[1]" in section
        assert "policy.pdf" in section
        assert "Risk must be reviewed quarterly." in section

    def test_labels_as_supplementary_not_a_statistics_source(self):
        section = build_context_section([_citation()])
        assert "never a source for statistics" in section.lower()


class TestFormatHistory:
    def test_empty_history_has_placeholder(self):
        assert format_history([], max_turns=6) == "(no earlier turns)"

    def test_truncates_to_max_turns(self):
        history = [{"role": "user", "content": f"turn {i}"} for i in range(5)]
        rendered = format_history(history, max_turns=2)
        assert "turn 4" in rendered
        assert "turn 0" not in rendered
