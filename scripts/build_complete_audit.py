"""
RegIntel RAG - Master Codebase Audit Generator.
Compiles:
  1. docs/RegIntel_RAG_Complete_Codebase_Audit.md
  2. docs/RegIntel_RAG_Complete_Codebase_Audit.pdf
"""

import os
import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_sections_1_10 import SECTIONS_1_TO_10
from scripts.audit_sections_11_25 import SECTIONS_11_TO_25
from scripts.audit_sections_26_40 import SECTIONS_26_TO_40
from scripts.audit_sections_41_50 import SECTIONS_41_TO_50

# ReportLab modules
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
MD_PATH = DOCS_DIR / "RegIntel_RAG_Complete_Codebase_Audit.md"
PDF_PATH = DOCS_DIR / "RegIntel_RAG_Complete_Codebase_Audit.pdf"


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page numbers and running headers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return  # Suppress running header/footer on cover page

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#4b5563"))

        # Running Header
        self.drawString(54, 11 * 72 - 36, "REGINTEL RAG — COMPLETE TECHNICAL ARCHITECTURE & CODEBASE AUDIT")
        self.setFont("Helvetica", 8)
        self.drawRightString(8.5 * 72 - 54, 11 * 72 - 36, "CONFIDENTIAL / TECHNICAL REPORT")
        self.setStrokeColor(colors.HexColor("#e5e7eb"))
        self.setLineWidth(0.5)
        self.line(54, 11 * 72 - 40, 8.5 * 72 - 54, 11 * 72 - 40)

        # Running Footer
        self.line(54, 45, 8.5 * 72 - 54, 45)
        self.drawString(54, 32, "Audited Repository: RegIntel-RAG | Commit: 878b33b | Version: 0.1.0")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * 72 - 54, 32, page_str)
        self.restoreState()


def write_markdown_report():
    """Writes the consolidated markdown audit document."""
    full_markdown = "\n\n".join([
        SECTIONS_1_TO_10.strip(),
        SECTIONS_11_TO_25.strip(),
        SECTIONS_26_TO_40.strip(),
        SECTIONS_41_TO_50.strip()
    ])
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(full_markdown)
    print(f"[OK] Markdown report written to: {MD_PATH} ({len(full_markdown)} bytes)")
    return full_markdown


