"""
NOVA — Report Generation Engine
Produces PDF, SARIF, and CycloneDX SBOM export artifacts.

A. PDF Report (ReportLab)
   - Executive Summary
   - Banking Risk Score visualization
   - Findings table
   - Compliance mappings
   - AI Recommendations

B. SARIF Export (OASIS SARIF 2.1.0)
   - Valid SARIF JSON for IDE integration and CI/CD pipelines

C. CycloneDX SBOM Export
   - Re-export the stored SBOM

Input:  Scan data + findings from DB
Output: PDF path, SARIF path, SBOM path
"""

import csv
import io
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Callable, Optional, Union, Dict
from xml.sax.saxutils import escape as _xml_escape
import structlog

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import KeepTogether
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend

logger = structlog.get_logger(__name__)


# ── Color Palette ─────────────────────────────────────────────────────────────

NOVA_DARK = colors.HexColor("#0F172A")
NOVA_BLUE = colors.HexColor("#3B82F6")
NOVA_TEAL = colors.HexColor("#14B8A6")
NOVA_LIGHT = colors.HexColor("#F8FAFC")
NOVA_MUTED = colors.HexColor("#64748B")

SEVERITY_HEX = {
    "CRITICAL": "#DC2626",
    "HIGH": "#EA580C",
    "MEDIUM": "#D97706",
    "LOW": "#16A34A",
    "INFO": "#2563EB",
}

SEVERITY_COLORS = {sev: colors.HexColor(hexval) for sev, hexval in SEVERITY_HEX.items()}

RISK_COLORS = {
    "Critical": colors.HexColor("#DC2626"),
    "High": colors.HexColor("#EA580C"),
    "Medium": colors.HexColor("#D97706"),
    "Low": colors.HexColor("#16A34A"),
}

SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def _esc(value) -> str:
    """
    Escape dynamic scanner/AI-provided text before it is interpolated into an
    f-string that gets passed to a ReportLab ``Paragraph``. ``Paragraph`` parses
    a mini-XML markup language, so raw content containing literal ``<``, ``>``,
    or unescaped ``&`` (plausible in descriptions, code snippets, file paths,
    etc.) can raise at ``doc.build()`` or silently corrupt the tag stack.
    Do NOT use this on markup this file itself constructs (e.g. ``<b>`` wrappers)
    — only on the dynamic data being inserted into it.
    """
    if value is None:
        return ""
    return _xml_escape(str(value))


# ── Charts (reportlab.graphics — no extra dependency beyond reportlab itself) ──
# `reportlab.graphics` `Drawing`/`Legend` objects do not auto-size to their own content — if a
# label renders wider than the box declared here, Platypus only ever reserves the *declared*
# width/height when flowing what comes next, so an under-sized box is a real (if currently
# unobserved, since today's label text is short/fixed-vocabulary) overlap vector. The pie
# chart's legend is the one part of either chart whose text length depends on runtime data
# (a framework's non-compliant count), so its box width is computed from the actual rendered
# text rather than a fixed guess. Consistent spacing before/after both charts, wherever used.
CHART_SPACING = 0.4 * cm


def _severity_bar_chart(summary: dict) -> Drawing:
    """Findings-by-severity bar chart, one bar per severity, individually colored."""
    values = [summary.get(sev, 0) for sev in SEVERITY_ORDER]

    drawing = Drawing(440, 170)
    chart = VerticalBarChart()
    chart.x = 35
    chart.y = 25
    chart.width = 380
    chart.height = 125
    chart.data = [values]
    chart.categoryAxis.categoryNames = SEVERITY_ORDER
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.fontName = "Helvetica-Bold"
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 8
    chart.barLabels.fontSize = 8
    chart.barLabelFormat = "%d"
    chart.barLabels.nudge = 8
    chart.bars.strokeColor = colors.white
    chart.bars.strokeWidth = 0.5
    for i, sev in enumerate(SEVERITY_ORDER):
        chart.bars[(0, i)].fillColor = SEVERITY_COLORS.get(sev, NOVA_MUTED)
    drawing.add(chart)
    return drawing


def _compliance_pie_chart(compliance_summary: dict) -> Optional[Drawing]:
    """Compliant vs. non-compliant framework split, as a simple two-slice pie."""
    if not compliance_summary:
        return None

    compliant = sum(1 for d in compliance_summary.values() if d.get("compliant"))
    non_compliant = len(compliance_summary) - compliant

    pie = Pie()
    pie.x = 60
    pie.y = 15
    pie.width = 120
    pie.height = 120
    pie.strokeColor = colors.white
    pie.strokeWidth = 1

    if non_compliant:
        pie.data = [compliant, non_compliant]
        slice_labels = ["Compliant", "Non-Compliant"]
        pie.slices[0].fillColor = colors.HexColor("#16A34A")
        pie.slices[1].fillColor = colors.HexColor("#DC2626")
    else:
        pie.data = [compliant or 1]
        slice_labels = ["Compliant"]
        pie.slices[0].fillColor = colors.HexColor("#16A34A")

    legend_x = 210
    legend_font = "Helvetica"
    legend_font_size = 8
    legend_texts = [f"{label} ({pie.data[i]})" for i, label in enumerate(slice_labels)]

    legend = Legend()
    legend.x = legend_x
    legend.y = 90
    legend.dx = 8
    legend.dy = 8
    legend.fontName = legend_font
    legend.fontSize = legend_font_size
    legend.colorNamePairs = [
        (pie.slices[i].fillColor, text) for i, text in enumerate(legend_texts)
    ]

    # The framework count in each label is the only runtime-variable part of either chart's
    # text — a two-digit-or-more violation count on "Non-Compliant (NN)" is exactly the kind of
    # content-dependent width a fixed box guess can't account for. Measure the actual widest
    # label and only ever grow the drawing to fit it, never shrink below the original 320pt.
    widest_label = max((stringWidth(t, legend_font, legend_font_size) for t in legend_texts), default=0)
    drawing_width = max(320, int(legend_x + legend.dx + widest_label + 20))
    drawing = Drawing(drawing_width, 160)

    drawing.add(pie)
    drawing.add(legend)
    return drawing


