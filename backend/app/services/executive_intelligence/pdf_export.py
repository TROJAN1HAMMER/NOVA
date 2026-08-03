"""
NOVA — Executive Intelligence PDF Export
Renders a PREVIOUSLY-GIVEN answer to PDF — the caller (the API endpoint)
passes back exactly the question/answer/evidence/citations the client
already displayed, rather than this module re-deriving them. That's
deliberate: re-running evidence aggregation moments later could pick up a
scan that just completed and produce a PDF that no longer matches what
the user actually saw and reviewed on screen. Self-contained (own
reportlab usage, own styles) rather than extending
app/services/reports/report_generator.py — a one-off on-demand export
with no persisted Report row/storage backend, unlike that module's
scan-report pipeline, so reuse would mean bending its shape rather than
sharing real logic.
"""

import io
import re
from datetime import datetime, timezone
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = re.compile(r"`(.+?)`")
_TABLE_SEPARATOR_RE = re.compile(r"^:?-{2,}:?$")
_HEADING_RE = re.compile(r"^(#{1,2})\s+(.*)")
_BULLET_RE = re.compile(r"^[-•]\s+(.*)")
_NUMBERED_RE = re.compile(r"^(\d+)\.\s+(.*)")


def _inline_markdown(text: str) -> str:
    """`**bold**` -> `<b>bold</b>` and `` `code` `` -> a monospace `<font>`
    run (ReportLab's own Paragraph mini-markup, already used elsewhere in
    this codebase) — applied AFTER escaping so the `*`/backtick markers
    themselves are never mistaken for markup."""
    escaped = xml_escape(text)
    escaped = _CODE_RE.sub(r'<font face="Courier">\1</font>', escaped)
    return _BOLD_RE.sub(r"<b>\1</b>", escaped)


def _table_row_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _render_markdown_answer(answer: str, styles) -> list:
    """Lightweight markdown -> ReportLab pass for the LLM's structured
    answer text (headings, bullets/numbered lists, bold, pipe tables) so
    the PDF typesets it properly instead of showing raw `#`/`**`/`|`
    characters. Purely a typesetting concern over the same `answer` string
    the API already returns — computes nothing new."""
    heading1_style = ParagraphStyle("AnswerH1", parent=styles["Heading3"], spaceBefore=6, spaceAfter=4)
    heading2_style = ParagraphStyle("AnswerH2", parent=styles["Heading4"], spaceBefore=4, spaceAfter=2)
    bullet_style = ParagraphStyle("AnswerBullet", parent=styles["Normal"], leftIndent=14)
    cell_style = ParagraphStyle("AnswerTableCell", parent=styles["Normal"], fontSize=9)
    header_cell_style = ParagraphStyle("AnswerTableHeader", parent=cell_style, fontName="Helvetica-Bold")

    flowables: list = []
    lines = answer.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|") and lines[index].strip().endswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = [
                cells
                for row in table_lines
                for cells in [_table_row_cells(row)]
                if not all(_TABLE_SEPARATOR_RE.match(cell) for cell in cells)
            ]
            if rows:
                col_count = max(len(row) for row in rows)
                normalized_rows = [row + [""] * (col_count - len(row)) for row in rows]
                table_data = [
                    [
                        Paragraph(_inline_markdown(cell), header_cell_style if row_index == 0 else cell_style)
                        for cell in row
                    ]
                    for row_index, row in enumerate(normalized_rows)
                ]
                col_width = (17 * cm) / col_count
                table = Table(table_data, colWidths=[col_width] * col_count)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                flowables.append(table)
                flowables.append(Spacer(1, 0.2 * cm))
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            level, text = heading_match.groups()
            style = heading1_style if len(level) == 1 else heading2_style
            flowables.append(Paragraph(_inline_markdown(text), style))
            index += 1
            continue

        bullet_match = _BULLET_RE.match(stripped)
        if bullet_match:
            flowables.append(Paragraph(f"•&nbsp;&nbsp;{_inline_markdown(bullet_match.group(1))}", bullet_style))
            index += 1
            continue

        numbered_match = _NUMBERED_RE.match(stripped)
        if numbered_match:
            number, text = numbered_match.groups()
            flowables.append(Paragraph(f"{number}.&nbsp;&nbsp;{_inline_markdown(text)}", bullet_style))
            index += 1
            continue

        flowables.append(Paragraph(_inline_markdown(stripped), styles["Normal"]))
        flowables.append(Spacer(1, 0.15 * cm))
        index += 1

    return flowables


