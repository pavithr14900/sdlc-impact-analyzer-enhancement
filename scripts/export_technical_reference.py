"""Render the repository technical reference as a standalone PDF."""
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted,
    LongTable, TableStyle, KeepTogether,
)
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "buildpilot-technical-reference.md"
OUTPUT = ROOT / "generated" / "reports" / "BuildPilot-Technical-Reference.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyRef", fontName="Helvetica", fontSize=9.5,
                          leading=14, spaceAfter=7, textColor=colors.HexColor("#24364b")))
styles.add(ParagraphStyle(name="CellRef", parent=styles["BodyRef"], fontSize=8,
                          leading=11, spaceAfter=0, splitLongWords=True))
styles.add(ParagraphStyle(name="HeadRef", parent=styles["Heading2"], fontSize=14,
                          leading=18, spaceBefore=16, spaceAfter=9,
                          textColor=colors.HexColor("#163d68")))
styles.add(ParagraphStyle(name="SubRef", parent=styles["Heading3"], fontSize=11,
                          leading=15, spaceBefore=10, spaceAfter=6))
styles.add(ParagraphStyle(name="CodeRef", fontName="Courier", fontSize=8,
                          leading=12, backColor=colors.HexColor("#eef3f8"),
                          borderPadding=9, spaceBefore=6, spaceAfter=12))
styles.add(ParagraphStyle(name="CoverRef", fontName="Helvetica-Bold", fontSize=30,
                          leading=38, textColor=colors.HexColor("#163d68"), spaceAfter=20))
styles.add(ParagraphStyle(name="CoverSubRef", parent=styles["BodyRef"], fontSize=14,
                          leading=21, spaceAfter=16))


def para(text, style="BodyRef"):
    value = escape(text)
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    return Paragraph(value, styles[style])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d4deea"))
    canvas.line(44, 40, A4[0] - 44, 40)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#60738a"))
    canvas.drawString(44, 27, "BuildPilot | Application Technical Reference")
    canvas.drawRightString(A4[0] - 44, 27, f"Page {doc.page}")
    canvas.restoreState()


text = SOURCE.read_text(encoding="utf-8")
lines = text.splitlines()
story = [Spacer(1, 85), para("BUILDPILOT", "CoverRef"),
         para("Application Technical Reference", "CoverSubRef"),
         para("Architecture, LangGraph workflows, agents, application sections, APIs and persistence", "CoverSubRef"),
         Spacer(1, 24), para("Repository: sdlc-impact-analyzer-enhancement"),
         para("Prepared: 23 September 2026"),
         Spacer(1, 24), para("Based on the reviewed local source implementation, including the legacy chatbot improvements. Intended for engineering review, onboarding and knowledge transfer."),
         PageBreak(), para("Contents", "HeadRef")]
for line in lines:
    if line.startswith("## "):
        story.append(para(line[3:]))
story.append(PageBreak())
i = 0
while i < len(lines):
    line = lines[i].strip()
    if not line or line.startswith("# "):
        i += 1
        continue
    if line.startswith("```"):
        block = []
        i += 1
        while i < len(lines) and not lines[i].startswith("```"):
            block.append(lines[i])
            i += 1
        story.append(Preformatted("\n".join(block), styles["CodeRef"]))
        i += 1
        continue
    if line.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            cells = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r"[-: ]+", cell) for cell in cells):
                rows.append(cells)
            i += 1
        data = [[para(cell, "CellRef") for cell in row] for row in rows]
        width = A4[0] - 88
        widths = [width * .39, width * .61] if len(rows[0]) == 2 else [width * .24, width * .31, width * .45]
        table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce8f5")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fb")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, 0), (-1, 0), .7, colors.HexColor("#a6bdd7")),
        ]))
        story.extend([table, Spacer(1, 11)])
        continue
    if line.startswith("## "):
        story.append(para(line[3:], "HeadRef"))
    elif line.startswith("### "):
        story.append(para(line[4:], "SubRef"))
    elif line.startswith("- "):
        story.append(para("\u2022 " + line[2:]))
    else:
        story.append(para(line))
    i += 1

doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=44, leftMargin=44,
                        topMargin=42, bottomMargin=55, title="BuildPilot Application Technical Reference",
                        author="BuildPilot", subject="Architecture, LangGraph workflows and agents")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
reader = PdfReader(OUTPUT)
extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
for heading in [line[3:] for line in lines if line.startswith("## ")]:
    assert heading in extracted, f"Missing section: {heading}"
assert len(reader.pages) > 5
assert all((page.extract_text() or "").strip() for page in reader.pages)
print(f"PDF: {OUTPUT}")
print(f"Validated {len(reader.pages)} pages, all 17 sections, {OUTPUT.stat().st_size:,} bytes.")