# ── Repeating header/footer (page numbers, scan identity) ─────────────────────
# Neither PDF used to have any per-page chrome at all — a printed/detached page had no
# identifying information, and there was no "Page X of Y" anywhere. `SimpleDocTemplate` has no
# built-in way to know the *total* page count while it's still drawing page N (it doesn't know
# there'll be a page N+1 yet), so this uses the standard ReportLab two-pass recipe: buffer every
# page's drawing state via an overridden `showPage()` instead of finalizing it immediately, then
# in `save()` — once every page has been drawn once and the true total is finally known — replay
# each buffered page, stamp the footer, and only then hand it to the real `showPage()`/`save()`.
class NumberedCanvas(Canvas):
    def __init__(self, *args, scan_id: str = "", repo_name: str = "", generated_at: Optional[datetime] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []
        self._footer_scan_id = scan_id
        self._footer_repo_name = repo_name
        self._footer_generated_at = generated_at or datetime.now(timezone.utc)

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total_pages)
            Canvas.showPage(self)
        Canvas.save(self)

    def _draw_footer(self, total_pages: int):
        width, _ = self._pagesize
        footer_y = 1.1 * cm
        rule_y = footer_y + 0.32 * cm

        self.saveState()
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(2 * cm, rule_y, width - 2 * cm, rule_y)

        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(NOVA_DARK)
        self.drawString(2 * cm, footer_y, "NOVA")

        self.setFont("Helvetica", 7)
        self.setFillColor(NOVA_MUTED)
        timestamp = self._footer_generated_at.strftime("%Y-%m-%d %H:%M UTC")
        self.drawCentredString(
            width / 2, footer_y,
            f"Generated {timestamp}  |  Scan ID: {self._footer_scan_id}",
        )
        self.drawRightString(width - 2 * cm, footer_y, f"Page {self._pageNumber} of {total_pages}")
        self.restoreState()


# ── PDF Generation ────────────────────────────────────────────────────────────