def _metric_rows(evidence: dict) -> list[list[str]]:
    rows = [["Metric", "Value"]]
    rows.append(["Data as of", evidence.get("generated_at", "N/A")])
    rows.append(["Total repositories", str(evidence.get("total_repositories", 0))])
    rows.append(["Total completed scans", str(evidence.get("total_completed_scans", 0))])
    rows.append(["Total findings", str(evidence.get("total_findings", 0))])
    avg_brs = evidence.get("portfolio_average_brs")
    rows.append(["Portfolio average BRS", f"{avg_brs:.1f}" if avg_brs is not None else "N/A"])

    severity = evidence.get("findings_by_severity") or {}
    if severity:
        rows.append(["Findings by severity", ", ".join(f"{k}={v}" for k, v in sorted(severity.items()))])

    for framework in evidence.get("compliance_by_framework") or []:
        total = framework["compliant_repo_count"] + framework["non_compliant_repo_count"]
        rows.append(
            [
                f"Compliance — {framework['framework_name']}",
                f"{framework['compliant_repo_count']} of {total} repos compliant, "
                f"{framework['total_violations']} violation(s)",
            ]
        )

    wow = evidence.get("week_over_week")
    if wow:
        rows.append(
            [
                "This week vs. last week",
                f"{wow['scans_this_week']} vs {wow['scans_last_week']} scans, "
                f"{wow['findings_this_week']} vs {wow['findings_last_week']} findings",
            ]
        )
    return rows


def render_pdf(
    *,
    question: str,
    answer: str,
    evidence: dict,
    citations: list[dict],
    confidence: Optional[float] = None,
    generated_at: Optional[str] = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm
    )
    styles = getSampleStyleSheet()
    excerpt_style = ParagraphStyle("Excerpt", parent=styles["Normal"], leftIndent=12, textColor=colors.HexColor("#444444"))

    story = [
        Paragraph("NOVA — Executive Intelligence Report", styles["Title"]),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"Generated {generated_at or datetime.now(timezone.utc).isoformat()}",
            ParagraphStyle("Meta", parent=styles["Normal"], textColor=colors.HexColor("#666666")),
        ),
        Spacer(1, 0.6 * cm),
        Paragraph("Question", styles["Heading2"]),
        Paragraph(xml_escape(question), styles["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Answer", styles["Heading2"]),
    ]

    story.extend(_render_markdown_answer(answer, styles))

    if confidence is not None:
        story.append(
            Paragraph(
                f"Knowledge-base citation confidence: {round(confidence * 100)}%",
                ParagraphStyle("Meta", parent=styles["Normal"], textColor=colors.HexColor("#666666")),
            )
        )

    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Evidence (scan history)", styles["Heading2"]))
    table = Table(_metric_rows(evidence), colWidths=[7 * cm, 9.5 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    if citations:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Sources", styles["Heading2"]))
        for index, citation in enumerate(citations, start=1):
            header = f"[{index}] {citation.get('filename', 'unknown')}"
            if citation.get("section_path"):
                header += f" — {citation['section_path']}"
            if citation.get("page_number") is not None:
                header += f" (page {citation['page_number']})"
            story.append(Paragraph(xml_escape(header), styles["Normal"]))
            story.append(Paragraph(xml_escape(citation.get("excerpt", "")).replace("\n", "<br/>"), excerpt_style))
            story.append(Spacer(1, 0.25 * cm))

    doc.build(story)
    return buffer.getvalue()
