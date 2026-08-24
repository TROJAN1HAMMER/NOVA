"""
NOVA — Executive Intelligence Unit Tests
Validates evidence snapshot generation, rendering, context building, history formatting,
structured fallback answer streaming, SSE packing, and PDF report generation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.executive_intelligence import _sse_pack
from app.schemas.executive_intelligence import (
    EvidenceSnapshotSchema,
    ExecutiveAskRequest,
    ExecutiveCitation,
    ExecutivePdfExportRequest,
)
from app.services.executive_intelligence.evidence_service import (
    ExecutiveEvidenceSnapshot,
    build_evidence_snapshot,
    render_evidence_block,
)
from app.services.executive_intelligence.executive_intelligence_service import (
    NO_DATA_MESSAGE,
    Citation,
    EvidenceBundle,
    _citation_header,
    build_context_section,
    format_history,
    stream_answer,
)
from app.services.executive_intelligence.pdf_export import (
    _inline_markdown,
    _metric_rows,
    render_pdf,
)


# ── 1. Evidence Snapshot & Rendering Tests ────────────────────────────────────


class TestExecutiveEvidenceSnapshot:
    def test_snapshot_creation_and_defaults(self):
        snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-08-24T12:00:00Z",
            total_repositories=5,
            total_completed_scans=42,
            total_findings=15,
            findings_by_severity={"indexed": 42},
            portfolio_average_brs=98.5,
        )
        assert snapshot.total_repositories == 5
        assert snapshot.total_completed_scans == 42
        assert snapshot.total_findings == 15
        assert snapshot.findings_by_severity == {"indexed": 42}
        assert snapshot.portfolio_average_brs == 98.5
        assert snapshot.top_risk_repositories == []
        assert snapshot.compliance_by_framework == []
        assert snapshot.weekly_trend == []
        assert snapshot.week_over_week is None
        assert snapshot.has_any_data is True

    def test_has_any_data_false_when_empty(self):
        empty_snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-08-24T12:00:00Z",
            total_repositories=0,
            total_completed_scans=0,
            total_findings=0,
            findings_by_severity={},
            portfolio_average_brs=None,
        )
        assert empty_snapshot.has_any_data is False

    def test_has_any_data_true_with_any_positive_metric(self):
        snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-08-24T12:00:00Z",
            total_repositories=1,
            total_completed_scans=0,
            total_findings=0,
            findings_by_severity={},
            portfolio_average_brs=None,
        )
        assert snapshot.has_any_data is True


class TestRenderEvidenceBlock:
    def test_render_evidence_block_formats_all_metrics(self):
        snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-08-24T12:00:00Z",
            total_repositories=10,
            total_completed_scans=120,
            total_findings=45,
            findings_by_severity={"indexed": 120},
            portfolio_average_brs=98.5,
        )
        block = render_evidence_block(snapshot)
        assert "Data as of: 2026-08-24T12:00:00Z" in block
        assert "Total knowledge documents: 10" in block
        assert "Total processed chunks: 120" in block
        assert "Total search analytics logs: 45" in block
        assert "Knowledge Base Status: Healthy & Fully Indexed." in block


class TestBuildEvidenceSnapshot:
    @pytest.mark.asyncio
    async def test_build_evidence_snapshot_empty_db_returns_none_average_and_empty_trends(self):
        mock_db = AsyncMock()

        # Counts: docs, chunks, logs, brs
        doc_res = MagicMock()
        doc_res.scalar_one.return_value = 0

        chunk_res = MagicMock()
        chunk_res.scalar_one.return_value = 0

        log_res = MagicMock()
        log_res.scalar_one.return_value = 0

        brs_res = MagicMock()
        brs_res.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [doc_res, chunk_res, log_res, brs_res]

        snapshot = await build_evidence_snapshot(mock_db)

        assert snapshot.total_repositories == 0
        assert snapshot.total_completed_scans == 0
        assert snapshot.total_findings == 0
        assert snapshot.findings_by_severity == {"indexed": 0}
        assert snapshot.portfolio_average_brs is None
        assert snapshot.weekly_trend == []
        assert snapshot.week_over_week is None
        assert snapshot.has_any_data is False

    @pytest.mark.asyncio
    async def test_build_evidence_snapshot_computes_real_brs_score(self):
        mock_db = AsyncMock()

        doc_res = MagicMock()
        doc_res.scalar_one.return_value = 8

        chunk_res = MagicMock()
        chunk_res.scalar_one.return_value = 64

        log_res = MagicMock()
        log_res.scalar_one.return_value = 30

        brs_res = MagicMock()
        brs_res.scalar_one_or_none.return_value = 92.4567

        # 4 weekly trend iterations: 2 queries each (log stats, scan BRS)
        weekly_responses = []
        for _ in range(4):
            log_stats = MagicMock()
            log_stats.one.return_value = (5, 1)
            scan_brs = MagicMock()
            scan_brs.scalar_one_or_none.return_value = 90.0
            weekly_responses.extend([log_stats, scan_brs])

        # Week over week: tw_log, lw_log, tw_brs, lw_brs
        tw_log = MagicMock()
        tw_log.one.return_value = (10, 2)
        lw_log = MagicMock()
        lw_log.one.return_value = (8, 1)

        tw_brs = MagicMock()
        tw_brs.scalar_one_or_none.return_value = 94.0
        lw_brs = MagicMock()
        lw_brs.scalar_one_or_none.return_value = 88.0

        mock_db.execute.side_effect = [
            doc_res,
            chunk_res,
            log_res,
            brs_res,
            *weekly_responses,
            tw_log,
            lw_log,
            tw_brs,
            lw_brs,
        ]

        snapshot = await build_evidence_snapshot(mock_db)

        assert snapshot.total_repositories == 8
        assert snapshot.total_completed_scans == 64
        assert snapshot.total_findings == 30
        assert snapshot.findings_by_severity == {"indexed": 64}
        assert snapshot.portfolio_average_brs == 92.46
        assert len(snapshot.weekly_trend) == 4
        assert snapshot.weekly_trend[0]["scan_count"] == 5
        assert snapshot.weekly_trend[0]["critical_high_findings"] == 1
        assert snapshot.weekly_trend[0]["average_brs"] == 90.0
        assert snapshot.week_over_week == {
            "scans_this_week": 10,
            "scans_last_week": 8,
            "findings_this_week": 2,
            "findings_last_week": 1,
            "average_brs_this_week": 94.0,
            "average_brs_last_week": 88.0,
        }
        assert snapshot.has_any_data is True

    @pytest.mark.asyncio
    async def test_build_evidence_snapshot_handles_null_scores_safely(self):
        mock_db = AsyncMock()

        doc_res = MagicMock()
        doc_res.scalar_one.return_value = 2

        chunk_res = MagicMock()
        chunk_res.scalar_one.return_value = 10

        log_res = MagicMock()
        log_res.scalar_one.return_value = 0

        brs_res = MagicMock()
        brs_res.scalar_one_or_none.return_value = None  # NULL BRS

        # Weekly iterations with NULLs
        weekly_responses = []
        for _ in range(4):
            log_stats = MagicMock()
            log_stats.one.return_value = (0, 0)
            scan_brs = MagicMock()
            scan_brs.scalar_one_or_none.return_value = None
            weekly_responses.extend([log_stats, scan_brs])

        tw_log = MagicMock()
        tw_log.one.return_value = (0, 0)
        lw_log = MagicMock()
        lw_log.one.return_value = (0, 0)

        tw_brs = MagicMock()
        tw_brs.scalar_one_or_none.return_value = None
        lw_brs = MagicMock()
        lw_brs.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [
            doc_res,
            chunk_res,
            log_res,
            brs_res,
            *weekly_responses,
            tw_log,
            lw_log,
            tw_brs,
            lw_brs,
        ]

        snapshot = await build_evidence_snapshot(mock_db)

        assert snapshot.total_repositories == 2
        assert snapshot.total_completed_scans == 10
        assert snapshot.portfolio_average_brs is None
        assert snapshot.has_any_data is True
        for point in snapshot.weekly_trend:
            assert point["average_brs"] is None
        assert snapshot.week_over_week["average_brs_this_week"] is None
        assert snapshot.week_over_week["average_brs_last_week"] is None

    @pytest.mark.asyncio
    async def test_weekly_trend_multi_week_chronology_and_counts(self):
        mock_db = AsyncMock()

        # Counts
        doc_res = MagicMock()
        doc_res.scalar_one.return_value = 5
        chunk_res = MagicMock()
        chunk_res.scalar_one.return_value = 20
        log_res = MagicMock()
        log_res.scalar_one.return_value = 42
        brs_res = MagicMock()
        brs_res.scalar_one_or_none.return_value = 91.5

        # 4 weeks distinct data:
        # Week 1 (oldest): 3 scans, 0 gaps, BRS 85.0
        # Week 2: 7 scans, 2 gaps, BRS 88.0
        # Week 3: 12 scans, 1 gap, BRS 92.5
        # Week 4 (newest): 20 scans, 4 gaps, BRS 95.0
        week_data = [
            ((3, 0), 85.0),
            ((7, 2), 88.0),
            ((12, 1), 92.5),
            ((20, 4), 95.0),
        ]
        weekly_mocks = []
        for (scans, gaps), brs_val in week_data:
            log_mock = MagicMock()
            log_mock.one.return_value = (scans, gaps)
            brs_mock = MagicMock()
            brs_mock.scalar_one_or_none.return_value = brs_val
            weekly_mocks.extend([log_mock, brs_mock])

        # Week-over-week mocks
        tw_log = MagicMock()
        tw_log.one.return_value = (20, 4)
        lw_log = MagicMock()
        lw_log.one.return_value = (12, 1)
        tw_brs = MagicMock()
        tw_brs.scalar_one_or_none.return_value = 95.0
        lw_brs = MagicMock()
        lw_brs.scalar_one_or_none.return_value = 92.5

        mock_db.execute.side_effect = [
            doc_res,
            chunk_res,
            log_res,
            brs_res,
            *weekly_mocks,
            tw_log,
            lw_log,
            tw_brs,
            lw_brs,
        ]

        snapshot = await build_evidence_snapshot(mock_db)

        # Verify exact 4 trend points
        assert len(snapshot.weekly_trend) == 4

        # Chronological ordering: week_start of week 0 < week 1 < week 2 < week 3
        week_dates = [point["week_start"] for point in snapshot.weekly_trend]
        assert week_dates == sorted(week_dates)

        # Verify point 0 (Week 1)
        assert snapshot.weekly_trend[0]["scan_count"] == 3
        assert snapshot.weekly_trend[0]["critical_high_findings"] == 0
        assert snapshot.weekly_trend[0]["average_brs"] == 85.0

        # Verify point 1 (Week 2)
        assert snapshot.weekly_trend[1]["scan_count"] == 7
        assert snapshot.weekly_trend[1]["critical_high_findings"] == 2
        assert snapshot.weekly_trend[1]["average_brs"] == 88.0

        # Verify point 2 (Week 3)
        assert snapshot.weekly_trend[2]["scan_count"] == 12
        assert snapshot.weekly_trend[2]["critical_high_findings"] == 1
        assert snapshot.weekly_trend[2]["average_brs"] == 92.5

        # Verify point 3 (Week 4)
        assert snapshot.weekly_trend[3]["scan_count"] == 20
        assert snapshot.weekly_trend[3]["critical_high_findings"] == 4
        assert snapshot.weekly_trend[3]["average_brs"] == 95.0

    @pytest.mark.asyncio
    async def test_week_over_week_comparison_deltas(self):
        mock_db = AsyncMock()

        doc_res = MagicMock()
        doc_res.scalar_one.return_value = 10
        chunk_res = MagicMock()
        chunk_res.scalar_one.return_value = 50
        log_res = MagicMock()
        log_res.scalar_one.return_value = 100
        brs_res = MagicMock()
        brs_res.scalar_one_or_none.return_value = 94.0

        weekly_mocks = []
        for _ in range(4):
            log_mock = MagicMock()
            log_mock.one.return_value = (10, 1)
            brs_mock = MagicMock()
            brs_mock.scalar_one_or_none.return_value = 90.0
            weekly_mocks.extend([log_mock, brs_mock])

        # This week vs Last week metrics
        tw_log = MagicMock()
        tw_log.one.return_value = (25, 5)  # 25 scans, 5 gaps
        lw_log = MagicMock()
        lw_log.one.return_value = (15, 2)  # 15 scans, 2 gaps
        tw_brs = MagicMock()
        tw_brs.scalar_one_or_none.return_value = 96.2
        lw_brs = MagicMock()
        lw_brs.scalar_one_or_none.return_value = 91.8

        mock_db.execute.side_effect = [
            doc_res,
            chunk_res,
            log_res,
            brs_res,
            *weekly_mocks,
            tw_log,
            lw_log,
            tw_brs,
            lw_brs,
        ]

        snapshot = await build_evidence_snapshot(mock_db)

        assert snapshot.week_over_week is not None
        assert snapshot.week_over_week["scans_this_week"] == 25
        assert snapshot.week_over_week["scans_last_week"] == 15
        assert snapshot.week_over_week["findings_this_week"] == 5
        assert snapshot.week_over_week["findings_last_week"] == 2
        assert snapshot.week_over_week["average_brs_this_week"] == 96.2
        assert snapshot.week_over_week["average_brs_last_week"] == 91.8

    @pytest.mark.asyncio
    async def test_time_window_boundary_queries(self):
        mock_db = AsyncMock()

        doc_res = MagicMock()
        doc_res.scalar_one.return_value = 1
        chunk_res = MagicMock()
        chunk_res.scalar_one.return_value = 1
        log_res = MagicMock()
        log_res.scalar_one.return_value = 1
        brs_res = MagicMock()
        brs_res.scalar_one_or_none.return_value = 90.0

        weekly_mocks = []
        for _ in range(4):
            log_mock = MagicMock()
            log_mock.one.return_value = (1, 0)
            brs_mock = MagicMock()
            brs_mock.scalar_one_or_none.return_value = 90.0
            weekly_mocks.extend([log_mock, brs_mock])

        tw_log = MagicMock()
        tw_log.one.return_value = (1, 0)
        lw_log = MagicMock()
        lw_log.one.return_value = (0, 0)
        tw_brs = MagicMock()
        tw_brs.scalar_one_or_none.return_value = 90.0
        lw_brs = MagicMock()
        lw_brs.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [
            doc_res,
            chunk_res,
            log_res,
            brs_res,
            *weekly_mocks,
            tw_log,
            lw_log,
            tw_brs,
            lw_brs,
        ]

        snapshot = await build_evidence_snapshot(mock_db)
        assert snapshot.has_any_data is True
        # Total DB execute calls: 4 (counts & BRS) + 8 (4 weekly buckets x 2) + 4 (WoW) = 16
        assert mock_db.execute.call_count == 16




# ── 2. Citations & Context Formatting Tests ───────────────────────────────────


def _citation(**overrides) -> Citation:
    defaults = dict(
        document_id="doc-123",
        filename="security_policy.pdf",
        page_number=4,
        section_path="Access Control > Authentication",
        heading="MFA Requirements",
        similarity_score=0.88,
        excerpt="Multi-factor authentication is mandatory for all administrative access.",
    )
    defaults.update(overrides)
    return Citation(**defaults)


class TestCitationAndContextSection:
    def test_citation_creation(self):
        c = _citation()
        assert c.document_id == "doc-123"
        assert c.filename == "security_policy.pdf"
        assert c.page_number == 4
        assert c.section_path == "Access Control > Authentication"
        assert c.similarity_score == 0.88

    def test_citation_header_with_full_metadata(self):
        c = _citation()
        header = _citation_header(c)
        assert "Source: security_policy.pdf" in header
        assert "Section: Access Control > Authentication" in header
        assert "Page: 4" in header

    def test_citation_header_heading_fallback(self):
        c = _citation(section_path=None, heading="Encryption at Rest")
        header = _citation_header(c)
        assert "Source: security_policy.pdf" in header
        assert "Section: Encryption at Rest" in header

    def test_citation_header_no_page(self):
        c = _citation(page_number=None)
        header = _citation_header(c)
        assert "Page:" not in header

    def test_build_context_section_empty(self):
        assert build_context_section([]) == ""

    def test_build_context_section_with_citations(self):
        c1 = _citation(filename="a.pdf", excerpt="Excerpt A.")
        c2 = _citation(filename="b.pdf", excerpt="Excerpt B.")
        block = build_context_section([c1, c2])

        assert "[1]" in block
        assert "Source: a.pdf" in block
        assert "Excerpt A." in block
        assert "[2]" in block
        assert "Source: b.pdf" in block
        assert "Excerpt B." in block
        assert "never a source for statistics" in block.lower()


# ── 3. Evidence Bundle & History Formatting Tests ─────────────────────────────


class TestEvidenceBundle:
    def test_has_any_grounding_true_with_snapshot_data(self):
        snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-08-24T12:00:00Z",
            total_repositories=3,
            total_completed_scans=10,
            total_findings=2,
            findings_by_severity={"indexed": 10},
            portfolio_average_brs=98.5,
        )
        bundle = EvidenceBundle(snapshot=snapshot, evidence_block="evidence", citations=[])
        assert bundle.has_any_grounding is True

    def test_has_any_grounding_true_with_citations(self):
        empty_snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-08-24T12:00:00Z",
            total_repositories=0,
            total_completed_scans=0,
            total_findings=0,
            findings_by_severity={},
            portfolio_average_brs=None,
        )
        bundle = EvidenceBundle(snapshot=empty_snapshot, evidence_block="", citations=[_citation()])
        assert bundle.has_any_grounding is True

    def test_has_any_grounding_false_when_empty(self):
        empty_snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-08-24T12:00:00Z",
            total_repositories=0,
            total_completed_scans=0,
            total_findings=0,
            findings_by_severity={},
            portfolio_average_brs=None,
        )
        bundle = EvidenceBundle(snapshot=empty_snapshot, evidence_block="", citations=[])
        assert bundle.has_any_grounding is False


class TestFormatHistory:
    def test_empty_history_returns_placeholder(self):
        assert format_history([], max_turns=6) == "(no earlier turns)"

    def test_renders_capitalized_roles_and_content(self):
        history = [
            {"role": "user", "content": "What is our current risk profile?"},
            {"role": "assistant", "content": "Portfolio average BRS is 98.5."},
        ]
        formatted = format_history(history, max_turns=4)
        assert "User: What is our current risk profile?" in formatted
        assert "Assistant: Portfolio average BRS is 98.5." in formatted

    def test_truncates_to_max_turns(self):
        history = [{"role": "user", "content": f"query {i}"} for i in range(10)]
        formatted = format_history(history, max_turns=3)
        assert "query 9" in formatted
        assert "query 8" in formatted
        assert "query 7" in formatted
        assert "query 6" not in formatted


# ── 4. Structured Fallback Answer Streaming Tests ─────────────────────────────


class TestStreamAnswerFallback:
    def test_stream_answer_structured_fallback_when_gateway_unavailable(self):
        snapshot = ExecutiveEvidenceSnapshot(
            generated_at="2026-08-24T12:00:00Z",
            total_repositories=4,
            total_completed_scans=32,
            total_findings=12,
            findings_by_severity={"CRITICAL": 1, "HIGH": 3, "MEDIUM": 5, "LOW": 3},
            portfolio_average_brs=92.5,
        )
        citation = _citation(filename="policy.pdf", excerpt="Passphrase must be 16 chars.")
        bundle = EvidenceBundle(
            snapshot=snapshot,
            evidence_block=render_evidence_block(snapshot),
            citations=[citation],
        )

        with patch(
            "app.services.executive_intelligence.executive_intelligence_service.get_gateway"
        ) as mock_get_gw:
            mock_gw = MagicMock()
            mock_gw.stream.side_effect = RuntimeError("No LLM provider available")
            mock_get_gw.return_value = mock_gw

            generator = stream_answer(
                bundle,
                question="What is our compliance status?",
                history=[],
            )
            output = "".join(list(generator))

            assert "## 📊 Executive Security Intelligence Report" in output
            assert '**User Query**: "What is our compliance status?"' in output
            assert "Portfolio Average BRS Score" in output
            assert "92.50" in output
            assert "Total Monitored Repositories" in output
            assert "4" in output
            assert "Total Completed Scans" in output
            assert "32" in output
            assert "Total Identified Findings" in output
            assert "12" in output
            assert "policy.pdf" in output
            assert "Passphrase must be 16 chars." in output


# ── 5. SSE Event Packing Tests ────────────────────────────────────────────────


class TestSSEPack:
    def test_sse_pack_plain_data(self):
        packed = _sse_pack("hello world")
        assert packed == "data: hello world\n\n"

    def test_sse_pack_with_event_name(self):
        packed = _sse_pack('{"status": "ok"}', event="evidence")
        assert packed == 'event: evidence\ndata: {"status": "ok"}\n\n'

    def test_sse_pack_multiline_data(self):
        packed = _sse_pack("line1\nline2\nline3", event="token")
        expected = "event: token\ndata: line1\ndata: line2\ndata: line3\n\n"
        assert packed == expected


# ── 6. PDF Export Rendering Tests ─────────────────────────────────────────────


class TestPdfExport:
    def test_inline_markdown(self):
        rendered = _inline_markdown("**Critical** issue in `main.py` & <config>")
        assert "<b>Critical</b>" in rendered
        assert '<font face="Courier">main.py</font>' in rendered
        assert "&amp;" in rendered
        assert "&lt;config&gt;" in rendered

    def test_metric_rows(self):
        evidence_dict = {
            "total_repositories": 3,
            "total_completed_scans": 25,
            "total_findings": 7,
            "portfolio_average_brs": 94.0,
            "findings_by_severity": {"CRITICAL": 1, "HIGH": 2},
        }
        rows = _metric_rows(evidence_dict)
        labels = [r[0] for r in rows]
        assert "Total repositories" in labels
        assert "Total completed scans" in labels
        assert "Total findings" in labels
        assert "Portfolio average BRS" in labels
        assert "Findings by severity" in labels

    def test_render_pdf_returns_valid_pdf_bytes(self):
        evidence_dict = {
            "total_repositories": 2,
            "total_completed_scans": 10,
            "total_findings": 4,
            "portfolio_average_brs": 95.0,
            "findings_by_severity": {"HIGH": 1, "MEDIUM": 3},
            "compliance_by_framework": [],
            "top_risk_repositories": [],
        }
        citations_dict = [
            {
                "filename": "security_policy.pdf",
                "section_path": "Access Control",
                "page_number": 2,
                "excerpt": "Access must be reviewed semi-annually.",
            }
        ]

        pdf_bytes = render_pdf(
            question="What is our security posture?",
            answer="**Executive Summary**: Systems are currently operating within acceptable risk limits.",
            evidence=evidence_dict,
            citations=citations_dict,
            confidence=0.92,
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")