class NOVAPDFReport:
    """Builds an executive-grade PDF security audit report for financial systems."""

    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        self.styles.add(ParagraphStyle(
            "NOVATitle",
            parent=self.styles["Title"],
            fontSize=28,
            # The parent "Title" style's own leading (22) is inherited unless overridden —
            # too tight for a 28pt line (same class of bug fixed on the cover page's inline
            # styles: leading must scale with fontSize, not just be inherited from a style
            # that was sized for a smaller font).
            leading=34,
            textColor=NOVA_DARK,
            spaceAfter=8,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            "NOVAH1",
            parent=self.styles["Heading1"],
            fontSize=16,
            textColor=NOVA_DARK,
            spaceAfter=10,
            spaceBefore=16,
            fontName="Helvetica-Bold",
            keepWithNext=True,
        ))
        self.styles.add(ParagraphStyle(
            "NOVAH2",
            parent=self.styles["Heading2"],
            fontSize=12,
            textColor=NOVA_BLUE,
            spaceAfter=8,
            spaceBefore=12,
            fontName="Helvetica-Bold",
            keepWithNext=True,
        ))
        self.styles.add(ParagraphStyle(
            "NOVABody",
            parent=self.styles["Normal"],
            fontSize=9.5,
            textColor=NOVA_DARK,
            spaceAfter=6,
            leading=14,
        ))
        self.styles.add(ParagraphStyle(
            "NOVABodyBold",
            parent=self.styles["Normal"],
            fontSize=9.5,
            textColor=NOVA_DARK,
            fontName="Helvetica-Bold",
            spaceAfter=6,
            leading=14,
        ))
        self.styles.add(ParagraphStyle(
            "NOVASmall",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=NOVA_MUTED,
            spaceAfter=4,
            leading=11,
        ))
        self.styles.add(ParagraphStyle(
            "NOVACell",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=NOVA_DARK,
            leading=9.5,
            spaceAfter=0,
        ))
        self.styles.add(ParagraphStyle(
            "NOVACellTiny",
            parent=self.styles["Normal"],
            fontSize=7.5,
            textColor=NOVA_DARK,
            leading=9,
            spaceAfter=0,
        ))
        self.styles.add(ParagraphStyle(
            "NOVACellCenter",
            parent=self.styles["Normal"],
            fontSize=8.5,
            textColor=NOVA_DARK,
            leading=10,
            alignment=TA_CENTER,
            spaceAfter=0,
        ))
        self.styles.add(ParagraphStyle(
            "NOVACode",
            parent=self.styles["Normal"],
            fontSize=8,
            fontName="Courier",
            textColor=NOVA_DARK,
            backColor=colors.HexColor("#F8FAFC"),
            borderPadding=4,
            spaceAfter=4,
        ))

    def _severity_badge(self, severity: str) -> Paragraph:
        color = SEVERITY_COLORS.get(severity.upper(), NOVA_MUTED)
        style = ParagraphStyle(
            "badge",
            fontSize=8,
            textColor=colors.white,
            backColor=color,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
            borderPadding=3,
        )
        return Paragraph(severity.upper(), style)

    def generate(
        self,
        scan_id: str,
        repo_name: str,
        brs_score: float,
        brs_risk_level: str,
        attack_surface_exposure_score: float,
        attack_surface_exposure_level: str,
        findings: list[dict],
        compliance_summary: dict,
        summary: dict,
        generated_at: datetime,
    ) -> Path:
        """Generate the complete PDF report."""

        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=f"NOVA Security Report — {repo_name}",
            author="NOVA Platform",
            subject="Banking Application Security Audit Report",
        )

        story = []

        # ── 1. Cover Page ──
        story.extend(self._build_cover(scan_id, repo_name, brs_score, brs_risk_level, generated_at))
        story.append(PageBreak())

        # ── 2. Executive Summary ──
        story.extend(self._build_executive_summary(
            repo_name, brs_score, brs_risk_level,
            attack_surface_exposure_score, attack_surface_exposure_level, summary, compliance_summary
        ))
        story.append(PageBreak())

        # ── 3. Threat Posture Overview ──
        story.extend(self._build_threat_posture_overview(
            summary, brs_score, brs_risk_level, attack_surface_exposure_score, attack_surface_exposure_level
        ))
        story.append(PageBreak())

        # ── 4. Regulatory Impact Analysis ──
        story.extend(self._build_compliance_section(compliance_summary, findings))
        story.append(PageBreak())

        # ── 5. Detailed Findings Section ──
        story.extend(self._build_detailed_findings_section(findings))
        story.append(PageBreak())

        # ── 6. AI Security Analyst Commentary ──
        story.extend(self._build_ai_analyst_commentary(findings))
        story.append(PageBreak())

        # ── 7. Executive Action Plan ──
        story.extend(self._build_action_plan(findings))
        story.append(PageBreak())

        # ── 8. Appendix ──
        story.extend(self._build_appendix(scan_id, repo_name, compliance_summary, generated_at))

        doc.build(story, canvasmaker=partial(
            NumberedCanvas, scan_id=scan_id, repo_name=repo_name, generated_at=generated_at,
        ))
        logger.info("[REPORT] report_generator.pdf.generated", path=str(self.output_path))
        return self.output_path

    def _build_cover(self, scan_id, repo_name, brs_score, brs_risk_level, generated_at):
        elements = []
        elements.append(Spacer(1, 1.5 * cm))

        # Logo Header. NOTE: every `ParagraphStyle(...)` below sets an explicit `leading`
        # (~1.25-1.3x its fontSize) — ReportLab's `ParagraphStyle` defaults `leading` to a
        # hardcoded 12 when no `parent=` is given, *regardless of fontSize*. Left unset, a
        # 32pt/20pt/13pt line only reserves a 12pt-tall box for the next flowable to start
        # from, so the following paragraph's text visually renders on top of this one's
        # descender — confirmed by rendering this exact page before this fix.
        elements.append(Paragraph(
            "NOVA",
            ParagraphStyle("logo", fontSize=32, leading=40, fontName="Helvetica-Bold",
                           textColor=NOVA_DARK, alignment=TA_CENTER)
        ))
        elements.append(Paragraph(
            "BANKING SECURITY COMMAND CENTER",
            ParagraphStyle("tagline", fontSize=10, leading=13, fontName="Helvetica-Bold",
                           textColor=NOVA_MUTED, alignment=TA_CENTER, spaceAfter=20)
        ))

        elements.append(HRFlowable(width="100%", thickness=1.5, color=NOVA_BLUE, spaceAfter=15))

        elements.append(Paragraph(
            "CONFIDENTIAL SECURITY AUDIT DOSSIER",
            ParagraphStyle("cover_header", fontSize=12, leading=15, fontName="Helvetica-Bold",
                           textColor=NOVA_BLUE, alignment=TA_CENTER, spaceAfter=10)
        ))

        elements.append(Paragraph(
            f"Vulnerability & Risk Assessment Report",
            ParagraphStyle("report_title", fontSize=20, leading=25, fontName="Helvetica-Bold",
                           textColor=NOVA_DARK, alignment=TA_CENTER, spaceAfter=10)
        ))

        elements.append(Paragraph(
            f"Repository Instance: <b>{_esc(repo_name)}</b>",
            ParagraphStyle("repo", fontSize=13, leading=17, textColor=NOVA_DARK, alignment=TA_CENTER, spaceAfter=40)
        ))

        # Overall Risk & BRS Matrix Block
        overall_rating = "CRITICAL POSTURE" if brs_score >= 30 else "ELEVATED RISK" if brs_score >= 20 else "STABLE POSTURE"
        rating_color = RISK_COLORS.get(brs_risk_level, NOVA_MUTED)

        brs_data = [
            ["BANKING RISK SCORE (BRS)", "OVERALL RATING"],
            [f"{brs_score:.1f} / 100", f"{overall_rating}"],
        ]
        brs_table = Table(brs_data, colWidths=[8.5 * cm, 8.5 * cm])
        brs_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NOVA_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9.5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 1), (-1, 1), 18),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 1), (0, 1), NOVA_BLUE),
            ("TEXTCOLOR", (1, 1), (1, 1), rating_color),
            ("BACKGROUND", (0, 1), (-1, 1), NOVA_LIGHT),
            ("BOX", (0, 0), (-1, -1), 1, NOVA_DARK),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        elements.append(brs_table)

        elements.append(Spacer(1, 2.5 * cm))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey, spaceAfter=15))

        # Metadata
        meta_data = [
            ["Scan identifier:", str(scan_id)],
            ["Generated Date:", generated_at.strftime("%Y-%m-%d %H:%M UTC")],
            ["Compliance Basis:", "RBI IT Framework 2021 | PCI DSS v4.0 | SWIFT CSP"],
            ["Target Environment:", "Production Banking Node Assessment"],
        ]
        meta_table = Table(meta_data, colWidths=[4.5 * cm, 12.5 * cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), NOVA_MUTED),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(meta_table)

        return elements

    def _build_executive_summary(
        self, repo_name, brs_score, brs_risk_level,
        attack_surface_exposure_score, attack_surface_exposure_level, summary, compliance_summary
    ):
        elements = []
        elements.append(Paragraph("2. Executive Summary", self.styles["NOVAH1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=10))

        # Core posture summary — driven by the engine's own risk_level string
        # (app/services/risk/brs_engine.py::_calculate_risk_level), not a
        # second, independently-thresholded check on the raw score here.
        # Two copies of the same cutoffs drift apart over time; one copy
        # can't.
        posture_description = {
            "Critical": "CRITICAL EXPOSURE DETECTED. Immediate patch orchestration required.",
            "High": "ELEVATED THREAT LANDSCAPE. Remediation should be scheduled in the next active sprint.",
            "Medium": "MODERATE RISK POSTURE. Remediation should be prioritized in the current cycle.",
        }.get(
            brs_risk_level,
            "STEADY SECURITY POSTURE. No findings requiring immediate action were detected — see the residual "
            "uncertainty note below before reading this as a zero-risk guarantee.",
        )

        elements.append(Paragraph(
            f"<b>ASSESSMENT STATUS:</b> {posture_description}",
            self.styles["NOVABodyBold"]
        ))

        intro = (
            f"NOVA completed a banking security audit of repository <b>{_esc(repo_name)}</b>. "
            f"The scanner performed static code parsing (SAST), software composition audit (SCA), "
            f"and deployment configuration assessments. A total of <b>{summary.get('total', 0)} security findings</b> "
            f"were logged during the pipeline run."
        )
        elements.append(Paragraph(intro, self.styles["NOVABody"]))
        elements.append(Spacer(1, 0.4 * cm))

        # Key Observations Block
        elements.append(Paragraph("Key Observations & Posture Analysis", self.styles["NOVAH2"]))
        critical_count = summary.get("CRITICAL", 0)
        high_count = summary.get("HIGH", 0)

        observations = (
            f"• <b>Critical Exposures:</b> {critical_count} critical-severity flaws were detected. These vulnerabilities "
            f"represent immediate exploit vectors affecting banking logic, token authorization, or data integrity.<br/>"
            f"• <b>High Vulnerability Vectors:</b> {high_count} high-severity flaws were logged, predominantly affecting package dependencies.<br/>"
            f"• <b>Risk Class:</b> The system resides in a <b>{brs_risk_level}</b> risk tier with a BRS score of <b>{brs_score:.1f}</b>.<br/>"
            f"• <b>Attack Surface Exposure:</b> Dependency footprint, patch hygiene, and configuration audits yield an exposure "
            f"index of <b>{attack_surface_exposure_score:.1f}/100</b> ({attack_surface_exposure_level}) — a composite measure of "
            f"factors correlated with undiscovered-vulnerability risk (dependency count, CVE density, staleness, risky "
            f"package categories, configuration risk), not a probability or prediction of any specific future exploit."
        )
        elements.append(Paragraph(observations, self.styles["NOVABody"]))
        elements.append(Spacer(1, 0.4 * cm))

        # Risk Level Explanation
        elements.append(Paragraph("Risk Score Model Explanation", self.styles["NOVAH2"]))
        explanation = (
            "The Banking Risk Score (BRS) is a weighted calculation reflecting vulnerability severity, CVSS values, business "
            "module criticality, internet exposure, regulatory compliance impact, and historical incident context. BRS values "
            "of 82 and above denote Critical risk (immediate remediation mandatory); 58-81 denote High risk (review and "
            "mitigation within days); 35-57 denote Medium risk; below 35 denotes Low risk. A scan reporting zero findings is "
            "never scored as a literal zero: no static/dependency/secrets scan pipeline can rule out every class of "
            "vulnerability, so a small residual baseline (typically 4-8) is retained to represent that irreducible "
            "uncertainty rather than overclaiming a provably secure result."
        )
        elements.append(Paragraph(explanation, self.styles["NOVABody"]))

        return elements

    def _build_threat_posture_overview(
        self, summary, brs_score, brs_risk_level, attack_surface_exposure_score, attack_surface_exposure_level
    ):
        elements = []
        elements.append(Paragraph("3. Threat Posture Overview", self.styles["NOVAH1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=10))

        # BRS / Attack Surface Exposure overview table
        elements.append(Paragraph("Banking Risk Scorecard", self.styles["NOVAH2"]))
        score_data = [
            ["Vulnerability Metric", "Score Value", "Rating Tier", "Mitigation Status"],
            ["Banking Risk Score (BRS)", f"{brs_score:.1f}", brs_risk_level.upper(), "Pending Patch"],
            [
                "Attack Surface Exposure",
                f"{attack_surface_exposure_score:.1f}/100",
                attack_surface_exposure_level.upper(),
                "Review Advisory",
            ],
        ]
        score_table = Table(score_data, colWidths=[6.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm])
        score_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NOVA_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 1), (-1, -1), NOVA_LIGHT),
            ("FONTNAME", (1, 1), (2, -1), "Helvetica-Bold"),
        ]))
        elements.append(score_table)
        elements.append(Spacer(1, 0.6 * cm))

        # Severity breakdown table
        elements.append(Paragraph("Threat Breakdown by Severity", self.styles["NOVAH2"]))
        sev_data = [
            ["Severity Level", "Vulnerabilities Logged", "Mitigation SLA Guide"],
            ["CRITICAL", str(summary.get("CRITICAL", 0)), "Immediate Patch (SLA: 24h)"],
            ["HIGH", str(summary.get("HIGH", 0)), "Mitigate within 7 days"],
            ["MEDIUM", str(summary.get("MEDIUM", 0)), "Mitigate within 30 days"],
            ["LOW", str(summary.get("LOW", 0)), "Log & Track"],
            ["INFO", str(summary.get("INFO", 0)), "Audit Reference Only"],
        ]
        sev_table = Table(sev_data, colWidths=[5 * cm, 5 * cm, 7 * cm])
        sev_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NOVA_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#FFE4E6")),
            ("TEXTCOLOR", (0, 1), (0, 1), SEVERITY_COLORS["CRITICAL"]),
            ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#FFEDD5")),
            ("TEXTCOLOR", (0, 2), (0, 2), SEVERITY_COLORS["HIGH"]),
            ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#FEF9C3")),
            ("TEXTCOLOR", (0, 3), (0, 3), SEVERITY_COLORS["MEDIUM"]),
            ("BACKGROUND", (0, 4), (-1, -1), NOVA_LIGHT),
        ]))
        elements.append(sev_table)
        elements.append(Spacer(1, 0.5 * cm))

        elements.append(Paragraph("Findings by Severity", self.styles["NOVAH2"]))
        elements.append(Spacer(1, CHART_SPACING))
        elements.append(_severity_bar_chart(summary))
        elements.append(Spacer(1, CHART_SPACING))

        return elements

    def _build_compliance_section(self, compliance_summary: dict, findings: list[dict]):
        elements = []
        elements.append(Paragraph("4. Regulatory Impact Analysis", self.styles["NOVAH1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=10))

        elements.append(Paragraph(
            "Banking applications require strict adherence to regulatory IT guidelines. Findings mapped to RBI, "
            "PCI-DSS, and SWIFT CSP frameworks are highlighted below.",
            self.styles["NOVABody"]
        ))
        elements.append(Spacer(1, 0.4 * cm))

        # Compliance frameworks table
        table_data = [["Compliance Standard", "Violations Count", "Framework Status"]]
        for key, data in compliance_summary.items():
            status = "COMPLIANT" if data["compliant"] else "NON-COMPLIANT"
            table_data.append([
                Paragraph(_esc(data["name"]), self.styles["NOVACellCenter"]),
                str(data["violations"]),
                status,
            ])

        comp_table = Table(table_data, colWidths=[7.5 * cm, 4.5 * cm, 5 * cm])
        comp_style = [
            ("BACKGROUND", (0, 0), (-1, 0), NOVA_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, NOVA_LIGHT]),
        ]

        # Highlight compliance status colors
        for idx, (key, data) in enumerate(compliance_summary.items(), 1):
            if data["compliant"]:
                comp_style.append(("TEXTCOLOR", (2, idx), (2, idx), colors.HexColor("#16A34A")))
            else:
                comp_style.append(("TEXTCOLOR", (2, idx), (2, idx), colors.HexColor("#DC2626")))
            comp_style.append(("FONTNAME", (2, idx), (2, idx), "Helvetica-Bold"))

        comp_table.setStyle(TableStyle(comp_style))
        elements.append(comp_table)
        elements.append(Spacer(1, 0.5 * cm))

        pie = _compliance_pie_chart(compliance_summary)
        if pie is not None:
            elements.append(Spacer(1, CHART_SPACING))
            elements.append(pie)
            elements.append(Spacer(1, CHART_SPACING))

        # Compliance mappings per finding
        elements.append(Paragraph("MAPPED AUDIT DEVIATIONS", self.styles["NOVAH2"]))
        violations = [
            f for f in findings
            if f.get("compliance") and f["severity"].upper() in {"CRITICAL", "HIGH", "MEDIUM"}
        ][:8]

        if violations:
            for f in violations:
                comp = f.get("compliance", {})
                elements.append(Paragraph(
                    f"• <b>[{f.get('severity', '')}] {_esc(f.get('title', ''))}</b>",
                    self.styles["NOVABody"]
                ))
                clauses = []
                if comp.get("rbi_clause"):
                    clauses.append(f"RBI IT 2021: <u>{_esc(comp['rbi_clause'])}</u>")
                if comp.get("pci_clause"):
                    clauses.append(f"PCI-DSS v4.0: <u>{_esc(comp['pci_clause'])}</u>")
                if comp.get("swift_clause"):
                    clauses.append(f"SWIFT CSP: <u>{_esc(comp['swift_clause'])}</u>")
                
                elements.append(Paragraph(
                    " &nbsp;&nbsp;&nbsp;&nbsp;MAPPED TO: " + " | ".join(clauses),
                    self.styles["NOVASmall"]
                ))
                elements.append(Spacer(1, 0.15 * cm))
        else:
            elements.append(Paragraph("No regulatory framework violations logged.", self.styles["NOVABody"]))

        return elements

    def _generate_banking_impact(self, f: dict) -> str:
        """Returns text already safe to interpolate directly into a `Paragraph`-bound
        f-string — every dynamic value here is escaped at this point, so callers must
        NOT wrap the return value in `_esc()` again (that would double-escape)."""
        comp = f.get("compliance", {})
        clauses = []
        if comp:
            if comp.get("rbi_clause"):
                clauses.append(f"RBI Guidelines Section {_esc(comp['rbi_clause'])}")
            if comp.get("pci_clause"):
                clauses.append(f"PCI DSS requirement {_esc(comp['pci_clause'])}")
            if comp.get("swift_clause"):
                clauses.append(f"SWIFT CSP clause {_esc(comp['swift_clause'])}")
        
        if clauses:
            ref_clause = " and ".join(clauses)
            return f"Direct violation of {ref_clause}. This critical deviation raises severe audit red flags, exposing the bank to regulatory sanctions, financial penalties by regulators, and potentially compromising user accounts."
        else:
            return "Compromises internal transaction processing boundaries. Exposes core system assets to unauthorized access, potentially violating RBI general security mandates."

    def _build_detailed_findings_section(self, findings: list[dict]):
        elements = []
        elements.append(Paragraph("5. Detailed Findings Section", self.styles["NOVAH1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=10))

        # Display top 5 critical findings in high detail
        critical_findings = [
            f for f in findings
            if f.get("severity", "").upper() in {"CRITICAL", "HIGH", "MEDIUM"}
        ][:5]

        if not critical_findings:
            elements.append(Paragraph("No detailed high-risk findings to report.", self.styles["NOVABody"]))
            return elements

        for idx, f in enumerate(critical_findings, 1):
            sev_color = SEVERITY_COLORS.get(f.get("severity", "").upper(), NOVA_MUTED)
            title_paragraph = Paragraph(
                f"Finding #{idx}: <b>{_esc(f.get('title', ''))}</b>",
                ParagraphStyle("det_title", fontSize=11, leading=14, fontName="Helvetica-Bold", textColor=NOVA_DARK, spaceBefore=8, spaceAfter=4)
            )

            # Metadata Table
            # NOTE: file_path is unbounded scanner-provided data — it must be a
            # Paragraph (word-wraps, grows row height) rather than a raw string,
            # or ReportLab draws it as one long line straight over the neighboring
            # column. The other cells here are short, fixed-vocabulary values.
            meta_data = [
                ["Severity:", f.get("severity", "").upper(), "CVSS Score:", f"{f.get('cvss', 0.0):.1f}"],
                ["Location:", Paragraph(_esc(f.get("file_path") or "Dependencies"), self.styles["NOVACell"]), "Line:", str(f.get("line_number") or "N/A")],
            ]
            meta_table = Table(meta_data, colWidths=[2.5 * cm, 6 * cm, 2.5 * cm, 6 * cm])
            meta_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (1, 0), (1, 0), sev_color),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.lightgrey),
            ]))
            # Title + metadata are both small/bounded (a couple of lines, fixed-vocabulary
            # values) so this KeepTogether can never fail to fit a page — it exists purely to
            # satisfy "keep the section title with at least one line of its content" without
            # reintroducing the unbounded-height KeepTogether risk fixed elsewhere in this file.
            # Description/impact/remediation below are deliberately NOT included — they're
            # unbounded (scanner/AI text) and already flow safely across a page break on their
            # own, same as any other Paragraph.
            elements.append(KeepTogether([title_paragraph, meta_table]))
            elements.append(Spacer(1, 0.15 * cm))

            elements.append(Paragraph(
                f"<b>Description:</b> {_esc(f.get('description', ''))}",
                self.styles["NOVABody"]
            ))

            # Business Impact
            biz_impact = f.get('ai_business_impact') or "Threatens the operational continuity of banking microservices."
            elements.append(Paragraph(
                f"<b>Business Impact:</b> {_esc(biz_impact)}",
                self.styles["NOVABody"]
            ))

            # Banking Impact
            banking_impact = self._generate_banking_impact(f)
            elements.append(Paragraph(
                f"<b>Banking Impact:</b> {banking_impact}",
                self.styles["NOVABody"]
            ))

            # Remediation
            remediation = f.get('ai_remediation') or "Please consult secure coding rules to fix this vulnerability."
            elements.append(Paragraph(
                f"<b>Remediation:</b> {_esc(remediation)}",
                self.styles["NOVABody"]
            ))

            elements.append(Spacer(1, 0.4 * cm))

        return elements

    def _generate_attack_scenario(self, f: dict) -> str:
        category = f.get("category", "").lower()
        title = f.get("title", "").lower()
        if "secret" in category or "credential" in title or "password" in title:
            return "An adversary scans code repositories or decompiles application assets to extract hardcoded API keys/passwords. They then authenticate directly to database interfaces or APIs, bypassing internal access logs."
        elif "sql" in category or "injection" in title:
            return "An attacker inputs specially crafted database payloads inside UI or API fields. The application database driver executes these queries directly, allowing the attacker to bypass authentication or fetch transaction ledgers."
        elif "crypto" in category or "weak" in title or "cipher" in title:
            return "A malicious actor intercepts network packets in transit, exploiting weaker encryption protocols to perform mathematical key collisions and recover customer credentials or payload details."
        elif "deserialization" in category or "pickle" in title:
            return "An attacker injects an encoded python object inside API requests. The application deserializes this object without verification, triggering arbitrary operating system commands and establishing a shell connection."
        elif "dependency" in category or "vulnerable" in category:
            return "An attacker launches automated exploits targeting the known CVE in the third-party library, forcing a memory buffer overflow to execute unauthorized scripts on the application node."
        else:
            return "An attacker exploits the configuration oversight to gain unauthorized permissions, allowing access to system settings or debug endpoints."

    def _build_ai_analyst_commentary(self, findings: list[dict]):
        elements = []
        elements.append(Paragraph("6. AI Security Analyst Commentary", self.styles["NOVAH1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=10))

        # Focus AI commentary on top 5 critical/high-severity findings
        target_findings = [
            f for f in findings
            if f.get("severity", "").upper() in {"CRITICAL", "HIGH", "MEDIUM"}
        ][:5]

        if not target_findings:
            elements.append(Paragraph("No critical or high findings requiring AI commentary.", self.styles["NOVABody"]))
            return elements

        for idx, f in enumerate(target_findings, 1):
            title_paragraph = Paragraph(
                f"Analyst Insight #{idx}: <b>{_esc(f.get('title', ''))}</b>",
                ParagraphStyle("ai_title", fontSize=10.5, leading=13, fontName="Helvetica-Bold", textColor=NOVA_DARK, spaceBefore=8, spaceAfter=4)
            )

            # Threat Analysis
            threat_analysis = f.get("ai_explanation") or "Automated vulnerability scanner identified potential exposure."

            # Attack Scenario (hardcoded strings from _generate_attack_scenario — no user data, no escaping needed)
            attack_scenario = self._generate_attack_scenario(f)

            # Risk Explanation
            risk_explanation = f.get("ai_business_impact") or "Vulnerability creates potential paths for lateral system escalation."

            # Recommended Action
            recommended_action = f.get("ai_remediation") or "Patch code and review system dependency trees."

            # AI Security Analyst Commentary box, styled as a shaded callout. Deliberately NOT
            # one big Table any more — an AI-generated field (ai_explanation/ai_business_impact/
            # ai_remediation) can be arbitrarily long, and a Table wrapped in KeepTogether that
            # doesn't fit even a fresh page silently abandons the "together" request, which used
            # to strand `title_paragraph` alone on a mostly-blank page while the box jumped to
            # the next one (reproduced and confirmed via a rendered test PDF). Individual
            # `Paragraph`s always split gracefully across a page boundary at a line boundary, no
            # matter how long, so only the small, bounded caption is kept with the title — the
            # unbounded body fields flow freely and can never orphan/overflow again.
            box_style = ParagraphStyle(
                "ai_box_field", parent=self.styles["NOVASmall"],
                backColor=colors.HexColor("#F8FAFC"), borderColor=colors.HexColor("#CBD5E1"),
                borderWidth=0.5, borderPadding=(4, 8, 2, 8), spaceAfter=0, leading=11,
            )
            caption_table = Table(
                [[Paragraph("<b>AI Security Analyst Commentary</b>", ParagraphStyle(
                    "ai_h", fontSize=8.5, fontName="Helvetica-Bold", textColor=colors.HexColor("#475569"),
                ))]],
                colWidths=[17 * cm],
            )
            caption_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#CBD5E1")),
                ("LINELEFT", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("LINERIGHT", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            elements.append(KeepTogether([title_paragraph, caption_table]))

            body_fields = [
                ("Threat Analysis", _esc(threat_analysis)),
                ("Attack Scenario", attack_scenario),
                ("Risk Explanation", _esc(risk_explanation)),
                ("Recommended Action", _esc(recommended_action)),
            ]
            for field_idx, (label, value) in enumerate(body_fields):
                style = box_style
                if field_idx == len(body_fields) - 1:
                    # Last field closes the shaded callout — draw the bottom/side border and
                    # restore normal paragraph spacing after it, instead of a shared Table's
                    # single outer box (see the docstring above for why this isn't one Table).
                    style = ParagraphStyle(
                        "ai_box_field_last", parent=box_style,
                        borderPadding=(2, 8, 4, 8), spaceAfter=6,
                    )
                elements.append(Paragraph(f"<b>{label}:</b> {value}", style))

        return elements

    def _build_action_plan(self, findings: list[dict]):
        elements = []
        elements.append(Paragraph("7. Executive Action Plan", self.styles["NOVAH1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=10))

        elements.append(Paragraph(
            "Banking stakeholders and CISOs must execute the following remediation actions based on logged threat profiles:",
            self.styles["NOVABody"]
        ))
        elements.append(Spacer(1, 0.3 * cm))

        # Priorities
        criticals = [f for f in findings if f["severity"].upper() == "CRITICAL"]
        highs = [f for f in findings if f["severity"].upper() == "HIGH"]
        mediums = [f for f in findings if f["severity"].upper() == "MEDIUM"]

        elements.append(Paragraph("<b>PRIORITY 1: Immediate Remediation (SLA: 24h - 48h)</b>", self.styles["NOVAH2"]))
        if criticals:
            p1_desc = f"Remediate the {len(criticals)} critical exposures logged in the codebase. Address SQL injection, token spoofing, or credential leaks immediately."
        else:
            p1_desc = "No critical vulnerabilities active. Verify authentication flows and continue automated integration checks."
        elements.append(Paragraph(p1_desc, self.styles["NOVABody"]))
        elements.append(Spacer(1, 0.2 * cm))

        elements.append(Paragraph("<b>PRIORITY 2: Dependency & Configuration Patching (SLA: 7 Days)</b>", self.styles["NOVAH2"]))
        if highs:
            p2_desc = f"Update the {len(highs)} outdated packages and libraries identified in the dependency audit. Focus on libraries with confirmed CVEs and high attack-surface exposure."
        else:
            p2_desc = "Evaluate and patch any medium-severity code issues and config files flagged in the latest scanner run."
        elements.append(Paragraph(p2_desc, self.styles["NOVABody"]))
        elements.append(Spacer(1, 0.2 * cm))

        elements.append(Paragraph("<b>PRIORITY 3: Compliance & Architecture Alignment (SLA: 30 Days)</b>", self.styles["NOVAH2"]))
        p3_desc = (
            "Verify complete RBI IT Framework alignment for encryption at rest and in transit. Update SBOM details "
            "and sign dependency definitions for the next regulatory audit cycle."
        )
        elements.append(Paragraph(p3_desc, self.styles["NOVABody"]))

        return elements

    def _build_appendix(self, scan_id, repo_name, compliance_summary, generated_at):
        elements = []
        elements.append(Paragraph("8. Appendix", self.styles["NOVAH1"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=10))

        # Compliance Basis
        bases = []
        for key, data in compliance_summary.items():
            bases.append(f"{data['name']}: {'COMPLIANT' if data['compliant'] else 'NON-COMPLIANT'}")
        bases_str = " | ".join(bases)

        elements.append(Paragraph(
            "<b>SARIF Integration:</b> A machine-readable SARIF v2.1.0 JSON file is generated alongside this document "
            f"({scan_id}_findings.sarif). This can be fed into IDEs or CI/CD pipelines (GitHub Actions, GitLab CI).<br/><br/>"
            "<b>SBOM Summary:</b> Software Bill of Materials compiled in CycloneDX JSON format "
            f"({scan_id}_sbom.json). It catalogs library trees, versions, and license profiles.<br/><br/>"
            f"<b>Metadata & Engine Version:</b> NOVA DevSecOps Core v1.0.0. Core scan time: "
            f"{generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}. Audit target: repository instance '{_esc(repo_name)}'.<br/>"
            f"<b>Regulatory Compliance Baseline:</b> {bases_str}",
            self.styles["NOVABody"]
        ))

        return elements



# ── SARIF Generator ───────────────────────────────────────────────────────────

def generate_sarif(
    scan_id: str,
    repo_name: str,
    findings: list[dict],
) -> dict:
    """
    Generate a valid SARIF 2.1.0 report from findings.
    SARIF is the standard format for static analysis results.
    """
    rules = {}
    results = []

    for finding in findings:
        rule_id = finding.get("category", "unknown").replace(" ", "_").replace("-", "_")
        severity = finding.get("severity", "warning").lower()

        # Map to SARIF severity levels
        sarif_level = {
            "critical": "error",
            "high": "error",
            "medium": "warning",
            "low": "note",
            "info": "none",
        }.get(severity, "warning")

        # Register rule if not seen
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": rule_id.replace("_", " ").title(),
                "shortDescription": {"text": finding.get("title", rule_id)},
                "fullDescription": {"text": finding.get("description", "")},
                "helpUri": "https://NOVA.security/rules/" + rule_id,
                "properties": {
                    "tags": [finding.get("category", "security")],
                    "precision": "medium",
                    "problem.severity": severity,
                },
            }

        # Build result
        result: dict = {
            "ruleId": rule_id,
            "level": sarif_level,
            "message": {"text": finding.get("description", finding.get("title", ""))},
            "properties": {
                "cvss": finding.get("cvss", 0.0),
                "brs": finding.get("brs", 0.0),
                "source": finding.get("source", ""),
            },
        }

        if finding.get("file_path"):
            location = {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": finding["file_path"],
                        "uriBaseId": "%SRCROOT%",
                    },
                }
            }
            if finding.get("line_number"):
                location["physicalLocation"]["region"] = {
                    "startLine": finding["line_number"],
                }
            result["locations"] = [location]

        results.append(result)

    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "NOVA",
                        "version": "1.0.0",
                        "informationUri": "https://NOVA.security",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
                "properties": {
                    "scan_id": scan_id,
                    "repository": repo_name,
                    "scanDate": datetime.now(timezone.utc).isoformat(),
                },
                "artifacts": [
                    {
                        "location": {"uri": "%SRCROOT%"},
                        "description": {"text": f"Source repository: {repo_name}"},
                    }
                ],
            }
        ],
    }

    return sarif


# ── CSV Export ────────────────────────────────────────────────────────────────

CSV_FIELDNAMES = [
    "title", "severity", "category", "cvss", "brs", "module",
    "file_path", "line_number", "source", "sources",
    "cwe_id", "owasp_category",
    "rbi_clause", "pci_clause", "swift_clause",
    "ai_explanation", "ai_remediation",
]


def generate_csv(findings: list[dict]) -> str:
    """Flat, spreadsheet-friendly export — one row per finding, findings-focused (no cover/narrative sections)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
    writer.writeheader()

    for f in findings:
        row = dict(f)
        compliance = f.get("compliance") or {}
        row["rbi_clause"] = compliance.get("rbi_clause", "")
        row["pci_clause"] = compliance.get("pci_clause", "")
        row["swift_clause"] = compliance.get("swift_clause", "")
        sources = f.get("sources")
        row["sources"] = "|".join(sources) if isinstance(sources, list) else (sources or "")
        writer.writerow(row)

    return buffer.getvalue()


# ── Technical PDF Report ──────────────────────────────────────────────────────

class NOVATechnicalPDFReport:
    """
    The engineering-facing counterpart to `NOVAPDFReport` (which is
    audience-scoped to executives/auditors and only details its top 5
    per severity tier). This one lists every finding, with the full
    CWE/OWASP taxonomy and cross-tool provenance the executive report
    deliberately omits for brevity.
    """

    def __init__(self, output_path: Path):
        self.output_path = output_path
        # Reuse NOVAPDFReport purely for its style setup — never call
        # .generate() on it, this class builds its own story/doc.
        self.styles = NOVAPDFReport(output_path).styles

    def generate(
        self,
        scan_id: str,
        repo_name: str,
        brs_score: float,
        brs_risk_level: str,
        findings: list[dict],
        summary: dict,
        generated_at: datetime,
    ) -> Path:
        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=A4,
            rightMargin=1.8 * cm,
            leftMargin=1.8 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=f"NOVA Technical Findings Report — {repo_name}",
            author="NOVA Platform",
            subject="Detailed Technical Vulnerability Report",
        )

        story = []
        story.append(Paragraph("NOVA Technical Findings Report", self.styles["NOVATitle"]))
        story.append(Paragraph(
            f"Repository: <b>{_esc(repo_name)}</b> &nbsp;|&nbsp; Scan ID: {_esc(scan_id)} &nbsp;|&nbsp; "
            f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            ParagraphStyle("sub", fontSize=9, textColor=NOVA_MUTED, alignment=TA_CENTER, spaceAfter=16),
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=14))

        story.append(Paragraph("Findings Summary", self.styles["NOVAH1"]))
        story.append(Spacer(1, CHART_SPACING))
        story.append(_severity_bar_chart(summary))
        story.append(Spacer(1, CHART_SPACING))
        story.append(PageBreak())

        story.append(Paragraph("All Findings — Technical Detail", self.styles["NOVAH1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=NOVA_BLUE, spaceAfter=10))

        ordered = sorted(
            findings,
            key=lambda f: SEVERITY_ORDER.index(f.get("severity", "INFO").upper())
            if f.get("severity", "").upper() in SEVERITY_ORDER
            else len(SEVERITY_ORDER),
        )

        if not ordered:
            story.append(Paragraph("No findings were reported for this scan.", self.styles["NOVABody"]))

        for idx, f in enumerate(ordered, 1):
            block = self._build_finding_block(idx, f)
            # Only the title + metadata table (the first two flowables — both small and
            # bounded: a couple of lines, fixed-vocabulary values) are kept together, so the
            # heading is never orphaned from at least its metadata. The remainder (description/
            # compliance/remediation) is unbounded scanner/AI text and is appended unwrapped —
            # a plain Paragraph already splits gracefully across a page break on its own; wrapping
            # the *entire* block (as this used to do) meant a long finding whose combined height
            # exceeded a full page silently abandoned the "keep together" request, which is what
            # produced the reported layout defects for very long AI explanations/descriptions.
            story.append(KeepTogether(block[:2]))
            story.extend(block[2:])

        doc.build(story, canvasmaker=partial(
            NumberedCanvas, scan_id=scan_id, repo_name=repo_name, generated_at=generated_at,
        ))
        logger.info("report_generator.pdf_technical.generated", path=str(self.output_path))
        return self.output_path

    def _build_finding_block(self, idx: int, f: dict) -> list:
        sev = f.get("severity", "").upper()
        sev_hex = SEVERITY_HEX.get(sev, "#64748B")
        elements = [
            Paragraph(
                f"#{idx} &nbsp; <font color='{sev_hex}'>[{sev}]</font> <b>{_esc(f.get('title', ''))}</b>",
                ParagraphStyle("tf_title", fontSize=10.5, leading=13, fontName="Helvetica-Bold", textColor=NOVA_DARK, spaceBefore=10, spaceAfter=4),
            )
        ]

        # NOTE: category/module/file_path/sources/CWE/OWASP are unbounded
        # scanner-provided strings — each is wrapped in a Paragraph (word-wraps,
        # grows row height) rather than passed as a raw string, or ReportLab
        # draws it as one long line straight over the neighboring column. The
        # label cells and CVSS/BRS/line-number values are short & fixed, so
        # they stay as plain strings.
        cell = self.styles["NOVACellTiny"]
        meta_rows = [
            ["CVSS:", f"{f.get('cvss', 0.0):.1f}", "BRS:", f"{f.get('brs', 0.0):.1f}"],
            ["Category:", Paragraph(_esc(f.get("category", "") or "N/A"), cell), "Module:", Paragraph(_esc(f.get("module", "") or "unclassified"), cell)],
            ["File:", Paragraph(_esc(f.get("file_path") or "Dependency"), cell), "Line:", str(f.get("line_number") or "N/A")],
            ["Source(s):", Paragraph(_esc("|".join(f.get("sources") or [f.get("source", "")])), cell), "CWE:", Paragraph(_esc(f.get("cwe_id") or "N/A"), cell)],
            ["OWASP:", Paragraph(_esc(f.get("owasp_category") or "N/A"), cell), "", ""],
        ]
        meta_table = Table(meta_rows, colWidths=[2.2 * cm, 6.3 * cm, 2.2 * cm, 6.3 * cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.lightgrey),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 0.1 * cm))

        elements.append(Paragraph(f"<b>Description:</b> {_esc(f.get('description', ''))}", self.styles["NOVASmall"]))

        compliance = f.get("compliance") or {}
        if compliance:
            clauses = [
                f"{label}: {_esc(compliance[key])}"
                for label, key in (("RBI", "rbi_clause"), ("PCI DSS", "pci_clause"), ("SWIFT CSP", "swift_clause"))
                if compliance.get(key)
            ]
            if clauses:
                elements.append(Paragraph(f"<b>Compliance:</b> {' | '.join(clauses)}", self.styles["NOVASmall"]))

        if f.get("ai_remediation"):
            elements.append(Paragraph(f"<b>Remediation:</b> {_esc(f['ai_remediation'])}", self.styles["NOVASmall"]))

        elements.append(Spacer(1, 0.25 * cm))
        return elements


# ── Report Context + Builder Dispatch ─────────────────────────────────────────
# The single interface `app/tasks/report_tasks.py` drives: one dataclass
# bundling everything any report type could need, and one dict mapping
# report_type -> a function of (ctx, reports_dir) -> Optional[Path]. Adding
# a new report type is: write a builder function, add one line here.

@dataclass
class ReportContext:
    scan_id: str
    repo_name: str
    findings: list[dict]
    brs_score: float
    brs_risk_level: str
    attack_surface_exposure_score: float
    attack_surface_exposure_level: str
    compliance_summary: dict
    summary: dict
    sbom: Optional[dict]
    unified_json: dict
    compliance_json: dict
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _build_pdf_executive(ctx: ReportContext, reports_dir: Path) -> Optional[Path]:
    path = reports_dir / f"{ctx.scan_id}_report.pdf"
    NOVAPDFReport(path).generate(
        scan_id=ctx.scan_id,
        repo_name=ctx.repo_name,
        brs_score=ctx.brs_score,
        brs_risk_level=ctx.brs_risk_level,
        attack_surface_exposure_score=ctx.attack_surface_exposure_score,
        attack_surface_exposure_level=ctx.attack_surface_exposure_level,
        findings=ctx.findings,
        compliance_summary=ctx.compliance_summary,
        summary=ctx.summary,
        generated_at=ctx.generated_at,
    )
    return path


def _build_pdf_technical(ctx: ReportContext, reports_dir: Path) -> Optional[Path]:
    path = reports_dir / f"{ctx.scan_id}_technical_report.pdf"
    NOVATechnicalPDFReport(path).generate(
        scan_id=ctx.scan_id,
        repo_name=ctx.repo_name,
        brs_score=ctx.brs_score,
        brs_risk_level=ctx.brs_risk_level,
        findings=ctx.findings,
        summary=ctx.summary,
        generated_at=ctx.generated_at,
    )
    return path


def _build_sarif(ctx: ReportContext, reports_dir: Path) -> Optional[Path]:
    path = reports_dir / f"{ctx.scan_id}_findings.sarif"
    sarif_data = generate_sarif(ctx.scan_id, ctx.repo_name, ctx.findings)
    path.write_text(json.dumps(sarif_data, indent=2), encoding="utf-8")
    return path


def _build_sbom(ctx: ReportContext, reports_dir: Path) -> Optional[Path]:
    path = reports_dir / f"{ctx.scan_id}_sbom.json"
    if ctx.sbom:
        path.write_text(json.dumps(ctx.sbom, indent=2), encoding="utf-8")
        return path
    return path if path.exists() else None  # already written by the dependency scanner, if at all


def _build_csv(ctx: ReportContext, reports_dir: Path) -> Optional[Path]:
    path = reports_dir / f"{ctx.scan_id}_findings.csv"
    path.write_text(generate_csv(ctx.findings), encoding="utf-8", newline="")
    return path


def _build_unified_findings(ctx: ReportContext, reports_dir: Path) -> Optional[Path]:
    path = reports_dir / f"{ctx.scan_id}_unified_findings.json"
    path.write_text(json.dumps(ctx.unified_json, indent=2), encoding="utf-8")
    return path


def _build_compliance_report(ctx: ReportContext, reports_dir: Path) -> Optional[Path]:
    path = reports_dir / f"{ctx.scan_id}_compliance_report.json"
    path.write_text(json.dumps(ctx.compliance_json, indent=2), encoding="utf-8")
    return path


REPORT_BUILDERS: Dict[str, Callable[[ReportContext, Path], Optional[Path]]] = {
    "pdf": _build_pdf_executive,
    "pdf_technical": _build_pdf_technical,
    "sarif": _build_sarif,
    "sbom": _build_sbom,
    "csv": _build_csv,
    "unified_findings": _build_unified_findings,
    "compliance_report": _build_compliance_report,
}


# ── Main Report Generator ─────────────────────────────────────────────────────

def generate_all_reports(
    scan_id: str,
    repo_name: str,
    findings: list[dict],
    brs_score: float,
    brs_risk_level: str,
    attack_surface_exposure_score: float,
    attack_surface_exposure_level: str,
    compliance_summary: dict,
    summary: dict,
    sbom: Optional[dict],
    reports_dir: Union[str, Path],
) -> Dict[str, Optional[str]]:
    """
    Generate all report artifacts: PDF, SARIF, and SBOM export.

    Returns:
        dict with keys: pdf_path, sarif_path, sbom_path
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc)

    paths: Dict[str, Optional[str]] = {
        "pdf_path": None,
        "sarif_path": None,
        "sbom_path": None,
    }

    # ── PDF ──
    try:
        pdf_path = reports_dir / f"{scan_id}_report.pdf"
        reporter = NOVAPDFReport(pdf_path)
        reporter.generate(
            scan_id=scan_id,
            repo_name=repo_name,
            brs_score=brs_score,
            brs_risk_level=brs_risk_level,
            attack_surface_exposure_score=attack_surface_exposure_score,
            attack_surface_exposure_level=attack_surface_exposure_level,
            findings=findings,
            compliance_summary=compliance_summary,
            summary=summary,
            generated_at=generated_at,
        )
        paths["pdf_path"] = str(pdf_path)
        logger.info("report_generator.pdf.ok", path=str(pdf_path))
    except Exception as exc:
        logger.exception("report_generator.pdf.error", error=str(exc))

    # ── SARIF ──
    try:
        sarif_path = reports_dir / f"{scan_id}_findings.sarif"
        sarif_data = generate_sarif(scan_id, repo_name, findings)
        sarif_path.write_text(json.dumps(sarif_data, indent=2), encoding="utf-8")
        paths["sarif_path"] = str(sarif_path)
        logger.info("report_generator.sarif.ok", path=str(sarif_path))
    except Exception as exc:
        logger.exception("report_generator.sarif.error", error=str(exc))

    # ── SBOM ──
    try:
        sbom_path = reports_dir / f"{scan_id}_sbom.json"
        if sbom:
            sbom_path.write_text(json.dumps(sbom, indent=2), encoding="utf-8")
        elif sbom_path.exists():
            pass  # Already written by dependency scanner
        paths["sbom_path"] = str(sbom_path) if sbom_path.exists() else None
        logger.info("report_generator.sbom.ok", path=str(sbom_path))
    except Exception as exc:
        logger.exception("report_generator.sbom.error", error=str(exc))

    return paths
