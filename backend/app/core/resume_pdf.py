"""
Renders a tailored resume (plain text, as produced by the Resume Tailor Agent) into a
clean, single-column PDF — Gate 10. Used for both apply paths: the email attachment
(recruiters expect a PDF, not a .txt) and the "Apply on LinkedIn" download (LinkedIn's
upload only accepts PDF/DOCX).

Deliberately simple and deterministic — layout is inferred from the text itself, never
rewritten: first non-empty line = the name (large, bold), short lines that look like
section headings = bold, "-"/"•"/"*" lines = indented bullets, everything else = body.
What the user approved on the review screen is exactly what ends up in the PDF.
"""
import re
from pathlib import Path

from fpdf import FPDF

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT = "DejaVu"

KNOWN_HEADINGS = {
    "summary", "profile", "objective", "education", "experience", "work experience",
    "internships", "internship", "projects", "skills", "technical skills", "certifications",
    "achievements", "awards", "publications", "activities", "extracurricular activities",
    "positions of responsibility", "languages", "interests", "coursework", "relevant coursework",
}
BULLET_RE = re.compile(r"^\s*([-•*▪●◦·])\s+")


def _is_heading(line: str) -> bool:
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > 40:
        return False
    if stripped.lower() in KNOWN_HEADINGS:
        return True
    letters = [c for c in stripped if c.isalpha()]
    return len(letters) >= 3 and all(c.isupper() for c in letters)


def render_resume_pdf(text: str, title: str = "Resume") -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_title(title)
    pdf.set_creator("Pathlight")
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_font(FONT, "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font(FONT, "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_page()
    width = pdf.epw

    lines = text.replace("\r\n", "\n").split("\n")
    name_done = False
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            pdf.ln(2.5)
            continue

        if not name_done:
            pdf.set_font(FONT, "B", 17)
            pdf.multi_cell(width, 8, line.strip(), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
            name_done = True
            continue

        if _is_heading(line):
            pdf.ln(2)
            pdf.set_font(FONT, "B", 11.5)
            pdf.multi_cell(width, 6, line.strip(), new_x="LMARGIN", new_y="NEXT")
            y = pdf.get_y()
            pdf.set_draw_color(180, 180, 190)
            pdf.line(pdf.l_margin, y, pdf.l_margin + width, y)
            pdf.ln(1.5)
            continue

        bullet = BULLET_RE.match(line)
        pdf.set_font(FONT, "", 10)
        if bullet:
            pdf.set_x(pdf.l_margin + 3)
            pdf.cell(4, 5.2, "•")
            pdf.multi_cell(width - 7, 5.2, line[bullet.end():].strip(), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.multi_cell(width, 5.2, line.strip(), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
