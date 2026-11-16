"""Build the Ferrero Case Intelligence solution-approach deck on the Intertec EPM template.

    python -I build_deck.py <template.pptx> <assets_dir> <screens_dir> <presenter-script.md> <out.pptx>

The template's masters, layouts, theme, logo and footer are kept; its slides are removed and new
slides are drawn with the template's own styling (Poppins headings, Arial body, the EF2737 -> 75309A
gradient, pink cards and magenta icon circles), the same way as the Amicorp solution-approach deck.
Each slide's speaker notes come from the "## Slide N" section of the presenter script.
"""
import os
import re
import sys
import uuid

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

TEMPLATE, ASSETS, SCREENS, SCRIPT, OUT = sys.argv[1:6]

# ---- template styling ----------------------------------------------------------------------
MAGENTA, PINK, PINK_LINE, PINK_EDGE = "D6297A", "FFF1F6", "F3C2D6", "FF65A0"
GREY_BG, DARK, BODY, SUB = "F4F5F7", "242831", "5F6673", "30343C"
RED, PURPLE, BORDER, WHITE = "EF2737", "75309A", "D9DCE3", "FFFFFF"
HEAD, TEXT = "Poppins", "Arial"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
GRAD_XML = (f'<a:gradFill xmlns:a="{A_NS}" rotWithShape="1"><a:gsLst>'
            f'<a:gs pos="0"><a:srgbClr val="{RED}"/></a:gs><a:gs pos="100000"><a:srgbClr val="{PURPLE}"/></a:gs>'
            '</a:gsLst><a:lin ang="20400000" scaled="0"/></a:gradFill>')
GRAD_TEXT_XML = (f'<a:gradFill xmlns:a="{A_NS}"><a:gsLst><a:gs pos="13000"><a:srgbClr val="EE2736"/></a:gs>'
                 '<a:gs pos="100000"><a:srgbClr val="7030A0"/></a:gs></a:gsLst><a:lin ang="4200000" scaled="0"/></a:gradFill>')

prs = Presentation(TEMPLATE)

# ---- remove the template's slides and sections ------------------------------------------------
sld_ids = prs.slides._sldIdLst
for sld in list(sld_ids):
    prs.part.drop_rel(sld.rId)
    sld_ids.remove(sld)
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
pres_el = prs.part._element
section_list = pres_el.find(".//{%s}sectionLst" % P14)
for child in list(section_list):
    section_list.remove(child)

LAYOUTS = {layout.name: layout for layout in prs.slide_masters[0].slide_layouts}
L_COVER, L_AGENDA = LAYOUTS["Cover Slide Option 1"], LAYOUTS["1_Agenda with Logo"]
L_CONTENT, L_SEPARATOR, L_THANKS = LAYOUTS["Custom Layout"], LAYOUTS["Separator 1"], LAYOUTS["Thank You UAE"]
SECTIONS = []  # (name, [slide ids])


def start_section(name):
    SECTIONS.append((name, []))


def new_slide(layout):
    slide = prs.slides.add_slide(layout)
    SECTIONS[-1][1].append(slide.slide_id)
    return slide


# ---- drawing helpers (as in the Amicorp deck) ---------------------------------------------------
def rgb(hex_):
    return RGBColor.from_string(hex_)


def no_shadow(shape):
    shape.shadow.inherit = False


def set_gradient(shape):
    sp_pr = shape._element.spPr
    for child in list(sp_pr):
        if child.tag in (qn("a:solidFill"), qn("a:noFill"), qn("a:gradFill"), qn("a:pattFill"), qn("a:blipFill")):
            sp_pr.remove(child)
    sp_pr.find(qn("a:prstGeom")).addnext(etree.fromstring(GRAD_XML))


def box(slide, x, y, w, h, fill=None, line=None, line_w=0.75, shape=MSO_SHAPE.RECTANGLE, name="Shape",
        grad=False, dash=False):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.name = name
    if grad:
        set_gradient(s)
    elif fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(line_w)
        if dash:
            s.line.dash_style = 4  # dash
    else:
        s.line.fill.background()
    no_shadow(s)
    return s


def fill_frame(tf, content, size, bold, color, font, align, italic=False, space_after=0, line_spacing=None):
    paras = content if isinstance(content, list) else [content]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if space_after:
            p.space_after = Pt(space_after)
        if line_spacing:
            p.line_spacing = line_spacing
        runs = para if isinstance(para, list) else [para]
        for r in runs:
            if isinstance(r, str):
                r = {"text": r}
            run = p.add_run()
            run.text = r["text"]
            f = run.font
            f.size = Pt(r.get("size", size))
            f.bold = r.get("bold", bold)
            f.italic = r.get("italic", italic)
            f.name = r.get("font", font)
            f.color.rgb = rgb(r.get("color", color))


