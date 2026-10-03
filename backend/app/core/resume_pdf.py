"""
Renders a tailored resume (plain text, as produced by the Resume Tailor Agent) into a
clean, single-column, ATS-friendly PDF — Gate 10. Used for both apply paths: the email
attachment and the "Apply on LinkedIn" download.

Layout is inferred from the text itself, never rewritten — what the user approved on
the review screen is exactly the text in the PDF:
- first non-empty line = the name (large, centered)
- the contact line right under it (email / phone / links joined by "|") = centered, small
- short lines that look like section headings = small caps-style heading with a rule
- "-"/"•"/"*" lines = bullets with a hanging indent
- "Label: values" lines (skills categories) = bold label
- a trailing date range ("2023 – 2027", "June 2025 – July 2025") = right-aligned

ATS-friendliness: real text (no images), one column, standard fonts embedded, reading
order top-to-bottom. Every URL and email address is a real clickable link AND visible as
text — ATS parsers read the text, people click the link.
"""
import re
from pathlib import Path

from fpdf import FPDF

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT = "DejaVu"

INK = (24, 24, 27)
MUTED = (82, 82, 91)
RULE = (200, 200, 206)
LINK = (29, 78, 216)

KNOWN_HEADINGS = {
    "summary", "profile", "objective", "education", "experience", "work experience",
    "internships", "internship", "projects", "skills", "technical skills", "certifications",
    "achievements", "awards", "publications", "activities", "extracurricular activities",
    "positions of responsibility", "languages", "interests", "coursework", "relevant coursework",
    "professional summary", "core competencies", "certifications & achievements", "leadership",
    "volunteering", "honors", "research", "academic projects", "personal projects",
}
BULLET_RE = re.compile(r"^\s*([-•*▪●◦·])\s+")
LABEL_RE = re.compile(r"^([A-Z][A-Za-z/&()+.\- ]{1,32}):\s+(.+)$")
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
_DATE = rf"(?:{_MONTH}\s+)?(?:19|20)\d{{2}}"
DATE_TAIL_RE = re.compile(rf"\s+({_DATE}(?:\s*[–—-]\s*(?:{_DATE}|Present|Current|Now|Ongoing))?)\s*$", re.I)
TOKEN_RE = re.compile(
    r"(?P<email>[\w.+-]+@[\w-]+\.[\w.-]+)"
    r"|(?P<url>(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s|,;)\]]*)?)",
    re.I,
)


def is_heading(line: str) -> bool:
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > 40:
        return False
    if stripped.lower() in KNOWN_HEADINGS:
        return True
    letters = [c for c in stripped if c.isalpha()]
    return len(letters) >= 3 and all(c.isupper() for c in letters)


def _href(token: str, kind: str) -> str | None:
    if kind == "email":
        return f"mailto:{token}"
    # Only things that are clearly addresses: a path, a scheme, or www. Plain words with a
    # dot ("Node.js", "B.Tech") are skills, not links.
    if "/" in token or token.lower().startswith(("http", "www.")):
        return token if token.lower().startswith("http") else f"https://{token}"
    return None


def _write_rich(pdf: FPDF, text: str, h: float, size: float, color=INK, bold_prefix: str | None = None) -> None:
    """Writes one logical line with inline clickable links, wrapping at the current
    left margin (callers set l_margin for hanging indents)."""
    if bold_prefix:
        pdf.set_font(FONT, "B", size)
        pdf.set_text_color(*color)
        pdf.write(h, bold_prefix)
    pos = 0
    for m in TOKEN_RE.finditer(text):
        kind = "email" if m.group("email") else "url"
        token = m.group(0).rstrip(".")
        href = _href(token, kind)
        if href is None:
            continue
        if m.start() > pos:
            pdf.set_font(FONT, "", size)
            pdf.set_text_color(*color)
            pdf.write(h, text[pos:m.start()])
        pdf.set_font(FONT, "", size)
        pdf.set_text_color(*LINK)
        pdf.write(h, token, link=href)
        pos = m.start() + len(token)
    if pos < len(text):
        pdf.set_font(FONT, "", size)
        pdf.set_text_color(*color)
        pdf.write(h, text[pos:])
    pdf.set_text_color(*INK)
    pdf.ln(h)


def render_resume_pdf(text: str, title: str = "Resume") -> bytes:
    """Renders at full size; if that spills onto a second page, retries a little tighter
    (a one-page resume is what recruiters and ATS-tuned templates expect for students).
    Never shrinks below 86% — past that, two readable pages beat one cramped one."""
    pdf = None
    for k in (1.0, 0.95, 0.9, 0.86):
        pdf = _render(text, title, k)
        if pdf.page_no() == 1:
            break
    return bytes(pdf.output())