def build_pdf_report():
    """Compiles the professional PDF audit document using ReportLab."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=26,
        leading=32,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=10,
    )

    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=18,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=15,
    )

    desc_style = ParagraphStyle(
        'CoverDesc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#475569'),
        spaceAfter=25,
    )

    h1_style = ParagraphStyle(
        'AuditH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=18,
        spaceAfter=8,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        'AuditH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor('#1e40af'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        'AuditBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        'AuditBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#1f2937'),
        leftIndent=14,
        spaceAfter=4,
    )

    code_style = ParagraphStyle(
        'AuditCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor('#0f172a'),
    )

    th_style = ParagraphStyle(
        'AuditTH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.white,
    )

    td_style = ParagraphStyle(
        'AuditTD',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#1f2937'),
    )

    callout_style = ParagraphStyle(
        'AuditCallout',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#92400e'),
    )

    story = []

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 40))
    story.append(Paragraph("REGINTEL RAG", title_style))
    story.append(Paragraph("AI-Powered Regulatory Intelligence & Change Detection Platform", subtitle_style))
    story.append(Paragraph(
        "Complete Technical Architecture, Implementation Verification, Technology Stack, "
        "Workflows, Evaluation Results, and Codebase Audit Report.",
        desc_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#2563eb'), spaceAfter=25))

    meta_rows = [
        [Paragraph("<b>Audit Date:</b>", td_style), Paragraph("September 3, 2026", td_style)],
        [Paragraph("<b>Git Commit HEAD:</b>", td_style), Paragraph("<code>878b33b616d61808d2faa41b40ecbf2ea1dff87f</code>", td_style)],
        [Paragraph("<b>Application Version:</b>", td_style), Paragraph("0.1.0 (from app/config.py)", td_style)],
        [Paragraph("<b>Primary Domain:</b>", td_style), Paragraph("SEBI Financial Regulatory Intelligence & Compliance Auditing", td_style)],
        [Paragraph("<b>Backend Architecture:</b>", td_style), Paragraph("FastAPI, MongoDB Atlas, Google Gemini Embeddings (768d), BM25, BGE Reranker", td_style)],
        [Paragraph("<b>Frontend Architecture:</b>", td_style), Paragraph("React 18, TypeScript 5.5, Vite 5.4 Single-Page Application (7 core views)", td_style)],
        [Paragraph("<b>Testing & Quality Gate:</b>", td_style), Paragraph("263 Passed Backend Pytest Suite | 12 Passed Frontend Vitest Suite", td_style)],
        [Paragraph("<b>Audit Mode:</b>", td_style), Paragraph("100% Read-Only Codebase Inspection & Empirical Verification", td_style)],
    ]
    meta_table = Table(meta_rows, colWidths=[140, 364])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 35))
    exec_summary_cover = (
        "<b>Auditor Executive Summary:</b> This audit report provides a rigorous, code-grounded architectural "
        "and business analysis of the RegIntel RAG repository. Every feature, API endpoint, schema, and benchmark metric "
        "has been audited directly against active source files. Inconsistencies between documentation claims (e.g., target resume bullets) "
        "and active code artifacts (e.g., actual measured benchmark reports) are explicitly identified and documented."
    )
    story.append(Paragraph(exec_summary_cover, body_style))
    story.append(PageBreak())

    # =========================================================================
    # PARSE ALL SECTIONS INTO STORY
    # =========================================================================
    all_sections = [
        SECTIONS_1_TO_10,
        SECTIONS_11_TO_25,
        SECTIONS_26_TO_40,
        SECTIONS_41_TO_50
    ]

    for section_block in all_sections:
        lines = section_block.split('\n')
        i = 0
        in_code_block = False
        code_lines = []
        in_table = False
        table_lines = []

        while i < len(lines):
            line = lines[i]

            # Handle code blocks
            if line.startswith('```'):
                if in_code_block:
                    in_code_block = False
                    if code_lines:
                        # Chunk long code blocks to allow clean page splitting
                        chunk_size = 30
                        for start_idx in range(0, len(code_lines), chunk_size):
                            chunk = code_lines[start_idx:start_idx + chunk_size]
                            code_text = '\n'.join(chunk)
                            code_table = Table(
                                [[Preformatted(code_text, code_style)]],
                                colWidths=[492]
                            )
                            code_table.setStyle(TableStyle([
                                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                                ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#cbd5e1')),
                                ('TOPPADDING', (0, 0), (-1, -1), 4),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                            ]))
                            story.append(code_table)
                            story.append(Spacer(1, 3))
                        story.append(Spacer(1, 4))
                    code_lines = []
                else:
                    in_code_block = True
                    code_lines = []
                i += 1
                continue

            if in_code_block:
                code_lines.append(line)
                i += 1
                continue

            # Handle markdown tables
            if line.strip().startswith('|') and '|' in line.strip()[1:]:
                in_table = True
                table_lines.append(line)
                i += 1
                continue
            elif in_table:
                # End of table, process table_lines
                in_table = False
                parsed_table = parse_markdown_table(table_lines, th_style, td_style)
                if parsed_table:
                    story.append(parsed_table)
                    story.append(Spacer(1, 8))
                table_lines = []
                # Don't increment i, re-evaluate current line

            # Handle callout boxes (> [!NOTE] or > [!WARNING] or > [!IMPORTANT])
            if line.startswith('>'):
                callout_text = line.lstrip('> ').strip()
                # Clean up callout headers
                callout_text = re.sub(r'\[!(NOTE|WARNING|IMPORTANT|TIP|CAUTION)\]', r'<b>\1:</b>', callout_text)
                callout_table = Table(
                    [[Paragraph(callout_text, callout_style)]],
                    colWidths=[492]
                )
                callout_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef3c7')),
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#f59e0b')),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ]))
                story.append(callout_table)
                story.append(Spacer(1, 6))
                i += 1
                continue

            # Headings
            if line.startswith('## SECTION'):
                clean_title = line.lstrip('#').strip()
                story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor('#cbd5e1'), spaceBefore=12, spaceAfter=8))
                story.append(Paragraph(clean_title, h1_style))
            elif line.startswith('###'):
                clean_title = line.lstrip('#').strip()
                story.append(Paragraph(clean_title, h2_style))
            elif line.startswith('####'):
                clean_title = line.lstrip('#').strip()
                story.append(Paragraph(f"<b>{clean_title}</b>", body_style))
            elif line.startswith('- **') or line.startswith('* **') or line.startswith('- ') or line.startswith('* '):
                # Bullet point
                b_text = re.sub(r'^[-*]\s+', '', line).strip()
                # Convert markdown bold to html bold
                b_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', b_text)
                b_text = re.sub(r'`(.*?)`', r'<code>\1</code>', b_text)
                story.append(Paragraph(f"• {b_text}", bullet_style))
            elif line.strip() and not line.startswith('---'):
                # Standard paragraph
                p_text = line.strip()
                p_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', p_text)
                p_text = re.sub(r'`(.*?)`', r'<code>\1</code>', p_text)
                story.append(Paragraph(p_text, body_style))

            i += 1

        # Catch trailing table at end of block
        if in_table and table_lines:
            parsed_table = parse_markdown_table(table_lines, th_style, td_style)
            if parsed_table:
                story.append(parsed_table)
                story.append(Spacer(1, 8))

    # Build PDF using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[OK] Professional PDF report compiled to: {PDF_PATH}")


def parse_markdown_table(table_lines, th_style, td_style):
    """Parses a markdown table into a ReportLab Table flowable with wrapped paragraphs."""
    if len(table_lines) < 2:
        return None

    raw_rows = []
    for line in table_lines:
        line = line.strip()
        if line.startswith('|') and line.endswith('|'):
            cells = [c.strip() for c in line[1:-1].split('|')]
        else:
            cells = [c.strip() for c in line.split('|')]
        # Skip markdown separator row |:---|:---|
        if all(re.match(r'^:?-+:?$', c) for c in cells if c):
            continue
        raw_rows.append(cells)

    if not raw_rows:
        return None

    header_cells = raw_rows[0]
    data_rows = raw_rows[1:]
    num_cols = len(header_cells)

    if num_cols == 0:
        return None

    # Calculate column widths proportionally
    available_width = 492.0
    col_width = available_width / num_cols

    # Wrap cells in Paragraph
    table_data = []

    # Headers
    h_row = []
    for c in header_cells:
        clean_c = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', c)
        clean_c = re.sub(r'`(.*?)`', r'<code>\1</code>', clean_c)
        h_row.append(Paragraph(clean_c, th_style))
    table_data.append(h_row)

    # Body
    for row in data_rows:
        # Pad row to match header count
        while len(row) < num_cols:
            row.append("")
        row = row[:num_cols]

        b_row = []
        for c in row:
            clean_c = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', c)
            clean_c = re.sub(r'\*(.*?)\*', r'<i>\1</i>', clean_c)
            clean_c = re.sub(r'`(.*?)`', r'<code>\1</code>', clean_c)
            b_row.append(Paragraph(clean_c, td_style))
        table_data.append(b_row)

    t = Table(table_data, colWidths=[col_width] * num_cols)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    return t


if __name__ == "__main__":
    print("Executing RegIntel RAG Codebase Audit Generator...")
    md = write_markdown_report()
    build_pdf_report()
    print("Done!")