def text(slide, x, y, w, h, content, size=11, bold=False, color=BODY, font=TEXT, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False, name="Text", space_after=0, margin=None, line_spacing=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    if margin is not None:
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(margin)
    fill_frame(tf, content, size, bold, color, font, align, italic, space_after, line_spacing)
    return tb


def shape_text(shape, content, size=11, bold=True, color=WHITE, font=HEAD, align=PP_ALIGN.CENTER,
               anchor=MSO_ANCHOR.MIDDLE, margin=0.06):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    fill_frame(tf, content, size, bold, color, font, align)
    return shape


def icon(slide, x, y, d, name, fill=MAGENTA, scale=0.56, alt=""):
    box(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL, name=f"Icon circle {name}")
    sz = d * scale
    pic = slide.shapes.add_picture(os.path.join(ASSETS, name), Inches(x + (d - sz) / 2),
                                   Inches(y + (d - sz) / 2), Inches(sz), Inches(sz))
    pic.name = f"Icon {name[:-4]}"
    pic._element.nvPicPr.cNvPr.set("descr", alt or name[:-4].split("_")[0] + " icon")
    return pic


def arrow(slide, x, y, w=0.45, h=0.34, direction="right"):
    shape = MSO_SHAPE.RIGHT_ARROW if direction == "right" else MSO_SHAPE.DOWN_ARROW
    return box(slide, x, y, w, h, fill=MAGENTA, shape=shape, name="Arrow")


def pill(slide, x, y, w, h, label, size=10):
    s = box(slide, x, y, w, h, line=MAGENTA, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=f"Pill {label}")
    s.adjustments[0] = 0.5
    shape_text(s, label, size=size, color=MAGENTA)
    return s


def banner(slide, y, label, h=0.55, size=12):
    s = box(slide, 0.6, y, 12.13, h, grad=True, name="Banner")
    shape_text(s, label, size=size, bold=True, color=WHITE, font=HEAD)
    return s


def content(title, subtitle):
    slide = new_slide(L_CONTENT)
    slide.shapes.title.text = title
    text(slide, 0.6, 1.08, 11.0, 0.4, subtitle, size=14, bold=True, color=SUB, name="Subtitle")
    return slide


def label(slide, x, y, w, words, color=BODY):
    return text(slide, x, y, w, 0.3, words, size=11, bold=True, color=color, font=HEAD, name="Label")


def remove_placeholder(slide, idx):
    for ph in slide.placeholders:
        if ph.placeholder_format.idx == idx:
            ph._element.getparent().remove(ph._element)
            return


def screen(slide, x, y, w, name, alt):
    """A live app screenshot at width w, keeping its aspect ratio, framed with a hairline border."""
    pic = slide.shapes.add_picture(os.path.join(SCREENS, name), Inches(x), Inches(y), width=Inches(w))
    pic.name = f"Screen {name[:-4]}"
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    pic.line.color.rgb = rgb(BORDER)
    pic.line.width = Pt(0.75)
    return y + pic.height / 914400  # bottom edge, in inches, for the caption underneath


def caption(slide, x, y, w, words, align=PP_ALIGN.LEFT):
    return text(slide, x, y, w, 0.3, words, size=10.5, italic=True, align=align, margin=0, name="Caption")


def badge(slide, x, y, w, h, words, size=9.5, solid=True):
    b = box(slide, x, y, w, h, fill=MAGENTA if solid else None, line=None if solid else MAGENTA,
            shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=f"Badge {words}")
    b.adjustments[0] = 0.5
    shape_text(b, words, size=size, color=WHITE if solid else MAGENTA, margin=0.04)
    return b


def flow(slide, steps, top=2.08, desc_h=1.05, pill_w=None, desc_size=11):
    """Icons on a line with a number, title, description and a pill per step (Amicorp 'life of a card')."""
    n = len(steps)
    pitch = 12.13 / n
    centres = [0.6 + pitch / 2 + i * pitch for i in range(n)]
    tw = min(2.2, pitch - 0.12)
    box(slide, centres[0], top + 0.4, centres[-1] - centres[0], 0.04, fill=PINK_LINE, name="Flow line")
    for i, ((ic, head, desc, who), cx) in enumerate(zip(steps, centres)):
        icon(slide, cx - 0.42, top, 0.84, ic, scale=0.56)
        text(slide, cx - tw / 2, top + 1.07, tw, 0.25, f"{i + 1:02d}", size=11, bold=True, color=MAGENTA, font=HEAD,
             align=PP_ALIGN.CENTER, name="Step number")
        text(slide, cx - tw / 2, top + 1.34, tw, 0.35, head, size=15, bold=True, color=DARK, font=HEAD,
             align=PP_ALIGN.CENTER, name="Step title")
        text(slide, cx - tw / 2 + 0.03, top + 1.78, tw - 0.06, desc_h, desc, size=desc_size, align=PP_ALIGN.CENTER,
             name="Step text")
        pw = pill_w or min(1.9, pitch - 0.3)
        pill(slide, cx - pw / 2, top + 2.92, pw, 0.36, who, size=9.5)
    return centres


# ===============================================================================================
# 1 Cover
start_section("Opening")
s = new_slide(L_COVER)
ph = {p.placeholder_format.idx: p for p in s.placeholders}
ph[0].text = "Ferrero Case Intelligence"
ph[10].text = "Legal case dashboards and a bilingual assistant for English and Arabic case files"
ph[10].left, ph[10].top, ph[10].width, ph[10].height = Inches(0.9), Inches(4.5), Inches(5.6), Inches(0.95)
ph[12].left, ph[12].top, ph[12].width, ph[12].height = Inches(0.9), Inches(5.56), Inches(5.79), Inches(0.36)
ph[12].text_frame.text = "Solution Approach  |  November 2026"
for r in ph[12].text_frame.paragraphs[0].runs:
    r.font.size = Pt(14)
    r.font.color.rgb = rgb(WHITE)
box(s, 6.75, 1.75, 5.9, 3.69, fill=WHITE, line=BORDER, name="Cover card")
text(s, 7.0, 1.92, 5.4, 0.3, "THE LIFE OF EVERY QUESTION", size=10, bold=True, color=BODY, font=HEAD,
     name="Cover label")
steps = [("chat_w.png", "Ask", "English or Arabic"), ("route_w.png", "Route", "Files or data"),
         ("lock_w.png", "Filter", "Your access"), ("spark_w.png", "Answer", "Claude"),
         ("quote_w.png", "Cite", "The paragraph")]
centres = [7.45 + i * 1.125 for i in range(5)]
box(s, centres[0], 2.6, centres[-1] - centres[0], 0.035, fill=PINK_LINE, name="Cover line")
for (ic, name, who), cx in zip(steps, centres):
    icon(s, cx - 0.3, 2.32, 0.6, ic)
    text(s, cx - 0.56, 3.0, 1.12, 0.28, name, size=11, bold=True, color=DARK, font=HEAD, align=PP_ALIGN.CENTER,
         margin=0, name=f"Cover step {name}")
    text(s, cx - 0.56, 3.27, 1.12, 0.25, who, size=9, bold=True, color=MAGENTA, font=HEAD, align=PP_ALIGN.CENTER,
         margin=0, name=f"Cover role {name}")
for i, (num, lab) in enumerate([("4", "dashboards"), ("2", "languages"), ("6", "access roles")]):
    x = 7.0 + i * 1.82
    text(s, x, 3.68, 1.75, 0.55, [[{"text": num, "size": 22, "bold": True, "color": MAGENTA, "font": HEAD},
                                   {"text": "  " + lab, "size": 10, "bold": True, "color": BODY, "font": HEAD}]],
         anchor=MSO_ANCHOR.MIDDLE, margin=0, name=f"Cover stat {num}")
tag = box(s, 7.0, 4.47, 5.4, 0.62, grad=True, name="Cover tagline")
shape_text(tag, "Every case in view.  Every answer cited.", size=13)

# 2 Agenda
s = new_slide(L_AGENDA)
remove_placeholder(s, 34)
agenda = ["The Problem We Solve", "What We Are Building", "The Approach on One Page", "Six Design Principles",
          "How It Works", "The Product, Screen by Screen", "Security, Access and Quality",
          "From Demo to Production", "The Plan and What We Need", "Where We Are, and a Live Demo"]
for i, item in enumerate(agenda):
    y = 0.69 + i * 0.56
    num = text(s, 3.95, y, 0.81, 0.5, str(i + 1), size=18, bold=True, font=HEAD, align=PP_ALIGN.CENTER,
               name=f"Agenda number {i + 1}")
    run = num.text_frame.paragraphs[0].runs[0]
    r_pr = run._r.get_or_add_rPr()
    for el in r_pr.findall(qn("a:solidFill")):
        r_pr.remove(el)
    r_pr.find(qn("a:latin")).addprevious(etree.fromstring(GRAD_TEXT_XML))
    item_box = text(s, 4.86, y, 8.04, 0.5, item, size=18, bold=True, font=HEAD, name=f"Agenda item {i + 1}")
    item_box.text_frame.paragraphs[0].runs[0].font.color.theme_color = MSO_THEME_COLOR.TEXT_2

# ===============================================================================================
# 3 How case work flows today
start_section("The problem")
s = content("How Case Work Flows Today",
            "Five stages and many sources of truth; the full picture is rebuilt by hand at every step")
flow(s, [("flag_w.png", "Detect",
          "Reports arrive by mailbox, intake form, app-store monitoring, vendors, distributors and customs",
          "Six channels to watch"),
         ("list_w.png", "Triage", "Legal operations sorts each report and decides which ones become cases",
          "SLA not visible"),
         ("gavel_w.png", "Enforce",
          "Counsel and external firms pursue notices, claims and takedowns in nine countries",
          "Nine sets of deadlines"),
         ("folder_w.png", "File", "Judgments, letters and agreements sit in SharePoint folders, in English and Arabic",
          "Read file by file"),
         ("dash_w.png", "Report", "Status lives in per-country Excel trackers, rolled up by hand for leadership",
          "Rebuilt by hand")])
banner(s, 5.72, "No single view of a case: the facts sit in trackers, inboxes and folders, and every answer means "
                "opening them", size=11.5)

# 4 Six challenges
s = content("Case Insight Depends on Manual Work",
            "Six challenges to solve, starting with one consolidated view of every case")
challenges = [
    ("MdInsights_p.png", "No consolidated case view",
     "Trackers, the infringement mailbox, intake forms and app-store reports sit apart; legal, leadership and "
     "procurement have no shared dashboard"),
    ("MdManageSearch_p.png", "Answers found by hand",
     "A question such as “what was awarded in case X?” means opening files one by one, at a real cost "
     "in lawyer time"),
    ("MdReportProblem_p.png", "Risk of wrong answers",
     "Reading many documents by hand invites slips, and a generic chatbot guesses with confidence"),
    ("MdFactCheck_p.png", "Answers must be verifiable",
     "A legal answer is only usable with the document and the paragraph behind it"),
    ("MdLock_p.png", "Confidential legal material",
     "Files must never reach anyone not cleared to read them; each country team sees only its own cases"),
    ("MdTranslate_p.png", "Two languages, scanned files",
     "Files in English and Arabic, party names in both scripts, and scans with no text layer"),
]
for i, (ic, head, desc) in enumerate(challenges):
    x = 0.6 + (i % 3) * 4.145
    y = 1.72 + (i // 3) * 2.08
    box(s, x, y, 3.84, 1.9, fill=GREY_BG, name=f"Challenge {i + 1}")
    icon(s, x + 0.25, y + 0.25, 0.6, ic, fill=PINK, scale=0.567)
    text(s, x + 1.0, y + 0.22, 2.7, 0.7, head, size=13, bold=True, color=DARK, font=HEAD,
         anchor=MSO_ANCHOR.MIDDLE, name="Challenge title")
    text(s, x + 0.25, y + 1.0, 3.4, 0.85, desc, size=11, name="Challenge text")
banner(s, 5.98, "Needed: one view of every case for every audience, and an assistant that answers only from your "
                "files, with sources", size=11.5)

# 5 Four audiences
s = content("Four Audiences, Four Questions",
            "What each group needs to know quickly today, and the dashboard that answers it")
audiences = [
    ("Legal team", "gavel_w.png", "IP counsel, litigation counsel and paralegals",
     "“What needs my attention this week, and where does every case stand?”", "D1 · Case Overview"),
    ("Leadership", "MdTrendingUp_w.png", "Head of Legal, Regional General Counsel and Procurement",
     "“Is enforcement paying for itself, and where are we exposed?”", "D2 · Leadership View"),
    ("Legal operations", "mail_w.png", "Legal operations and brand protection",
     "“Are we keeping up with incoming reports, and which channels become real cases?”",
     "D3 · Intake and Triage"),
    ("Enforcement", "flag_w.png", "IP counsel, brand protection and external counsel reviews",
     "“Which infringers and routes deserve the next budget?”", "D4 · Enforcement Outcomes"),
]
for i, (head, ic, who, quote, dash) in enumerate(audiences):
    x = 0.6 + i * 3.08
    hdr = box(s, x, 1.72, 2.89, 0.48, grad=True, name=f"Audience header {head}")
    shape_text(hdr, head, size=12)
    box(s, x, 2.2, 2.89, 3.25, fill=WHITE, line=PINK_EDGE, name=f"Audience body {head}")
    icon(s, x + 0.2, 2.42, 0.55, ic, scale=0.56)
    text(s, x + 0.88, 2.36, 1.92, 0.68, who, size=10.5, color=BODY, anchor=MSO_ANCHOR.MIDDLE, name="Audience who")
    text(s, x + 0.15, 3.16, 2.62, 1.6, quote, size=15, italic=True, color=DARK, name="Audience question")
    pill(s, x + 0.2, 4.84, 2.49, 0.36, dash, size=9.5)
banner(s, 5.72, "And everyone asks “what does the file actually say?” — Ferrero answers from the "
                "documents, citing the paragraph", size=11.5)

# ===============================================================================================
# 6 What we are building
start_section("The solution")
s = content("Two Capabilities on One Case Model",
            "Dashboards show every case, the assistant answers from the files, and access rules run through both")
stats = [("4", "Dashboards", "One per audience: legal, leadership, legal ops and enforcement"),
         ("EN | AR", "Two Languages", "Questions, case files and answers in English and Arabic"),
         ("6", "Access Roles", "Country teams, Legal Ops, Leadership and Procurement, from Entra ID groups"),
         ("1", "Case Model", "Trackers, mailbox, intake, app stores and invoices, in one place")]
for i, (num, lab, desc) in enumerate(stats):
    x = 0.6 + i * 3.0875
    box(s, x, 1.72, 2.8675, 1.85, fill=PINK, name=f"Stat card {lab}")
    text(s, x + 0.25, 1.86, 2.5, 0.7, num, size=30, bold=True, color=MAGENTA, font=HEAD, name="Stat value")
    text(s, x + 0.25, 2.6, 2.5, 0.32, lab, size=13, bold=True, color=DARK, font=HEAD, name="Stat label")
    text(s, x + 0.25, 2.93, 2.48, 0.62, desc, size=11, name="Stat text")
pillars = [("It Consolidates", "MdAccountTree_w.png",
            "Trackers, mailbox, intake, app-store and spend data become one case model, shown in four dashboards"),
           ("It Answers", "spark_w.png",
            "Questions in English or Arabic answered from the case files and the tracker, each document claim cited"),
           ("It Protects", "shield_w.png",
            "Each person sees only the cases their role allows, in every chart, list, document and answer")]
for i, (head, ic, desc) in enumerate(pillars):
    x = 0.6 + i * 4.11
    hdr = box(s, x, 3.85, 3.91, 0.48, grad=True, name=f"Pillar header {head}")
    shape_text(hdr, head, size=12)
    box(s, x, 4.33, 3.91, 1.45, fill=WHITE, line=PINK_EDGE, name=f"Pillar body {head}")
    icon(s, x + 0.25, 4.73, 0.65, ic, scale=0.554)
    text(s, x + 1.12, 4.33, 2.69, 1.45, desc, size=12, color=SUB, anchor=MSO_ANCHOR.MIDDLE, name="Pillar text")
caption(s, 0.6, 6.05, 12.1, "The dashboards, the case pages and the assistant share one set of data and one set of "
                            "access rules, so the numbers always agree.")

# 7 How each challenge is resolved
s = content("How Each Challenge Is Resolved",
            "From scattered trackers and manual search to dashboards and cited answers, inside each reader’s access")
label(s, 0.6, 1.62, 5.4, "THE CHALLENGE")
label(s, 6.95, 1.62, 5.8, "HOW IT IS RESOLVED", color=MAGENTA)
resolved = [
    ("MdInsights_p.png", "No consolidated case view", "Trackers, mailbox, intake and app reports sit apart",
     "MdTrendingUp_w.png", "One case model, four dashboards", "KPIs, drill-throughs and a page for every case"),
    ("MdManageSearch_p.png", "Answers found by hand", "Files opened one by one, at real cost in lawyer time",
     "chat_w.png", "Ask in plain language", "Answers from every file you may open, in seconds"),
    ("MdReportProblem_p.png", "Risk of wrong answers", "Manual slips, and generic AI that guesses with confidence",
     "block_w.png", "Answers only from the evidence", "When the files are silent, Ferrero says so instead of guessing"),
    ("MdFactCheck_p.png", "Answers must be verifiable", "A legal answer needs the document behind it",
     "quote_w.png", "Every document claim cited", "Each claim links to its paragraph and SharePoint path"),
    ("MdLock_p.png", "Confidential legal material", "Files must never reach anyone not cleared to read them",
     "lock_w.png", "Access enforced in the data", "A case you may not open is treated as if it does not exist"),
    ("MdTranslate_p.png", "Two languages, scanned files", "English and Arabic files, names in both scripts, scans",
     "translate_w.png", "English and Arabic as equals", "Arabic normalised for search; every scan listed for OCR"),
]
for i, (ic_l, t_l, d_l, ic_r, t_r, d_r) in enumerate(resolved):
    y = 1.98 + i * 0.74
    box(s, 0.6, y, 5.6, 0.64, fill=GREY_BG, name=f"Challenge row {i + 1}")
    icon(s, 0.74, y + 0.1, 0.44, ic_l, fill=PINK, scale=0.6)
    text(s, 1.3, y + 0.03, 4.8, 0.3, t_l, size=12, bold=True, color=DARK, font=HEAD, name="Row title")
    text(s, 1.3, y + 0.31, 4.85, 0.3, d_l, size=10.5, name="Row text")
    arrow(s, 6.36, y + 0.17, w=0.42, h=0.3)
    box(s, 6.95, y, 5.78, 0.64, fill=PINK, line=PINK_LINE, name=f"Resolution row {i + 1}")
    icon(s, 7.09, y + 0.1, 0.44, ic_r, scale=0.6)
    text(s, 7.65, y + 0.03, 4.98, 0.3, t_r, size=12, bold=True, color=DARK, font=HEAD, name="Row title")
    text(s, 7.65, y + 0.31, 5.0, 0.3, d_r, size=10.5, name="Row text")

# 8 The approach on one page
s = content("The Approach on One Page",
            "One case model and one document index, both filtered by the reader’s access, behind every screen")
label(s, 0.6, 1.62, 2.5, "SOURCES")
label(s, 3.5, 1.62, 3.7, "ONE MODEL, ONE INDEX")
label(s, 7.65, 1.62, 3.2, "WHAT PEOPLE USE")
LANE1, LANE2, LH = 1.98, 4.13, 1.65  # top of each lane and its height; the gap holds the cross-links
sources = [(LANE1, "Case data", ["Per-country Excel trackers", "Mailbox and intake forms", "App-store monitoring",
                                 "External counsel invoices"]),
           (LANE2, "Case libraries", ["SharePoint folder per case", "Judgments, claims, notices",
                                      "English and Arabic files"])]
for y, head, lines in sources:
    box(s, 0.6, y, 2.45, LH, fill=GREY_BG, name=f"Source {head}")
    text(s, 0.72, y + 0.08, 2.25, 0.3, head, size=12, bold=True, color=DARK, font=HEAD, name="Source title")
    for j, line in enumerate(lines):
        ly = y + 0.47 + j * 0.28
        box(s, 0.78, ly + 0.105, 0.07, 0.07, fill=MAGENTA, shape=MSO_SHAPE.OVAL, name="Marker")
        text(s, 0.93, ly, 2.08, 0.28, line, size=10, anchor=MSO_ANCHOR.MIDDLE, margin=0, name="Source line")
engine = [(LANE1, "db_w.png", "Case model", WHITE, PINK_EDGE,
           "Cases, events, intake, app-store detections and invoices in one set of tables. Each person gets a "
           "read-only copy holding only the rows they may see."),
          (LANE2, "folder_w.png", "Document sync", PINK, PINK_LINE,
           "Each file tied to its case, split into sections and indexed with that case’s access group. Every "
           "file gets a status and a reason.")]
for y, ic, head, fill, line, desc in engine:
    box(s, 3.5, y, 3.7, LH, fill=fill, line=line, name=f"Engine {head}")
    icon(s, 3.68, y + 0.16, 0.52, ic, scale=0.56)
    text(s, 4.32, y + 0.18, 2.8, 0.45, head, size=13, bold=True, color=DARK, font=HEAD, anchor=MSO_ANCHOR.MIDDLE,
         name="Engine title")
    text(s, 3.66, y + 0.76, 3.45, 0.86, desc, size=10.5, name="Engine text")
outputs = [(LANE1, "dash_w.png", "Dashboards and case pages",
            "D1–D4 in Superset, the Overview and a page for every case"),
           (LANE2, "spark_w.png", "Ferrero assistant",
            "Routes each question to the documents, the case data or both, and cites every document claim")]
for y, ic, head, desc in outputs:
    box(s, 7.65, y, 3.15, LH, fill=WHITE, line=PINK_EDGE, name=f"Output {head}")
    icon(s, 7.82, y + 0.16, 0.52, ic, scale=0.56)
    text(s, 8.44, y + 0.15, 2.3, 0.52, head, size=12, bold=True, color=DARK, font=HEAD, anchor=MSO_ANCHOR.MIDDLE,
         name="Output title")
    text(s, 7.8, y + 0.76, 2.92, 0.86, desc, size=10.5, name="Output text")
people = box(s, 11.25, LANE1, 1.48, LANE2 + LH - LANE1, grad=True, name="People")
shape_text(people, [[{"text": "People", "size": 13}],
                    [{"text": "Legal, leadership, legal ops and procurement, each seeing only what their role "
                              "allows", "size": 10, "bold": False, "font": TEXT}]], margin=0.1)
for y in (LANE1, LANE2):
    for x in (3.11, 7.26, 10.86):
        arrow(s, x, y + LH / 2 - 0.13, w=0.32, h=0.26)
# cross-links between the lanes
for x, words, w in [(3.9, "Each file inherits its case’s access", 3.1),
                    (8.05, "“Ask Ferrero” opens the case", 2.7)]:
    arrow(s, x, LANE1 + LH + 0.08, w=0.24, h=0.34, direction="down")
    text(s, x + 0.34, LANE1 + LH + 0.06, w, 0.38, words, size=10, bold=True, color=MAGENTA, font=HEAD,
         anchor=MSO_ANCHOR.MIDDLE, margin=0, name="Cross-link label")
banner(s, 6.05, "Access is decided by the case and enforced in the data layer, never by the prompt", size=11.5)

# 9 Six principles
s = content("Six Principles Behind the Design",
            "Each one removes a specific risk; together they make every answer defensible to a lawyer")
principles = [
    ("quote_w.png", "Answers come from evidence",
     "Document claims cite their paragraph; when the files are silent, Ferrero says so instead of guessing"),
    ("lock_w.png", "Access decided by the case",
     "Enforced in the data and in every tool, never by the prompt; a hidden case looks exactly like a missing one"),
    ("MdAccountTree_w.png", "One set of numbers everywhere",
     "Dashboards, case pages and the assistant read the same data with the same definitions"),
    ("tag_w.png", "Files tied to cases, not names",
     "Manifest or catalogue first; a case number in a file name must agree with the file’s own text"),
    ("translate_w.png", "English and Arabic as equals",
     "One normaliser for documents and questions; answers come back in the language of the question"),
    ("grade_w.png", "Measured and honest about gaps",
     "A golden set checks every change; skipped files and conflicting sources are reported, never hidden"),
]
for i, (ic, head, desc) in enumerate(principles):
    x = 0.6 + (i % 3) * 4.145
    y = 1.72 + (i // 3) * 2.42
    box(s, x, y, 3.84, 2.2, fill=PINK, line=PINK_LINE, name=f"Principle {i + 1}")
    icon(s, x + 0.25, y + 0.25, 0.6, ic, scale=0.567)
    text(s, x + 2.7, y + 0.2, 0.95, 0.5, f"{i + 1:02d}", size=20, bold=True, color=PINK_LINE, font=HEAD,
         align=PP_ALIGN.RIGHT, name="Principle number")
    text(s, x + 0.25, y + 0.98, 3.4, 0.45, head, size=13, bold=True, color=DARK, font=HEAD, name="Principle title")
    text(s, x + 0.25, y + 1.42, 3.4, 0.74, desc, size=11, name="Principle text")

# ===============================================================================================
# 10 The life of a question
start_section("How it works")
s = content("The Life of a Question",
            "Six steps from question to answer; the model writes only from what the reader may see")
flow(s, [("chat_w.png", "Ask", "In English or Arabic, from the assistant or from any case page", "Any page"),
         ("route_w.png", "Route", "Ferrero decides whether the answer is in the documents, the case data or both",
          "Claude"),
         ("search_w.png", "Search", "Case files searched, but only within the reader’s access groups",
          "Document index"),
         ("db_w.png", "Query", "Counts, deadlines and amounts read from the reader’s own copy of the case data",
          "Case model"),
         ("spark_w.png", "Answer", "Written only from the passages and rows returned, in the question’s language",
          "Claude"),
         ("quote_w.png", "Cite", "Each document claim linked to its paragraph, file and SharePoint path",
          "Sources panel")],
     desc_size=10.5, pill_w=1.62)
banner(s, 5.72, "A case the reader may not open is reported exactly like one that does not exist, in every tool and "
                "every answer", size=11.5)
caption(s, 0.6, 6.4, 12.1, "Claude Sonnet 5 on Amazon Bedrock in the demo; the same code also runs on Microsoft Foundry "
                           "or the Claude API.")

# 11 Four dashboards
s = content("Four Dashboards, One Set of Numbers",
            "Each audience gets its own view in Apache Superset, built on the same case model as Ferrero")
dashboards = [("D1", "Legal Case Overview", "IP counsel, litigation counsel, paralegals",
               "Open and new cases, hearings in 30 days, overdue actions, ageing, caseload by counsel"),
              ("D2", "Leadership Command View", "Head of Legal, Regional GC, Procurement",
               "Claimed, awarded and recovered, recovery and win rates, legal spend, exceptions"),
              ("D3", "Intake and Triage", "Legal operations, brand protection",
               "Reports by channel, triage SLA, backlog, conversion to case, app takedowns"),
              ("D4", "Infringers and Outcomes", "IP counsel, external counsel reviews",
               "Repeat infringers, takedown success, days to resolution, recovered per case")]
for i, (code, head, who, kpis) in enumerate(dashboards):
    y = 1.72 + i * 1.17
    tile = box(s, 0.6, y, 0.78, 1.05, grad=True, name=f"{code} tile")
    shape_text(tile, code, size=16)
    box(s, 1.38, y, 4.97, 1.05, fill=PINK, line=PINK_LINE, name=f"{code} body")
    text(s, 1.5, y + 0.04, 4.8, 0.3, head, size=12.5, bold=True, color=DARK, font=HEAD, name=f"{code} title")
    text(s, 1.5, y + 0.33, 4.8, 0.26, who, size=10, bold=True, color=MAGENTA, font=HEAD, name=f"{code} audience")
    text(s, 1.5, y + 0.58, 4.8, 0.45, kpis, size=10.5, name=f"{code} KPIs")
bottom = screen(s, 6.65, 1.72, 6.08, "dashboard.jpg",
                "Superset dashboard D1 Legal Case Overview embedded in Ferrero's Dashboards page, with KPI tiles and charts")
caption(s, 6.65, bottom + 0.08, 6.08, "D1 running inside Ferrero, for the signed-in person (synthetic data)")
note = box(s, 6.65, 5.86, 6.08, 0.42, fill=GREY_BG, name="Drill-through note")
shape_text(note, [[{"text": "Case drill-through: ", "bold": True, "color": MAGENTA, "font": HEAD},
                   {"text": "DS-1 Case Detail, opened from any case page", "bold": False, "color": SUB,
                    "font": TEXT}]], size=10.5, align=PP_ALIGN.LEFT, margin=0.15)

# 12 One page for every case
s = content("One Page for Every Case",
            "Facts, amounts, timeline, documents and spend in one place, with Ferrero one click away")
screen(s, 0.6, 1.72, 7.6, "case.jpg",
       "Case page for TM-2024-428 with facts, amounts, timeline and documents, and an Ask Ferrero button")
caption(s, 0.6, 6.12, 7.6, "Live screen from the Ferrero environment (synthetic case data)")
features = [("folder_w.png", "Everything about the case",
             "Parties, court, counsel and amounts in local currency and AED"),
            ("timeline_w.png", "What happened, what is next",
             "Timeline of events, next action, due date and overdue flags"),
            ("docshield_w.png", "Documents and their status",
             "Each file shows whether Ferrero can search it, and if not, why"),
            ("spark_w.png", "Ask Ferrero about this case",
             "Opens the assistant with the case in focus; dashboards link straight to this page")]
for i, (ic, head, desc) in enumerate(features):
    y = 1.8 + i * 1.1
    icon(s, 8.55, y + 0.02, 0.56, ic, scale=0.56)
    text(s, 9.3, y - 0.04, 3.45, 0.32, head, size=12.5, bold=True, color=DARK, font=HEAD, name="Feature title")
    text(s, 9.3, y + 0.28, 3.45, 0.62, desc, size=10.5, name="Feature text")

# 13 Every answer cited, or refused
s = content("Every Answer Cited, or Refused",
            "Each claim from a document carries its source; when a case is out of reach, Ferrero says so")
bottom = screen(s, 0.6, 1.72, 5.6, "answer-cited.jpg",
                "Ferrero answers what was awarded in TM-2024-428, with numbered citations and the source passage")
caption(s, 0.6, bottom + 0.08, 5.6, "Live answers from the Ferrero environment (synthetic case files)")
bottom = screen(s, 6.5, 1.72, 6.23, "answer-access.jpg",
                "A Legal-KSA user asks about a UAE case; Ferrero says it is not in the files available to them")
caption(s, 6.5, bottom + 0.08, 6.23, "Asked by a Legal-KSA user about a UAE case")
cited = [("quote_w.png", "Citations you can check",
          "Each [n] opens the quoted paragraph, with file, section and SharePoint path"),
         ("lock_w.png", "Access respected in every answer",
          "Out-of-scope cases get no figures and no hint that they exist"),
         ("merge_w.png", "Sources that disagree are named",
          "If a document and the tracker differ, Ferrero gives both and names each")]
for i, (ic, head, desc) in enumerate(cited):
    y = 3.72 + i * 0.86
    box(s, 6.5, y, 6.23, 0.76, fill=PINK, line=PINK_LINE, name=f"Cited card {head}")
    icon(s, 6.64, y + 0.15, 0.46, ic, scale=0.58)
    text(s, 7.25, y + 0.04, 5.4, 0.3, head, size=12, bold=True, color=DARK, font=HEAD, name="Cited title")
    text(s, 7.25, y + 0.36, 5.4, 0.36, desc, size=10.5, name="Cited text")

# 14 Arabic
s = content("Arabic Case Files, Answered in Arabic",
            "Ask in Arabic and the answer comes back right to left, cited the same way as in English")
bottom = screen(s, 0.6, 1.72, 5.6, "answer-arabic.jpg",
                "An Arabic question about the settlement in TM-2024-421 answered in Arabic with numbered citations")
caption(s, 0.6, bottom + 0.08, 5.6, "Live answer from the Ferrero environment (synthetic case files)")
arabic = [("translate_w.png", "Ask in either language",
           "Answers come back in the language of the question, whatever the language of the file"),
          ("abc_w.png", "One Arabic normaliser",
           "Diacritics, tatweel, letter variants and Arabic-Indic digits unified for files and questions"),
          ("person_w.png", "Names in both scripts",
           "A mark or party named in Arabic or in English still ties a file to its case"),
          ("grade_w.png", "Arabic PDFs checked",
           "Shaped-glyph text layers repaired and flagged, so dates and amounts get a second look")]
for i, (ic, head, desc) in enumerate(arabic):
    y = 1.82 + i * 0.86
    icon(s, 6.6, y + 0.02, 0.54, ic, scale=0.56)
    text(s, 7.33, y - 0.04, 5.4, 0.32, head, size=12.5, bold=True, color=DARK, font=HEAD, name="Arabic title")
    text(s, 7.33, y + 0.27, 5.4, 0.5, desc, size=10.5, name="Arabic text")
box(s, 6.6, 5.36, 6.13, 0.8, fill=GREY_BG, name="Arabic stat")
text(s, 6.75, 5.4, 1.9, 0.72, "251 of 508", size=20, bold=True, color=MAGENTA, font=HEAD, anchor=MSO_ANCHOR.MIDDLE,
     name="Arabic stat value")
text(s, 8.6, 5.4, 4.05, 0.72, "case files in the demo corpus are Arabic; search, answers and citations work the "
     "same in both languages", size=10.5, anchor=MSO_ANCHOR.MIDDLE, name="Arabic stat text")

# 15 Every file accounted for
s = content("Every File Accounted For",
            "Each document is tied to its case and indexed with that case’s access, or listed with the reason why not")
sync = [("Collect", "SharePoint through the Graph delta API, or a folder with a manifest; unchanged files skipped"),
        ("Match to case", "Manifest or catalogue first; a case number in a name or text must be confirmed by the "
                          "mark or infringer"),
        ("Extract", "Text from DOCX and PDF, Arabic normalised; scans queued for OCR"),
        ("Index", "Sections become passages tagged with the case’s access group"),
        ("Report", "Each file is reported as indexed, flagged, skipped or pending, with a reason")]
for i, (head, desc) in enumerate(sync):
    y = 1.78 + i * 0.88
    c = box(s, 0.6, y, 0.5, 0.5, fill=MAGENTA, shape=MSO_SHAPE.OVAL, name=f"Sync step {i + 1}")
    shape_text(c, f"{i + 1:02d}", size=11, margin=0)
    text(s, 1.25, y - 0.04, 4.95, 0.3, head, size=12.5, bold=True, color=DARK, font=HEAD, name="Sync title")
    text(s, 1.25, y + 0.26, 5.0, 0.56, desc, size=10.5, name="Sync text")
screen(s, 6.55, 1.72, 6.18, "documents.jpg",
       "Documents page: 106 files searchable, 40 scanned copies awaiting text recognition, 4 password-protected")
caption(s, 6.55, 5.5, 6.18, "Documents page: 508 files, each searchable or listed with its reason (synthetic data)")
note = box(s, 6.55, 5.86, 6.18, 0.45, fill=PINK, line=PINK_LINE, name="File name note")
shape_text(note, [[{"text": "Never matched by name alone: ", "bold": True, "color": MAGENTA, "font": HEAD},
                   {"text": "think scan1234.pdf or “(final)” copies", "bold": False,
                    "color": SUB, "font": TEXT}]], size=10.5, align=PP_ALIGN.LEFT, margin=0.15)

# ===============================================================================================
# 16 Security and access
start_section("Trust")
s = content("Access Decided by the Case",
            "What a person may read decides what every page, chart and answer may use")
cols = [(0.6, 1.55, "Entra ID group"), (2.15, 2.75, "Cases and case data"), (4.9, 1.9, "Documents")]
for x, w, head in cols:
    h = box(s, x, 1.72, w, 0.45, grad=True, name=f"Table header {head}")
    shape_text(h, head, size=11, align=PP_ALIGN.LEFT, margin=0.12)
roles = [("Legal-UAE", "UAE cases", "UAE files"),
         ("Legal-KSA", "KSA cases", "KSA files"),
         ("Legal-MENA", "Egypt, Jordan, Kuwait, Oman, Qatar, Turkey, India", "The same countries"),
         ("Legal-Ops", "All countries", "All files"),
         ("Leadership", "All countries", "All files"),
         ("Procurement", "All countries", "None: no document catalogue")]
for i, row in enumerate(roles):
    y = 2.17 + i * 0.52
    box(s, 0.6, y, 6.2, 0.52, fill=PINK if i % 2 == 0 else WHITE, line=PINK_LINE, line_w=0.5, name=f"Role row {i}")
    for j, ((x, w, _), value) in enumerate(zip(cols, row)):
        text(s, x + 0.05, y, w - 0.1, 0.52, value, size=10.5, bold=j == 0, color=MAGENTA if j == 0 else SUB,
             font=HEAD if j == 0 else TEXT, anchor=MSO_ANCHOR.MIDDLE, name="Role cell")
caption(s, 0.6, 5.36, 6.2, "Mailbox, intake-form and app-store data are filtered by country as well.")
controls = [("lock_w.png", "Enforced in the data",
             "Each person gets a read-only copy of the case data holding only their rows; every search is "
             "filtered by access group"),
            ("block_w.png", "No hints about hidden cases",
             "A case you may not see is reported exactly like one that does not exist"),
            ("person_w.png", "Bound to a person",
             "Each conversation belongs to the user who started it, and so does the case in focus"),
            ("MdBadge_w.png", "Entra ID in production",
             "Group claims map to the six roles; until then the server listens on this machine only")]
for i, (ic, head, desc) in enumerate(controls):
    x = 7.15 + (i % 2) * 2.84
    y = 1.72 + (i // 2) * 1.86
    box(s, x, y, 2.74, 1.72, fill=WHITE, line=PINK_EDGE, name=f"Control {head}")
    icon(s, x + 0.18, y + 0.18, 0.48, ic, scale=0.56)
    text(s, x + 0.75, y + 0.12, 1.95, 0.6, head, size=11.5, bold=True, color=DARK, font=HEAD,
         anchor=MSO_ANCHOR.MIDDLE, name="Control title")
    text(s, x + 0.15, y + 0.78, 2.5, 0.92, desc, size=10.5, name="Control text")
banner(s, 5.85, "The same rules drive every KPI, chart, case list, document and answer: switch the persona and "
                "everything changes", size=11.5)

# 17 Quality
s = content("Measured Before It Ships",
            "A golden set of real questions, access probes and offline tests decide whether a change ships")
qstats = [("30", "Golden questions", "25 answered from documents and 5 from case data; 22 in English, 8 in Arabic"),
          ("3", "Access probes", "Restricted cases and files must not leak into any answer"),
          ("75+", "Offline tests", "Sync, access rules, assistant, dashboards and web, with no network")]
for i, (num, lab, desc) in enumerate(qstats):
    y = 1.72 + i * 1.38
    box(s, 0.6, y, 3.9, 1.24, fill=PINK, name=f"Quality stat {lab}")
    text(s, 0.78, y + 0.1, 1.2, 1.04, num, size=28, bold=True, color=MAGENTA, font=HEAD, anchor=MSO_ANCHOR.MIDDLE,
         name="Quality value")
    text(s, 2.0, y + 0.12, 2.4, 0.3, lab, size=12.5, bold=True, color=DARK, font=HEAD, name="Quality label")
    text(s, 2.0, y + 0.42, 2.42, 0.78, desc, size=10.5, name="Quality text")
label(s, 4.85, 1.62, 3.9, "EVERY ANSWER IS CHECKED FOR", color=MAGENTA)
checks = [("Route", "Documents, case tracker or both, as expected"),
          ("Source", "The expected file is among the citations"),
          ("Language", "Answered in the language of the question"),
          ("No leak", "Probes reveal nothing outside the user’s access"),
          ("Correctness", "A Claude judge compares each answer with the reference")]
for i, (head, desc) in enumerate(checks):
    y = 2.02 + i * 0.77
    icon(s, 4.85, y + 0.03, 0.42, "verified_w.png", scale=0.6)
    text(s, 5.4, y - 0.04, 3.3, 0.3, head, size=12, bold=True, color=DARK, font=HEAD, name="Check title")
    text(s, 5.4, y + 0.25, 3.35, 0.45, desc, size=10.5, name="Check text")
data = CategoryChartData()
data.categories = ["From documents", "From case data"]
data.add_series("English", (18, 4))
data.add_series("Arabic", (7, 1))
gframe = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(9.0), Inches(1.95), Inches(3.73), Inches(2.3), data)
gframe.name = "Golden set chart"
chart = gframe.chart
chart.has_title = False
chart.has_legend = True
chart.legend.position = XL_LEGEND_POSITION.TOP
chart.legend.include_in_layout = False
chart.legend.font.size = Pt(10)
chart.font.size = Pt(10)
chart.font.name = TEXT
chart.font.color.rgb = rgb(SUB)
cat = chart.category_axis
cat.reverse_order = True
cat.has_major_gridlines = False
cat.format.line.color.rgb = rgb(BORDER)
cat.tick_labels.font.size = Pt(10)
val = chart.value_axis
val.visible = False
val.has_major_gridlines = False
val.maximum_scale = 26
plot = chart.plots[0]
plot.gap_width = 55
plot.overlap = 100
plot.has_data_labels = True
plot.data_labels.font.size = Pt(10)
plot.data_labels.font.bold = True
plot.data_labels.position = XL_LABEL_POSITION.CENTER
plot.data_labels.show_value = True
for series, colour, fg in zip(plot.series, [MAGENTA, PINK_LINE], [WHITE, MAGENTA]):
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = rgb(colour)
    labels = series.data_labels
    labels.show_value = True
    labels.font.color.rgb = rgb(fg)
    labels.font.size = Pt(10)
    labels.font.bold = True
    labels.position = XL_LABEL_POSITION.CENTER
text(s, 9.0, 1.62, 3.73, 0.3, "GOLDEN SET BY SOURCE AND LANGUAGE", size=11, bold=True, color=BODY, font=HEAD,
     name="Chart label")
box(s, 9.0, 4.42, 3.73, 1.38, fill=GREY_BG, name="Live note")
text(s, 9.12, 4.47, 3.5, 1.3, [[{"text": "Verified live", "bold": True, "color": DARK, "font": HEAD, "size": 11.5}],
                               "English and Arabic cited answers, case counts and access refusals on Claude Sonnet 5. "
                               "The full golden-set run comes next, before UAT."], size=10.5, name="Live note text")
banner(s, 6.0, "In UAT the golden set grows with Legal’s own questions; after go-live it is re-run before every "
               "change", size=11.5)

# ===============================================================================================
# 18 From demo to production
start_section("Delivery")
s = content("From Demo to Production",
            "The demo runs the real code on synthetic data; production replaces each stand-in with your platform")
label(s, 2.65, 1.62, 4.4, "IN THE DEMO TODAY")
label(s, 7.6, 1.62, 5.1, "IN YOUR TENANT", color=MAGENTA)
mapping = [("Sign-in", "Persona switcher with ten test users", "Entra ID sign-in; group claims mapped to the six roles"),
           ("Case files", "508-file corpus in a folder, mapped by a manifest",
            "SharePoint case libraries, synced through Microsoft Graph"),
           ("Search", "SQLite full-text index with a light Arabic stemmer",
            "Azure AI Search: Arabic analyzer, vectors, access filter"),
           ("Scanned files", "Read on this laptop's CPU: 3 of 40 done, 37 queued",
            "OCR on a GPU or Document Intelligence before indexing"),
           ("Case data", "Data-pack tables, one read-only copy per user",
            "Your trackers and intake data, refreshed on a schedule"),
           ("Dashboards", "D1–D4 and DS-1 in Superset, embedded per persona",
            "Superset or Power BI on your data, embedded the same way"),
           ("Language model", "Claude Sonnet 5 on Amazon Bedrock",
            "Claude on Amazon Bedrock or Microsoft Foundry, in your region")]
for i, (head, demo, prod) in enumerate(mapping):
    y = 1.98 + i * 0.6
    tile = box(s, 0.6, y, 1.9, 0.5, grad=True, name=f"Mapping {head}")
    shape_text(tile, head, size=11, margin=0.1)
    c = box(s, 2.65, y, 4.4, 0.5, fill=WHITE, line=PINK_LINE, name=f"Demo {head}")
    shape_text(c, demo, size=10.5, bold=False, color=SUB, font=TEXT, align=PP_ALIGN.LEFT, margin=0.12)
    arrow(s, 7.14, y + 0.12, w=0.36, h=0.26)
    c = box(s, 7.6, y, 5.13, 0.5, fill=PINK, line=PINK_LINE, name=f"Production {head}")
    shape_text(c, prod, size=10.5, bold=False, color=DARK, font=TEXT, align=PP_ALIGN.LEFT, margin=0.12)
caption(s, 0.6, 6.25, 12.1, "The case logic, access rules and assistant stay the same; the stand-ins are replaced one "
                            "by one, each verified against the golden set.")

# 19 The plan
s = content("Live in Five Weeks, Handed Over in Six",
            "Indicative plan: workstreams run in parallel, and access and decisions are needed in week 1")
X0, PER = 4.3, 1.4  # chart origin and inches per week


def wx(week):
    return X0 + week * PER


plan = [("Foundation: environments, identity, model access", [(0, 1, DARK)]),
        ("SharePoint sync with permissions", [(1, 3, MAGENTA)]),
        ("OCR for scans; Arabic search tuning", [(1, 3, MAGENTA)]),
        ("Production search index and shared state", [(1, 3, MAGENTA)]),
        ("Case-data pipelines", [(1, 3, PURPLE)]),
        ("Dashboards D1–D4 and drill-throughs", [(2.5, 4, PURPLE)]),
        ("Embedding and deep links in Ferrero", [(3, 4, PURPLE)]),
        ("UAT, golden-set growth, security review", [(4, 5, RED)]),
        ("Hypercare and handover", [(5, 6, BODY)])]
TOP, PITCH = 2.12, 0.34
for wk, m in [(1, "M1"), (3, "M2"), (4, "M3"), (5, "M4"), (6, "HC")]:
    box(s, wx(wk) - 0.006, 1.98, 0.012, TOP + len(plan) * PITCH - 1.98, fill=PINK_LINE, name="Milestone guide")
    box(s, wx(wk) - 0.08, 1.8, 0.16, 0.16, fill=MAGENTA, shape=MSO_SHAPE.DIAMOND, name="Milestone")
    text(s, wx(wk) - 0.4, 1.5, 0.8, 0.27, m, size=10, bold=True, color=MAGENTA, font=HEAD, align=PP_ALIGN.CENTER,
         margin=0, name="Milestone label")
for i, (name, bars) in enumerate(plan):
    y = TOP + i * PITCH
    text(s, 0.6, y, 3.55, PITCH, name, size=10.5, color=SUB, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE,
         margin=0, name="Plan row label")
    for start, end, colour in bars:
        bar = box(s, wx(start) + 0.03, y + 0.06, (end - start) * PER - 0.06, PITCH - 0.12, fill=colour,
                  shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=f"Bar {name}")
        bar.adjustments[0] = 0.3
axis_y = TOP + len(plan) * PITCH + 0.02
box(s, wx(0), axis_y, 6 * PER, 0.01, fill=BODY, name="Week axis")
for wk in range(6):
    text(s, wx(wk), axis_y + 0.03, PER, 0.24, f"Week {wk + 1}", size=10, bold=True, color=BODY, font=HEAD,
         align=PP_ALIGN.CENTER, margin=0, name="Week label")
gates = [("M1 · end of week 1", "Platform ready: sign-in, model access, golden set passing"),
         ("M2 · end of week 3", "Build complete: SharePoint sync, OCR, search, case data loaded"),
         ("M3 · end of week 4", "Dashboards ready: D1–D4 on the case model, inside Ferrero"),
         ("M4 · end of week 5", "Go-live: Legal signs off answers, refusals and dashboards"),
         ("HC · end of week 6", "Handover: no open severity-1, runbook accepted")]
for i, (head, desc) in enumerate(gates):
    x = 0.6 + i * 2.453
    box(s, x, 5.62, 2.33, 0.9, fill=PINK if i < 4 else GREY_BG, line=PINK_LINE if i < 4 else None,
        name=f"Gate {head}")
    text(s, x + 0.1, 5.65, 2.15, 0.28, head, size=10.5, bold=True, color=MAGENTA, font=HEAD, name="Gate title")
    text(s, x + 0.1, 5.93, 2.15, 0.56, desc, size=10, color=SUB, name="Gate text")

# 20 What we need
s = content("What We Need from You, and When",
            "The plan holds only if access and decisions arrive on time; each late input has a known effect")
hard = [("Decisions in week 1",
         "Hosting region and data residency; where Claude runs (Amazon Bedrock or Microsoft Foundry); the BI "
         "platform for the dashboards (Superset or Power BI)"),
        ("Legal stays in control",
         "Legal owns the corpus, the access groups and acceptance; nothing goes live without Legal’s sign-off on "
         "answers and refusals")]
for i, (head, desc) in enumerate(hard):
    x = 0.6 + i * 6.16
    hdr = box(s, x, 1.72, 5.97, 0.42, grad=True, name="Hard dependency header")
    shape_text(hdr, head, size=12)
    box(s, x, 2.14, 5.97, 0.92, fill=WHITE, line=PINK_EDGE, name="Hard dependency body")
    text(s, x + 0.15, 2.16, 5.7, 0.88, desc, size=11, color=SUB, anchor=MSO_ANCHOR.MIDDLE, name="Hard text")
label(s, 0.6, 3.25, 6.0, "DEPENDENCY CALENDAR")
cal = [("Week 1", "Project owner, steering committee and KPI owners named"),
       ("Week 1", "Cloud subscription and Claude access in place"),
       ("Week 1", "Entra ID app registration with the groups claim"),
       ("Week 1", "Read access to the case libraries, with their permission mapping"),
       ("Week 1", "Case trackers, mailbox, intake and app monitoring data shared"),
       ("Week 1", "Dashboard KPIs and page layouts agreed in a workshop"),
       ("Week 3", "Domain name and TLS certificate; BI licences if needed"),
       ("Before UAT", "UAT participants and their sample questions")]
for i, (week, desc) in enumerate(cal):
    x = 0.6 + (i % 4) * 3.08
    y = 3.6 + (i // 4) * 1.28
    box(s, x, y, 2.89, 1.13, fill=PINK if week == "Week 1" else GREY_BG, name=f"Calendar {i + 1}")
    badge(s, x + 0.14, y + 0.15, 1.2 if len(week) > 7 else 0.95, 0.28, week)
    text(s, x + 0.1, y + 0.52, 2.7, 0.58, desc, size=10.5, color=SUB, name="Calendar text")
caption(s, 0.6, 6.2, 12.1, "If an input is late, only the work that depends on it moves, and we report it the same "
                           "week.")

# 21 Where we are
s = content("Where We Are Today",
            "The product runs end to end on synthetic data; the next steps land it on your platform")
done_stats = [("6", "App pages", "Overview, cases, case detail, assistant, documents, dashboards"),
              ("508", "Files tracked", "467 searchable in 3,014 passages; the rest listed with a reason"),
              ("30 + 3", "Evaluation set", "30 golden questions and 3 access probes, ready to run"),
              ("75+", "Offline tests", "Sync, access rules, assistant, dashboards and web")]
for i, (num, lab, desc) in enumerate(done_stats):
    x = 0.6 + i * 3.08
    box(s, x, 1.72, 2.86, 1.58, fill=PINK, name=f"Status stat {lab}")
    text(s, x + 0.25, 1.78, 2.5, 0.6, num, size=28, bold=True, color=MAGENTA, font=HEAD, name="Stat value")
    text(s, x + 0.25, 2.38, 2.5, 0.3, lab, size=12.5, bold=True, color=DARK, font=HEAD, name="Stat label")
    text(s, x + 0.25, 2.68, 2.5, 0.58, desc, size=10.5, name="Stat text")
label(s, 0.6, 3.45, 5.8, "DONE", color=MAGENTA)
done = ["Case model with Overview, Cases and Case pages, under all six access roles",
        "A file for every catalogue entry: 508 English and Arabic documents",
        "Superset dashboards D1–D4 and DS-1 embedded, filtered per persona",
        "Bilingual assistant answering live on Claude Sonnet 5 (Amazon Bedrock)"]
for i, item in enumerate(done):
    y = 3.82 + i * 0.66
    icon(s, 0.6, y, 0.44, "verified_w.png", scale=0.6)
    text(s, 1.18, y - 0.02, 5.2, 0.5, item, size=11.5, color=SUB, anchor=MSO_ANCHOR.MIDDLE, name="Done item")
label(s, 6.85, 3.45, 5.8, "NEXT", color=DARK)
nxt = ["Text recognition for the 37 remaining scans (running)",
       "Entra ID sign-in in place of the persona switcher",
       "SharePoint sync on your tenant; production search index",
       "Full golden-set run, then UAT with Legal’s own questions",
       "Dashboard guest role and embed domains locked down"]
for i, item in enumerate(nxt):
    y = 3.82 + i * 0.53
    c = box(s, 6.85, y, 0.42, 0.42, fill=PINK, line=PINK_LINE, shape=MSO_SHAPE.OVAL, name=f"Next {i + 1}")
    shape_text(c, str(i + 1), size=11, color=MAGENTA, margin=0)
    text(s, 7.42, y - 0.03, 5.3, 0.48, item, size=11.5, color=SUB, anchor=MSO_ANCHOR.MIDDLE, name="Next item")

# ===============================================================================================
# 22 Live demo
start_section("Demo and close")
s = new_slide(L_SEPARATOR)
ph = {p.placeholder_format.idx: p for p in s.placeholders}
ph[0].text = "Live Demo"
ph[10].left, ph[10].top, ph[10].width, ph[10].height = Inches(0.87), Inches(4.67), Inches(11.6), Inches(0.6)
ph[10].text = ("Overview  →  Dashboards  →  Case page  →  Ask Ferrero  →  Arabic  →  "
               "Access  →  Documents")

# 23 Thank you
s = new_slide(L_THANKS)
ph = {p.placeholder_format.idx: p for p in s.placeholders}
tf = ph[13].text_frame
tf.text = "Every case in view."
tf.add_paragraph().text = "Every answer cited."


# ---- speaker notes from the presenter script ---------------------------------------------------
def load_script(path):
    """Return {slide number: notes}. Paragraphs under '## Slide N' are separated by blank lines, as in Markdown."""
    notes, current = {}, None
    for line in open(path, encoding="utf-8"):
        heading = re.match(r"^## Slide (\d+)\b", line)
        if heading:
            current = int(heading.group(1))
            notes[current] = [[]]
        elif line.startswith("#"):
            current = None
        elif current is not None:
            if line.strip():
                notes[current][-1].append(line.strip())
            elif notes[current][-1]:
                notes[current].append([])
    return {n: "\n".join(" ".join(p) for p in paras if p) for n, paras in notes.items()}


NOTES = load_script(SCRIPT)
missing = [n for n in range(1, len(prs.slides) + 1) if n not in NOTES]
if missing:
    sys.exit(f"presenter script has no section for slides {missing}")
for number, slide in enumerate(prs.slides, start=1):
    slide.notes_slide.notes_text_frame.text = NOTES[number]

# ---- sections ---------------------------------------------------------------------------------
for name, ids in SECTIONS:
    sec = etree.SubElement(section_list, "{%s}section" % P14, name=name, id="{%s}" % str(uuid.uuid4()).upper())
    lst = etree.SubElement(sec, "{%s}sldIdLst" % P14)
    for sid in ids:
        etree.SubElement(lst, "{%s}sldId" % P14, id=str(sid))

prs.core_properties.title = "Ferrero Case Intelligence: Solution Approach"
prs.core_properties.subject = "Case dashboards and a bilingual legal assistant: the problem, the approach and the plan"
prs.core_properties.author = "Intertec Solution Architecture"
prs.save(OUT)
print("slides:", len(prs.slides), "->", OUT)