def _render(text: str, title: str, k: float) -> FPDF:
    pdf = FPDF(format="A4")
    pdf.set_title(title)
    pdf.set_author(title.split(" Resume")[0].replace("_", " "))
    pdf.set_creator("Pathlight")
    margin = 16
    pdf.set_margins(margin, 14, margin)
    pdf.set_auto_page_break(auto=True, margin=14)
    # Module-level font choice is safe: rendering is synchronous, never interleaved.
    global FONT
    # Helvetica is compact (a full resume fits one page) and what most ATS-tested
    # templates use, but only covers Windows-1252; anything outside it (non-Latin names,
    # symbols) falls back to the embedded DejaVu, which covers everything.
    try:
        text.encode("cp1252")
        FONT = "helvetica"
        pdf.core_fonts_encoding = "windows-1252"  # en dash, bullet, curly quotes
    except UnicodeEncodeError:
        FONT = "DejaVu"
        pdf.add_font(FONT, "", str(FONT_DIR / "DejaVuSans.ttf"))
        pdf.add_font(FONT, "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_page()
    width = pdf.epw

    lines = [l.rstrip() for l in text.replace("\r\n", "\n").split("\n")]
    content = [l for l in lines if l.strip()]
    name = content[0].strip() if content else ""
    contact = content[1].strip() if len(content) > 1 and ("|" in content[1] or "@" in content[1]) else None

    pdf.set_font(FONT, "B", 20 * k)
    pdf.set_text_color(*INK)
    pdf.cell(width, 9 * k, name, align="C", new_x="LMARGIN", new_y="NEXT")
    if contact:
        pdf.ln(0.5 * k)
        _centered_contact(pdf, contact, k)
    pdf.ln(1.5 * k)

    body_started = False
    skip = {0, 1} if contact else {0}
    seen = -1
    for line in lines:
        if not line.strip():
            continue
        seen += 1
        if seen in skip:
            continue
        stripped = line.strip()

        if is_heading(stripped):
            pdf.ln((2.6 if body_started else 1) * k)
            pdf.set_font(FONT, "B", 10.5 * k)
            pdf.set_text_color(*INK)
            pdf.cell(width, 5.6 * k, stripped.rstrip(":").upper(), new_x="LMARGIN", new_y="NEXT")
            y = pdf.get_y() + 0.4
            pdf.set_draw_color(*RULE)
            pdf.set_line_width(0.25)
            pdf.line(pdf.l_margin, y, pdf.l_margin + width, y)
            pdf.ln(1.6 * k)
            body_started = True
            continue

        bullet = BULLET_RE.match(line)
        if bullet:
            pdf.set_font(FONT, "", 9.6 * k)
            pdf.set_text_color(*INK)
            pdf.set_x(margin + 1.5)
            pdf.cell(3.5, 4.7 * k, "•")
            pdf.set_left_margin(margin + 5)
            _write_rich(pdf, line[bullet.end():].strip(), 4.7 * k, 9.6 * k)
            pdf.set_left_margin(margin)
            pdf.ln(0.5 * k)
            continue

        label = LABEL_RE.match(stripped)
        if label and len(label.group(1)) < 34:
            _write_rich(pdf, label.group(2), 4.9 * k, 9.6 * k, bold_prefix=f"{label.group(1)}: ")
            pdf.ln(0.4 * k)
            continue

        date = DATE_TAIL_RE.search(stripped)
        if date and len(stripped) - len(date.group(0)) > 3:
            left = stripped[: date.start()].rstrip(" ,|")
            pdf.set_font(FONT, "", 9.4 * k)
            date_w = pdf.get_string_width(date.group(1)) + 1
            pdf.set_font(FONT, "B", 10 * k)
            pdf.set_text_color(*INK)
            pdf.multi_cell(width - date_w - 2, 5.2 * k, left, new_x="RIGHT", new_y="TOP")
            y_after = pdf.get_y()
            pdf.set_font(FONT, "", 9.4 * k)
            pdf.set_text_color(*MUTED)
            pdf.set_xy(margin + width - date_w, y_after)
            pdf.cell(date_w, 5.2 * k, date.group(1), align="R", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*INK)
            pdf.ln(0.3 * k)
            continue

        # Entry titles (a project or role name on its own short line) read better bold.
        if len(stripped) <= 70 and not stripped.endswith(".") and body_started and not re.search(r"[.!?]\s", stripped):
            pdf.set_font(FONT, "B", 10 * k)
            pdf.set_text_color(*INK)
            pdf.multi_cell(width, 5.2 * k, stripped, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.3 * k)
            continue

        _write_rich(pdf, stripped, 4.9 * k, 9.6 * k)
        pdf.ln(0.5 * k)

    return pdf


def _centered_contact(pdf: FPDF, contact: str, k: float = 1.0) -> None:
    """Contact line centered, with each email/URL clickable. Items are packed into rows
    that fit the page width, so a long line wraps BETWEEN items, never inside a URL."""
    size = 9 * k
    sep = "  |  "
    parts = [p.strip() for p in contact.split("|") if p.strip()]
    pdf.set_font(FONT, "", size)
    rows: list[list[str]] = [[]]
    for part in parts:
        trial = sep.join(rows[-1] + [part])
        if rows[-1] and pdf.get_string_width(trial) > pdf.epw:
            rows.append([part])
        else:
            rows[-1].append(part)
    for row in rows:
        total = pdf.get_string_width(sep.join(row))
        pdf.set_x(pdf.l_margin + max(0, (pdf.epw - total) / 2))
        for i, part in enumerate(row):
            if i:
                pdf.set_text_color(*RULE)
                pdf.write(4.6 * k, sep)
            m = TOKEN_RE.fullmatch(part)
            href = _href(part, "email" if m and m.group("email") else "url") if m else None
            pdf.set_text_color(*(LINK if href else MUTED))
            pdf.write(4.6 * k, part, link=href or "")
        pdf.ln(4.6 * k)
    pdf.set_text_color(*INK)
