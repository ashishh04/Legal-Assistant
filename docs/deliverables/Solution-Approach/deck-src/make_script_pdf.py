"""Make the printable presenter script: one A4 page per slide, with the slide image, its timing and the talk track.

    python -I make_script_pdf.py <presenter-script.md> <slide_png_dir> <out.pdf>

<slide_png_dir> holds slide-01.png ... slide-23.png, written by export-slides.ps1 from the built deck.
Text is set in Arial from C:/Windows/Fonts so dashes and arrows render. Cue lines (Timing, Transition, Ask,
If asked) are set apart in colour, so the presenter reads only the plain text aloud.
"""
import html
import os
import re
import shutil
import sys
import tempfile

import pymupdf
from PIL import Image

SCRIPT, PNG_DIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
MAGENTA, DARK, BODY = "#D6297A", "#242831", "#30343C"
FONTS = {"arial.ttf": "", "arialbd.ttf": "font-weight: bold;", "ariali.ttf": "font-style: italic;"}


def read_script(path):
    """Return (intro paragraphs, [(number, title, [paragraphs])]). Paragraphs are blank-line separated."""
    intro, slides, buf = [], [], []

    def flush():
        if buf:
            (slides[-1][2] if slides else intro).append(" ".join(buf))
            buf.clear()

    for line in open(path, encoding="utf-8"):
        line = line.strip()
        heading = re.match(r"^## Slide (\d+):\s*(.+)$", line)
        if heading:
            flush()
            slides.append((int(heading.group(1)), heading.group(2), []))
        elif line.startswith("#") or not line:
            flush()
        else:
            buf.append(line)
    flush()
    return intro, slides


def para_html(text):
    text = html.escape(text).replace("`", "")
    for label in ("Timing:", "Transition:", "Ask:"):
        if text.startswith(label):
            cls = "timing" if label == "Timing:" else "cue"
            return f'<p class="{cls}"><b>{label}</b>{text[len(label):]}</p>'
    if text.startswith("If asked"):
        return f'<p class="cue">{text}</p>'
    if re.match(r"^\d+\. ", text):
        return f'<p class="step">{text}</p>'
    return f"<p>{text}</p>"


CSS = "".join(f"@font-face {{font-family: Arial; src: url({name}); {style}}}\n" for name, style in FONTS.items()) + f"""
body {{font-family: Arial; font-size: 11.5pt; line-height: 1.42; color: {BODY};}}
h1 {{font-size: 20pt; color: {DARK}; margin: 0 0 6pt 0;}}
h2 {{font-size: 14pt; color: {MAGENTA}; margin: 10pt 0 5pt 0;}}
p {{margin: 0 0 7pt 0;}}
p.timing {{color: #5F6673; font-size: 10pt; margin-bottom: 8pt;}}
p.cue {{color: {MAGENTA}; font-style: italic;}}
p.step {{margin: 0 0 4pt 0;}}
p.lead {{color: #5F6673;}}
p.toc {{margin: 0 0 2pt 0; font-size: 10.5pt;}}
img {{width: 100%;}}
"""

intro, slides = read_script(SCRIPT)
work = tempfile.mkdtemp()
try:
    for name in FONTS:
        shutil.copy(os.path.join("C:/Windows/Fonts", name), work)
    for number, _, _ in slides:  # JPEG keeps the PDF small; the slides are flat graphics
        Image.open(os.path.join(PNG_DIR, f"slide-{number:02d}.png")).convert("RGB").save(
            os.path.join(work, f"slide-{number:02d}.jpg"), quality=88)
    archive = pymupdf.Archive(work)
    page_rect = pymupdf.paper_rect("a4")
    frame = page_rect + (42, 44, -42, -50)
    raw = os.path.join(work, "raw.pdf")
    writer = pymupdf.DocumentWriter(raw)

    def place(markup):
        story = pymupdf.Story(html=markup, user_css=CSS, archive=archive)
        more = True
        while more:
            device = writer.begin_page(page_rect)
            more, _ = story.place(frame)
            story.draw(device)
            writer.end_page()

    total = 0.0
    for _, _, paras in slides:
        for p in paras:
            m = re.match(r"Timing: about ([\d.]+) (minute|second)", p)
            if m:
                total += float(m.group(1)) / (60 if m.group(2) == "second" else 1)
    cover = ("<h1>Ferrero Case Intelligence: Solution Approach</h1>"
             f"<p class='lead'>Presenter script for Ferrero-Solution-Approach.pptx: {len(slides)} slides, about "
             f"{round(total)} minutes including the live demo. The same words are in the deck's speaker notes, so "
             "PowerPoint's Presenter View shows them too.</p>"
             + "".join(f"<p>{html.escape(p)}</p>" for p in intro[1:]))
    contents = "".join(f"<p class='toc'>Slide {n}: {html.escape(t)}</p>" for n, t, _ in slides)
    place(cover + "<h2>Slides</h2>" + contents)
    for number, title, paras in slides:
        place(f'<img src="slide-{number:02d}.jpg"/>'
              f"<h2>Slide {number}: {html.escape(title)}</h2>" + "".join(para_html(p) for p in paras))
    writer.close()

    # Footer with the document name and page number; then merge the font copies each page carries and subset them.
    doc = pymupdf.open(raw)
    for i, page in enumerate(doc, start=1):
        page.insert_text((42, page.rect.height - 24), f"Ferrero Case Intelligence  |  Presenter script  |  {i}",
                         fontsize=8, color=(0.37, 0.4, 0.45))
    doc.subset_fonts()
    pages = doc.page_count
    doc.save(OUT, garbage=4, deflate=True, clean=True)
    doc.close()
finally:
    shutil.rmtree(work, ignore_errors=True)
print(f"pages: {pages}, {os.path.getsize(OUT) / 1e6:.1f} MB -> {OUT}")
