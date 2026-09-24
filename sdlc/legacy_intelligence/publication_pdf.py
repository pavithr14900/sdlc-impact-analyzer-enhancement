"""Publication cover and running folios for the saved Markdown document."""
from io import BytesIO
from pathlib import Path
import tempfile
import os

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from sdlc.agents.quality_agent import _render_documentation_pdf


def render_publication_pdf(doc: dict, destination: Path):
    handle, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".pdf")
    os.close(handle)
    try:
        _render_documentation_pdf(doc["content"], temporary, wide_tables=doc["type"] == "api_documentation")
        source = PdfReader(temporary)
        writer = PdfWriter()
        cover = BytesIO()
        page = canvas.Canvas(cover, pagesize=A4)
        width, height = A4
        page.setFillColor(colors.HexColor("#13243e"))
        page.rect(0, height - 300, width, 300, fill=1, stroke=0)
        page.setFillColor(colors.HexColor("#bca4ff"))
        page.setFont("Helvetica-Bold", 11)
        page.drawString(48, height - 66, "BUILDPILOT  /  LEGACY CODE INTELLIGENCE")
        page.setFillColor(colors.white)
        y = height - 130
        for line in simpleSplit(doc["title"], "Helvetica-Bold", 30, width - 96):
            page.setFont("Helvetica-Bold", 30)
            page.drawString(48, y, line)
            y -= 40
        page.setFillColor(colors.HexColor("#d0dced"))
        page.setFont("Helvetica", 12)
        page.drawString(48, height - 266, "Engineering reference | Source-backed documentation")
        page.setFillColor(colors.HexColor("#33465e"))
        y = height - 355
        for label, value in [("DOCUMENT STATUS", "AI-authored review draft" if doc.get("generationMode") == "ai-authored" else "Source analysis summary"),
                             ("GENERATED", doc.get("generatedAt", "")[:10]),
                             ("SOURCE REFERENCES", str(len(doc.get("evidence", [])))),
                             ("DOCUMENT REVISION", doc.get("revision", "")[:12])]:
            page.setFont("Helvetica-Bold", 9)
            page.drawString(48, y, label)
            page.setFont("Helvetica", 12)
            page.drawString(48, y - 22, value)
            y -= 68
        page.setFont("Helvetica", 10)
        page.drawString(48, 60, "Prepared for engineering review, onboarding and knowledge transfer.")
        page.save()
        cover.seek(0)
        writer.add_page(PdfReader(cover).pages[0])
        for number, body in enumerate(source.pages, 1):
            overlay = BytesIO()
            body_width, body_height = float(body.mediabox.width), float(body.mediabox.height)
            c = canvas.Canvas(overlay, pagesize=(body_width, body_height))
            c.setStrokeColor(colors.HexColor("#dce3ec"))
            c.line(48, body_height - 32, body_width - 48, body_height - 32)
            c.setFillColor(colors.HexColor("#6b7d95"))
            c.setFont("Helvetica", 8)
            c.drawString(48, body_height - 24, "BuildPilot | " + doc["title"])
            c.drawString(48, 24, "Legacy Code Intelligence | Review draft")
            c.drawRightString(body_width - 48, 24, f"{number} / {len(source.pages)}")
            c.save()
            overlay.seek(0)
            body.merge_page(PdfReader(overlay).pages[0])
            writer.add_page(body)
        writer.add_metadata({"/Title": doc["title"], "/Author": "BuildPilot", "/Subject": "Legacy Code Intelligence engineering reference"})
        with open(destination, "wb") as stream:
            writer.write(stream)
    finally:
        Path(temporary).unlink(missing_ok=True)
