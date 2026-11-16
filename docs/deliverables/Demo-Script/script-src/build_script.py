"""Builds the Ferrero live-demo script: HTML here, then PDF through headless Chrome (print_pdf.py).

The words live in this file so a timing change is one edit, and the speaking-time check runs on the same text that
gets printed. Every figure was read from the running app on 12 Nov 2026 (app date frozen at 5 Nov 2026).

    python build_script.py            # writes demo-script.html next to this file and prints the timing check
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "demo-script.html"
WPM = 135  # comfortable presenting pace

# --------------------------------------------------------------------------------------------- the steps

STEPS = [
    dict(
        n=1, start="0:00", end="0:30", title="Frame it", reqs=[],
        brd="The BRD asks for two things on one case model: a consolidated view of every case "
            "(<b>R1, the key requirement</b>) and an assistant that answers from the case files, with sources (R2&ndash;R4).",
        show=["Ferrero is open on <b>Overview</b>, signed in as <b>Priya Menon</b> (Legal-Ops). No clicks yet."],
        say=["What you&rsquo;re about to see is the working product, live. The data is synthetic: the company name and "
             "the trademarks are fictional stand-ins for yours. It does the two things your requirements ask for: one consolidated view of every case, and an assistant that "
             "answers from your own case files, with sources, in English or Arabic. The app&rsquo;s &lsquo;today&rsquo; is "
             "fixed at 5 November, so the figures stay stable. I&rsquo;ll call out the requirement numbers as we go."],
        wait=0,
    ),
    dict(
        n=2, start="0:30", end="1:30", title="One view of every case", reqs=["R1*"],
        brd="<b>R1 &middot; Key requirement:</b> replace the per-country Excel trackers with one consolidated view of "
            "every case, for every audience.",
        show=["Point along the KPI row, left to right.",
              "Scroll down slowly past <b>Open cases by stage</b> and <b>Open cases by country</b>.",
              "Stop at <b>Upcoming hearings and due actions</b>: the overdue rows sit at the top."],
        say=["This is R1, the key requirement: one view instead of nine country trackers. I&rsquo;m Priya, Legal "
             "Operations, so I see all 120 cases. 37 are open, 8 have a hearing in the next 30 days, and 4 actions "
             "are overdue. They sit at the top of this list, each with the counsel who owns it. And the money: "
             "64 percent of what was awarded or settled has been recovered, an 88 percent win rate on decided cases, "
             "and 5.8 million dirhams of legal spend.",
             "<span class=\"cue\">Bridge:</span> The same figures, for each audience, live in the dashboards."],
        careful="Don&rsquo;t click <b>What needs my attention?</b> in the main path: it is a live AI question and adds "
                "about 20 s. Use it only if you are ahead of time.",
        shots=[("overview", "Open cases <b>37</b> (120 in scope) &middot; Hearings in 30 days <b>8</b> &middot; "
                            "Overdue <b>4</b> &middot; Closed this year <b>28</b> &middot; Recovery <b>64.1%</b> &middot; "
                            "Win rate <b>88.0%</b> &middot; Legal spend <b>AED 5.8M</b>")],
        wait=15,
    ),
    dict(
        n=3, start="1:30", end="2:30", title="Same numbers, every audience", reqs=["R1*"], layout="wide",
        brd="<b>R1:</b> one dashboard per audience from the spec: D1 legal team, D2 leadership and procurement, "
            "D3 legal operations, D4 brand protection, plus DS-1 case detail.",
        show=["Sidebar &rarr; <b>Dashboards</b>.",
              "Click the tab <b>D1 &middot; Legal Case Overview</b>. Talk while the tiles draw (5&ndash;10 s).",
              "Click <b>D2 &middot; Leadership Command View</b>.",
              "Point along the other tabs: <b>D3</b>, <b>D4</b>, <b>DS-1</b>. Don&rsquo;t open them unless asked."],
        say=["You asked for dashboards for each audience. These are the four from the specification, embedded "
             "right here. D1 is for the legal team: the same 37 open, 8 hearings and 4 overdue "
             "as the overview, because it is the same case model. D2 is the leadership view: 152 million dirhams "
             "claimed, 40 million awarded or settled, 26 million recovered. D3 covers intake and triage, D4 "
             "infringers and enforcement outcomes, and DS-1 is the case drill-through.",
             "<span class=\"cue\">Bridge:</span> Let&rsquo;s open one case."],
        careful="The proposal promised Power BI: don&rsquo;t name the BI tool unless asked (answer on page 11). "
                "Never open the last tab, <b>Legal &amp; Brand Protection</b> (a combined draft that loads slowly). "
                "&ldquo;Avg days open&rdquo; reads 250.6 here and 251 days on the Overview: same figure, rounded. "
                "If the dashboards don&rsquo;t draw, skip the step and say &ldquo;same tiles as the overview, same case data&rdquo;.",
        shots=[("dash-d1", "<b>D1</b>: 37 &middot; 2 &middot; 8 &middot; 4 &middot; 250.6 &middot; 28, identical to the Overview"),
               ("dash-d2", "<b>D2</b>: claimed 152,193,967 &middot; awarded + settled 40,378,715 &middot; "
                           "recovered 25,878,960 &middot; recovery 64.1% &middot; win 88.0% &middot; spend 5,826,000")],
        wait=20,
    ),
    dict(
        n=4, start="2:30", end="3:15", title="One page per case", reqs=["R1*", "R6"], layout="wide",
        brd="<b>R1, drill-through DS-1:</b> parties, amounts, timeline, documents and counsel spend for one case, "
            "with an &ldquo;Ask Ferrero about this case&rdquo; button.",
        show=["Click the top search box (<i>Search cases, parties, marks&hellip;</i>), type <b>TM-2024-428</b>, press <b>Enter</b>.",
              "Point at <b>Closed &middot; Won &middot; Confidential</b>, the four amount tiles, the <b>Timeline</b>, and "
              "<b>Documents on file &middot; 1 of 4 searchable by Ferrero</b>.",
              "<i>Optional, +15 s:</i> click <b>Case dashboard</b>; DS-1 shows the same figures; browser <b>Back</b>."],
        say=["Every case has one page: the case drill-through. VELORA against Zahrat Al Sahra Trading, in Dubai: won. "
             "3.3 million claimed, 2.3 million awarded and fully recovered. Here&rsquo;s the timeline, the counsel "
             "spend, and every document on file, each with an honest status: one is searchable, three are in the "
             "catalogue but not yet in the library. &lsquo;Case dashboard&rsquo; opens this same case as a dashboard, "
             "with the same figures.",
             "<span class=\"cue\">Bridge:</span> But what does the file actually say?"],
        shots=[("case428", "VELORA v. Zahrat Al Sahra Trading &middot; Claimed <b>AED 3.3M</b> &middot; Awarded <b>AED 2.3M</b> "
                           "&middot; Recovered <b>AED 2.3M</b>"),
               ("dash-ds1", "<b>DS-1</b> for the same case: 3,334,000 &middot; 2,288,000 &middot; 2,288,000 &middot; legal spend 107,000")],
        wait=10,
    ),
    dict(
        n=5, start="3:15", end="4:30", title="Ask, and check every word", reqs=["R2", "R3", "R4", "R6", "R10"], layout="wider",
        brd="<b>R3:</b> every statement cited to its document and section. <b>R4:</b> answers only from the files; "
            "no guessing.",
        show=["Click <b>Ask Ferrero about this case</b> (top right of the case card). The panel opens: "
              "<i>Ask about TM-2024-428</i>.",
              "Type <span class=\"q\">What damages were awarded in TM-2024-428?</span> and press <b>Enter</b>.",
              "While it works (15&ndash;25 s), point at the steps appearing: <i>Searched documents&hellip;</i>, "
              "<i>Looked up case&hellip;</i>",
              "Click citation <b>[1]</b> in the answer: Source 1 lights up with <b>TM-2024-428_Judgment_EN.pdf "
              "&middot; Operative part</b>, the quoted sentence and the SharePoint path.",
              "Point at the footer: <b>How Ferrero answered &middot; N steps &middot; N s</b>."],
        say=["<span class=\"cue\">While it works:</span> Now the assistant, in plain English. You can watch what it "
             "does: it searches this case&rsquo;s documents and checks the case tracker, and it only ever sees what "
             "Priya is cleared to see.",
             "<span class=\"cue\">When the answer lands:</span> 2,288,000 dirhams. Every statement carries a number; "
             "click it, and there&rsquo;s the exact paragraph, the operative part of the judgment, with the file and "
             "its SharePoint path. That&rsquo;s R3: a lawyer checks it in one click. The last line cross-checks the "
             "case tracker, and they agree. If they didn&rsquo;t, it would show both and name each source. And when "
             "the files don&rsquo;t hold the answer, it says so instead of guessing. That&rsquo;s R4.",
             "<span class=\"cue\">Bridge:</span> It works across cases too."],
        shots=[("answer-cited", "&ldquo;&hellip;the Court awarded <b>AED 2,288,000</b>.&rdquo; Four numbered citations; "
                                "badges <b>Case documents</b> + <b>Case tracker</b>; last line: matches the case tracker")],
        wait=15,
    ),
    dict(
        n=6, start="4:30", end="5:15", title="Compare two cases", reqs=["R7"],
        brd="<b>R7:</b> comparisons across cases, in one answer.",
        show=["In the same panel type <span class=\"q\">Compare the outcomes of TM-2024-428 and TM-2024-407.</span> "
              "and press <b>Enter</b>.",
              "Let it answer (about 20 s), then point at the citations from <b>both</b> judgments."],
        say=["R7 is comparisons across cases. One question, two cases: it reads each case&rsquo;s files and puts the "
             "evidence side by side. One was won; the other was dismissed, and the judgment says why: no notarised "
             "test purchase, no proof of sale in the UAE. Normally that means reading two files side by side.",
             "<span class=\"cue\">Bridge:</span> And in Arabic."],
        careful="Wording changes from run to run; the facts don&rsquo;t. <b>Running late? Cut this step first.</b>",
        see="<b>TM-2024-428</b> won: AED 2,288,000 awarded (Dubai). <b>TM-2024-407</b> lost: the AED 225,000 claim was "
            "dismissed by the Sharjah court for insufficient evidence (no notarised test purchase, no proof of delivery "
            "in the UAE). Often shown as a small table.",
        wait=20,
    ),
    dict(
        n=7, start="5:15", end="6:00", title="Arabic in, Arabic out", reqs=["R2", "R6"],
        brd="<b>R2:</b> plain-language questions in English or Arabic, answered in the language of the question.",
        show=["Close the panel (<b>&times;</b> or <b>Esc</b>), then Sidebar &rarr; <b>Assistant</b>.",
              "Click the Arabic example: <span class=\"ar\" dir=\"rtl\" lang=\"ar\">ما شروط التسوية في القضية TM-2024-421؟</span> "
              "<span class=\"muted\">(&ldquo;What are the settlement terms in case TM-2024-421?&rdquo;)</span>"],
        say=["R2 also means Arabic as an equal. Same assistant, an Arabic question about a settlement: the answer "
             "comes back in Arabic, right to left, citing the Arabic agreement: 49,000 dirhams, sixty percent within "
             "14 days and the rest within 60, the stock destroyed within 30 days. Case and registration numbers stay "
             "exactly as written. That&rsquo;s R6, exact identifiers.",
             "<span class=\"cue\">Bridge:</span> So who gets to see all of this?"],
        shots=[("answer-arabic", "Arabic, right to left, citing the Arabic settlement agreement: <b>AED 49,000</b> "
                                 "(60% in 14 days, 40% in 60); stock destroyed within 30 days; registration "
                                 "<b>UAE-TM-284517</b> kept as written")],
        wait=20,
    ),
    dict(
        n=8, start="6:00", end="7:30", title="Access follows the person", reqs=["R5", "R8"],
        brd="<b>R5:</b> each person sees only what their role allows, in every chart, list, document and answer.",
        show=["Bottom-left user card &rarr; <b>Omar Al Qahtani</b> (Legal-KSA).",
              "Sidebar &rarr; <b>Overview</b>: 9 open cases, 23 in scope, KSA only.",
              "Sidebar &rarr; <b>Dashboards</b> &rarr; tab <b>D1</b>: 9 &middot; 0 &middot; 2 &middot; 1. The Country "
              "filter shows <i>1 option</i>.",
              "Top right <b>Ask Ferrero</b> &rarr; click the first example: <span class=\"q\">What damages were awarded "
              "in TM-2024-428?</span>"],
        say=["R5, access. I&rsquo;m now Omar, litigation counsel in Saudi Arabia. Every number changes: 9 open cases, "
             "not 37, only KSA. The dashboards apply the very same rule. Now I&rsquo;ll ask about the UAE "
             "case we just opened&hellip; No figures, and it won&rsquo;t even confirm the case exists. That&rsquo;s by "
             "design: access is enforced in the data, not in the prompt. The model is never handed what Omar can&rsquo;t "
             "see, so there&rsquo;s nothing to leak, however the question is phrased. That&rsquo;s our answer on R8, "
             "misuse. And Procurement sees the case figures but no documents at all.",
             "<span class=\"cue\">Bridge:</span> Back to Priya, and the files themselves."],
        shots=[("overview-omar", "As Omar: Open cases <b>9</b> &middot; 23 in scope &middot; recovery 96.3% &middot; KSA only"),
               ("dash-d1-omar", "D1 as Omar: <b>9</b> &middot; 0 &middot; 2 &middot; 1 &middot; 349.3 &middot; 4"),
               ("answer-access", "About 5 s: &ldquo;TM-2024-428 is not in the files available to you&hellip;&rdquo;")],
        wait=30,
    ),
    dict(
        n=9, start="7:30", end="8:45", title="Every file accounted for, scans included", reqs=["R9", "R4"], layout="wide",
        brd="<b>R9:</b> scanned documents made searchable, with low-confidence pages flagged.",
        show=["User card &rarr; <b>Priya Menon</b>.",
              "Sidebar &rarr; <b>Documents</b>. Point at the four tiles.",
              "In <i>File, case number, type&hellip;</i> type <b>157264</b>, then click <b>Scan_20250814_157264.pdf</b>.",
              "Point: the scan on the left, the recognised Arabic on the right, <b>Scanned copy &middot; read with 94% "
              "confidence</b>."],
        say=["R9, scanned documents. Every file in the libraries is accounted for: 109 searchable, password-protected "
             "files listed but never opened, nothing silently dropped. Scans are read page by page with text "
             "recognition. Here&rsquo;s an Arabic customs seizure notice: the scan on the left, the recognised text on "
             "the right, read with 94 percent confidence. A page that reads poorly is flagged for a person to check, "
             "not trusted blindly. In this environment 37 scans are still being processed; in production, text "
             "recognition takes seconds per page."],
        careful="If the tiles differ (text recognition ran since 12 Nov), read them as shown. <i>Optional, +20 s:</i> "
                "search <b>141551</b>: that power of attorney was read at 89% and is <b>Searchable, to review</b>. "
                "The model read &ldquo;POA-2625&rdquo; where the scan says &ldquo;POA-2025&rdquo;, which is exactly why "
                "weak pages are flagged.",
        shots=[("documents", "Searchable <b>109</b> (692 passages) &middot; Read from scans <b>3 of 40</b> &middot; "
                             "Password-protected <b>4</b> &middot; Not linked <b>0</b>"),
               ("docview-ar-scan", "Customs seizure notice, TM-2025-430, Arabic: scan beside recognised text, <b>94%</b>")],
        wait=20,
    ),
    dict(
        n=10, start="8:45", end="9:30", title="Close", reqs=["R10", "R11"],
        brd="<b>R10:</b> quality and cost made transparent. <b>R11:</b> runs on your cloud, priced up front.",
        show=["Sidebar &rarr; <b>Overview</b> (optional). No more clicks; look at the room."],
        say=["Two last requirements. R10, transparency: every answer shows the steps it took and how long it took, "
             "and the assistant is scored against a 30-question golden set, in English and Arabic, on documents and "
             "case data, plus access probes, with 77 automated tests behind it. R11: it runs in your cloud: Claude on "
             "Amazon Bedrock or Microsoft Foundry in your region, with Entra ID sign-in, your SharePoint libraries, "
             "and dashboards in Power BI or Superset. Same code, same access rules. Every case in view, every answer "
             "cited. Thank you."],
        wait=0,
    ),
]

REQS = [
    ("R1", "Consolidated case dashboards", "Key requirement", "2, 3, 4",
     "Overview tiles = dashboards D1/D2 = DS-1 for the case; every audience, one case model"),
    ("R2", "Plain-language questions in English or Arabic", "", "5, 7",
     "English question, English answer; Arabic question, Arabic answer, right to left"),
    ("R3", "Every statement cited to document, page and section", "", "5",
     "Numbered markers open the quoted paragraph, file, section and SharePoint path"),
    ("R4", "Answers only from the documents; no guessing", "", "5, 8, 9",
     "Cross-checks the tracker; says so when the files are silent; every file has a status"),
    ("R5", "Respect document access", "", "8",
     "Omar (KSA) sees 9 open cases, not 37; dashboard filtered; UAE case hidden"),
    ("R6", "Exact identifiers", "", "4, 5, 7",
     "Case numbers, file names and registration numbers kept exactly as written"),
    ("R7", "Comparisons across cases", "", "6",
     "One answer, two cases, citations from both judgments"),
    ("R8", "Resistance to prompt injection and misuse", "Say, don&rsquo;t demo", "8",
     "The model never receives what the user may not see; off-topic requests are declined"),
    ("R9", "Scanned documents searchable", "", "9",
     "Arabic scan read at 94%; a weak page flagged for review at 89%"),
    ("R10", "Transparency of quality and cost", "", "5, 10",
     "&ldquo;How Ferrero answered&rdquo; steps and seconds; golden set; 77 tests"),
    ("R11", "Run on your cloud, priced up front", "Say", "10",
     "Claude on Amazon Bedrock or Microsoft Foundry, in your region; cost sheet"),
]

MESSAGES = [
    ("One view of every case", "The key requirement: dashboards for every audience on one case model, so a chart, a "
                               "case page and an answer never disagree.", "R1"),
    ("Answers only from your files", "Every statement cited to the paragraph it came from; when the files are "
                                     "silent, it says so.", "R3 &middot; R4"),
    ("English and Arabic as equals", "Questions, answers, documents and scans in both languages.", "R2 &middot; R9"),
    ("Access follows the person", "Enforced in the data, not the prompt; a hidden case looks like a missing one.",
     "R5 &middot; R8"),
    ("Measured, and yours to run", "Golden set and tests; runs on Bedrock or Foundry in your region.",
     "R10 &middot; R11"),
]

QA = [
    ("Is this real data?",
     "No. It is synthetic but consistent across every table and file: 120 cases, 9 countries, 6 marks, 45 infringers, "
     "150 files (78 Arabic). The real portfolio replaces it at kickoff; nothing else changes."),
    ("Which AI model, and where does our data go?",
     "Claude (Sonnet 5) on Amazon Bedrock in this demo; the same code runs on Microsoft Foundry. It runs in your own "
     "cloud account and region under enterprise terms, with no training on your data. The exact terms are part of the "
     "week-1 hosting decision."),
    ("Why Superset and not Power BI?",
     "The dashboards follow the BRD spec on the same case model. Superset is what this build uses; Power BI is the "
     "alternative (the measures are already in the data pack). The BI platform is a week-1 decision."),
    ("What if a scan is misread?",
     "Every page gets a confidence score. Below 80% the document is not indexed; below 90% the page is flagged for "
     "review. The viewer shows the scan beside its text, and answers say when they rely on a scanned copy."),
    ("What if a document and the tracker disagree?",
     "Ferrero gives both and names each source; it never silently picks one."),
    ("How is access enforced?",
     "Each person&rsquo;s role (an Entra ID group in production) decides which cases they get. The assistant and the "
     "dashboards only ever receive those rows and documents, so a hidden case looks exactly like a missing one."),
    ("How accurate is it?",
     "It is measured on a 30-question golden set (25 document, 5 case-data; 22 English, 8 Arabic) plus 3 access "
     "probes. The full scored run is the gate before UAT, and Legal adds its own questions during UAT."),
    ("Prompt injection?",
     "Access is enforced outside the model, so a planted instruction cannot unlock hidden cases, and documents are "
     "treated as evidence to quote. The production build adds the input guard and content filter from the proposal."),
    ("How long to go live?",
     "Indicative plan: live in 5 weeks, handed over in 6. Week 1 decides the hosting region, where Claude runs and "
     "the BI platform."),
]

DONT = [
    "Quote a golden-set score. The full scored run hasn&rsquo;t been done yet (it makes billed model calls).",
    "Point at cost per answer. This build shows steps and seconds, not cost.",
    "Present DS-2 to DS-6 as separate dashboards. DS-1 is built; the infringer, intake and app-store views sit "
    "inside D3 and D4.",
    "Present Entra ID sign-in, SharePoint sync or Azure AI Search as live. The demo uses a user switcher, a local "
    "copy of the libraries and a local index; those are the production steps.",
    "Type <b>127.0.0.1:8090</b>. Superset only embeds into <b>localhost:8090</b>.",
]

# --------------------------------------------------------------------------------------------- helpers

def words(html_text: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return len(text.split())


def secs(clock: str) -> int:
    m, s = clock.split(":")
    return int(m) * 60 + int(s)


def dur(a: str, b: str) -> str:
    d = secs(b) - secs(a)
    m, s = divmod(d, 60)
    return (f"{m} min " if m else "") + (f"{s} s" if s else "").strip()


def chip(r: str) -> str:
    if r.endswith("*"):
        return f'<span class="chip key">{r[:-1]} &middot; KEY</span>'
    return f'<span class="chip">{r}</span>'


def timing(step: dict) -> tuple[int, int, int]:
    talk = round(sum(words(s) for s in step["say"]) / WPM * 60)
    slot = secs(step["end"]) - secs(step["start"])
    return talk, step.get("wait", 0), slot


def step_html(step: dict) -> str:
    talk, wait, slot = timing(step)
    chips = "".join(chip(r) for r in step["reqs"])
    show = "".join(f"<li>{s}</li>" for s in step["show"])
    say = "".join(f"<p>{s}</p>" for s in step["say"])
    careful = f'<div class="careful"><span class="bang">!</span><div>{step["careful"]}</div></div>' if step.get("careful") else ""
    shots = step.get("shots", [])
    if shots:
        figs = "".join(
            f'<figure><img src="img/{name}.jpg" alt=""><figcaption><span class="see">You will see</span>{cap}</figcaption></figure>'
            for name, cap in shots)
        right = f'<div class="right">{figs}</div>'
        layout = "cols" + (" " + step["layout"] if step.get("layout") else "")
    elif step.get("see"):
        right = f'<div class="right"><div class="seebox"><span class="see">You will see</span>{step["see"]}</div></div>'
        layout = "cols"
    else:
        right = ""
        layout = "single"
    return f"""
<section class="step">
  <div class="step-head">
    <div class="num">{step['n']}</div>
    <div class="titleblock">
      <div class="clock">{step['start']} &ndash; {step['end']} <span>&middot; {dur(step['start'], step['end'])}</span></div>
      <h2>{step['title']}</h2>
    </div>
    <div class="chips">{chips}</div>
  </div>
  <div class="brd"><span class="brdtag">BRD</span><div>{step['brd']}</div></div>
  <div class="{layout}">
    <div class="left">
      <div class="label">Show</div>
      <ol class="show">{show}</ol>
      <div class="label">Say <span class="est">about {talk} s of talk{f' + {wait} s of clicks and waiting' if wait else ''}</span></div>
      <div class="say">{say}</div>
      {careful}
    </div>
    {right}
  </div>
</section>"""


# --------------------------------------------------------------------------------------------- pages

def run_sheet() -> str:
    rows = []
    for s in STEPS:
        first = re.sub(r"<[^>]+>", "", s["show"][0])
        first = re.sub(r"\s+", " ", first)
        rows.append(f"""<tr><td class="c-n">{s['n']}</td><td class="c-t">{s['start']}&ndash;{s['end']}</td>
<td class="c-b"><b>{s['title']}</b></td><td class="c-d">{RUN_DO[s['n']]}</td>
<td class="c-r">{''.join(chip(r) for r in s['reqs']) or '<span class="muted">intro</span>'}</td></tr>""")
    return "".join(rows)


RUN_DO = {
    1: "Overview on screen as Priya. No clicks.",
    2: "KPI row &rarr; scroll to <i>Upcoming hearings and due actions</i>.",
    3: "Dashboards &rarr; <b>D1</b> tab &rarr; <b>D2</b> tab.",
    4: "Search <b>TM-2024-428</b> &rarr; case page (&rarr; Case dashboard).",
    5: "<b>Ask Ferrero about this case</b> &rarr; damages question &rarr; click [1].",
    6: "Ask: compare TM-2024-428 and TM-2024-407.",
    7: "Assistant &rarr; Arabic example chip (TM-2024-421).",
    8: "Switch to <b>Omar</b> &rarr; Overview &rarr; D1 &rarr; Ask Ferrero &rarr; first chip.",
    9: "Back to <b>Priya</b> &rarr; Documents &rarr; open scan <b>157264</b>.",
    10: "Golden set, tests, your cloud. Thank you.",
}

CSS = r"""
@page { size: A4; margin: 13mm 13mm 15mm 13mm; }
:root{
  --ink:#16171b; --ink2:#3b3d44; --muted:#6c6f77; --line:#e4dfd4; --soft:#f7f3ea; --soft2:#fbf8f2;
  --gold:#a8772b; --gold-ink:#7a5418; --gold-soft:#f2e6cf; --dark:#16171b; --warn:#9a5a00; --warn-soft:#fff3df;
}
*{ box-sizing:border-box; }
html,body{ margin:0; padding:0; background:#fff; }
body{ font-family:"Segoe UI", system-ui, sans-serif; color:var(--ink); font-size:9.4pt; line-height:1.42;
      -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.page{ page-break-after:always; break-after:page; }
.page:last-child{ page-break-after:auto; break-after:auto; }
h1,h2,h3{ margin:0; letter-spacing:-0.01em; }
b{ font-weight:600; }
.muted{ color:var(--muted); }
.ar{ font-family:"Segoe UI", sans-serif; unicode-bidi:isolate; font-size:10.5pt; display:inline-block; white-space:nowrap; direction:rtl; }
.q{ font-weight:600; background:var(--soft); border:1px solid var(--line); border-radius:4px; padding:0 4px; white-space:normal; }

/* cover band */
.band{ background:var(--dark); color:#fff; border-radius:10px; padding:16px 18px; display:flex; align-items:center; gap:14px; }
.mono{ width:40px; height:40px; border-radius:10px; background:linear-gradient(145deg,#2a2b31,#121317);
       border:1px solid #3a3b41; display:grid; place-items:center; color:#d7a54c; font-weight:700; font-size:20px; flex:none; }
.band h1{ font-size:19pt; font-weight:600; }
.band .sub{ color:#c9c6bd; font-size:9.6pt; margin-top:2px; }
.band .tag{ margin-left:auto; text-align:right; font-size:8pt; color:#d7a54c; letter-spacing:.12em; text-transform:uppercase; line-height:1.5; }
.band .tag span{ color:#9d9a92; letter-spacing:0; text-transform:none; display:block; }

.stats{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin:9px 0 9px; }
.stat{ border:1px solid var(--line); border-radius:9px; padding:8px 10px; background:var(--soft2); }
.stat .k{ font-size:7.4pt; letter-spacing:.12em; text-transform:uppercase; color:var(--gold-ink); font-weight:600; }
.stat .v{ font-size:13.5pt; font-weight:600; margin-top:1px; }
.stat .s{ font-size:8pt; color:var(--muted); }

h3.sec{ font-size:11.5pt; margin:4px 0 6px; display:flex; align-items:center; gap:8px; }
h3.sec::before{ content:""; width:4px; height:14px; background:var(--gold); border-radius:2px; display:inline-block; }

table{ border-collapse:collapse; width:100%; }
.run td{ border-bottom:1px solid var(--line); padding:4.2px 6px; vertical-align:top; font-size:9pt; }
.run tr:last-child td{ border-bottom:none; }
.run th{ text-align:left; font-size:7.4pt; letter-spacing:.1em; text-transform:uppercase; color:var(--muted);
         font-weight:600; padding:0 6px 4px; border-bottom:1.5px solid var(--ink); }
.c-n{ width:22px; font-weight:700; color:var(--gold-ink); }
.c-t{ width:66px; white-space:nowrap; font-variant-numeric:tabular-nums; color:var(--ink2); }
.c-b{ width:150px; }
.c-r{ width:118px; }
.chip{ display:inline-block; font-size:7.3pt; font-weight:600; padding:1px 6px; border-radius:20px; margin:0 3px 3px 0;
       border:1px solid var(--line); background:#fff; color:var(--ink2); white-space:nowrap; }
.chip.key{ background:var(--gold); border-color:var(--gold); color:#fff; }

.twocol{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }
.box{ border:1px solid var(--line); border-radius:9px; padding:9px 11px; background:#fff; }
.box.gold{ background:var(--soft); border-color:#e8dcc4; }
.box.warn{ background:var(--warn-soft); border-color:#f1d9b0; }
.box h4{ margin:0 0 4px; font-size:9.6pt; }
.box ul, .box ol{ margin:0; padding-left:16px; }
.box li{ margin:2px 0; }

.qbox{ margin-top:10px; }
.qs td{ padding:3px 6px 3px 0; vertical-align:middle; font-size:9.2pt; }
.qs .w{ width:150px; color:var(--muted); font-size:8.2pt; white-space:nowrap; }
.who{ margin-top:6px; font-size:8.6pt; color:var(--ink2); border-top:1px dashed var(--line); padding-top:5px; }
/* checklist */
.check{ list-style:none; padding:0; margin:0; }
.check li{ display:flex; gap:9px; padding:5px 0; border-bottom:1px dashed var(--line); }
.check li:last-child{ border-bottom:none; }
.tick{ flex:none; width:13px; height:13px; border:1.5px solid var(--ink2); border-radius:3px; margin-top:2px; }
.when{ font-size:7.6pt; letter-spacing:.12em; text-transform:uppercase; color:var(--gold-ink); font-weight:700; margin:8px 0 2px; }
.fix td{ border-bottom:1px solid var(--line); padding:5px 6px; vertical-align:top; }
.fix td:first-child{ width:34%; font-weight:600; }

/* BRD page */
.msgs{ display:grid; grid-template-columns:repeat(5,1fr); gap:7px; margin:4px 0 9px; }
.msg{ border:1px solid #e8dcc4; background:var(--soft); border-radius:9px; padding:8px 9px; }
.msg .i{ font-size:15pt; font-weight:700; color:var(--gold); line-height:1; }
.msg h4{ margin:4px 0 3px; font-size:9.2pt; line-height:1.25; }
.msg p{ margin:0; font-size:8.2pt; color:var(--ink2); }
.msg .r{ margin-top:5px; font-size:7.4pt; font-weight:700; color:var(--gold-ink); letter-spacing:.04em; }
.req td{ border-bottom:1px solid var(--line); padding:3.6px 6px; vertical-align:top; font-size:8.7pt; }
.req th{ text-align:left; font-size:7.3pt; letter-spacing:.1em; text-transform:uppercase; color:var(--muted);
         font-weight:600; padding:0 6px 4px; border-bottom:1.5px solid var(--ink); }
.req .id{ width:36px; font-weight:700; color:var(--gold-ink); }
.req .st{ width:54px; text-align:center; font-variant-numeric:tabular-nums; font-weight:600; }
.req tr.key td{ background:var(--soft); }
.note{ font-size:7.8pt; color:var(--muted); margin-top:6px; }
.roles td{ border:1px solid var(--line); padding:3px 6px; font-size:8.1pt; vertical-align:top; }
.roles th{ border:1px solid var(--line); background:var(--soft); padding:3px 6px; font-size:7.4pt; text-align:left; }

/* steps */
.step{ margin-bottom:12px; break-inside:avoid; }
.step + .step{ border-top:1px solid var(--line); padding-top:11px; }
.step-head{ display:flex; align-items:center; gap:11px; }
.num{ flex:none; width:34px; height:34px; border-radius:9px; background:var(--dark); color:#d7a54c; font-weight:700;
      font-size:15pt; display:grid; place-items:center; }
.titleblock{ flex:1; }
.clock{ font-size:8.4pt; color:var(--gold-ink); font-weight:700; letter-spacing:.04em; font-variant-numeric:tabular-nums; }
.clock span{ color:var(--muted); font-weight:500; letter-spacing:0; }
.step h2{ font-size:14.5pt; font-weight:600; }
.chips{ text-align:right; max-width:230px; }
.brd{ display:flex; gap:9px; align-items:flex-start; margin:8px 0 9px; background:var(--soft); border:1px solid #e8dcc4;
      border-radius:8px; padding:7px 10px; font-size:9pt; }
.brdtag{ flex:none; font-size:7.2pt; font-weight:700; letter-spacing:.12em; color:#fff; background:var(--gold);
         border-radius:4px; padding:2px 5px; margin-top:1px; }
.cols{ display:grid; grid-template-columns:1.12fr 1fr; gap:13px; align-items:start; }
.cols.wide{ grid-template-columns:1fr 1.22fr; }
.cols.wider{ grid-template-columns:1fr 1.4fr; }
.single{ display:block; }
.label{ font-size:7.6pt; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:700; margin:2px 0 4px; }
.label .est{ letter-spacing:0; text-transform:none; font-weight:500; color:var(--muted); margin-left:6px; font-size:7.8pt; }
ol.show{ margin:0 0 9px; padding:0; list-style:none; counter-reset:s; }
ol.show li{ counter-increment:s; position:relative; padding-left:24px; margin:0 0 5px; font-size:9.3pt; }
ol.show li::before{ content:counter(s); position:absolute; left:0; top:0.5px; width:17px; height:17px; border-radius:50%;
                    background:var(--gold-soft); color:var(--gold-ink); font-size:8pt; font-weight:700; display:grid; place-items:center; }
.say{ border-left:3.5px solid var(--gold); background:var(--soft2); border-radius:0 8px 8px 0; padding:8px 11px 8px 12px;
      font-size:10.6pt; line-height:1.5; color:var(--ink); }
.say p{ margin:0 0 6px; }
.say p:last-child{ margin-bottom:0; }
.cue{ display:inline-block; font-size:7.6pt; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--gold-ink);
      margin-right:4px; }
.careful{ display:flex; gap:8px; margin-top:8px; background:var(--warn-soft); border:1px solid #f1d9b0; border-radius:8px;
          padding:6px 9px; font-size:8.5pt; color:#4a3a1f; }
.bang{ flex:none; width:15px; height:15px; border-radius:50%; background:var(--warn); color:#fff; font-weight:700;
       font-size:9pt; display:grid; place-items:center; margin-top:1px; }
figure{ margin:0 0 8px; }
figure img{ width:100%; display:block; border:1px solid var(--line); border-radius:7px; }
figcaption{ font-size:8pt; color:var(--ink2); margin-top:3px; line-height:1.35; }
.see{ display:block; font-size:7pt; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin-bottom:1px; }
.seebox{ border:1px dashed #d9cdb5; border-radius:8px; padding:9px 11px; font-size:9pt; background:#fff; }

/* Q&A + cheat sheet */
.qa{ display:grid; grid-template-columns:1fr 1fr; gap:6px 12px; }
.qa div{ border-bottom:1px solid var(--line); padding:4px 0 6px; }
.qa h4{ margin:0 0 2px; font-size:9.2pt; }
.qa p{ margin:0; font-size:8.6pt; color:var(--ink2); }
.nums td{ border-bottom:1px solid var(--line); padding:3.5px 6px; font-size:8.6pt; font-variant-numeric:tabular-nums; }
.nums th{ text-align:left; font-size:7.3pt; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); font-weight:600;
          padding:0 6px 3px; border-bottom:1.5px solid var(--ink); }
.nums td:not(:first-child), .nums th:not(:first-child){ text-align:right; }
.kv{ font-size:8.6pt; margin:0; padding-left:15px; }
.kv li{ margin:2.5px 0; }
"""


def build() -> str:
    steps = {s["n"]: step_html(s) for s in STEPS}
    total_talk = sum(timing(s)[0] for s in STEPS)
    total_wait = sum(timing(s)[1] for s in STEPS)

    page1 = f"""
<div class="page">
  <div class="band">
    <div class="mono">F</div>
    <div>
      <h1>Live demo script</h1>
      <div class="sub">Ferrero Case Intelligence &middot; your part, under 10 minutes: what to click, what to say, and the BRD point each moment proves</div>
    </div>
    <div class="tag">Internal<span>for the presenter, not the client</span><span>Thu 12 Nov 2026</span></div>
  </div>

  <div class="stats">
    <div class="stat"><div class="k">Your slot</div><div class="v">9 min 30 s</div><div class="s">scripted, plus 30 s spare</div></div>
    <div class="stat"><div class="k">Start as</div><div class="v">Priya Menon</div><div class="s">Legal-Ops: sees every case</div></div>
    <div class="stat"><div class="k">Open</div><div class="v">localhost:8090</div><div class="s">never 127.0.0.1 (dashboards break)</div></div>
    <div class="stat"><div class="k">App date</div><div class="v">5 Nov 2026</div><div class="s">frozen; all data synthetic</div></div>
  </div>

  <h3 class="sec">Run sheet</h3>
  <table class="run">
    <thead><tr><th>#</th><th>Clock</th><th>Beat</th><th>Do this</th><th>BRD</th></tr></thead>
    <tbody>{run_sheet()}</tbody>
  </table>

  <div class="twocol">
    <div class="box gold">
      <h4>Running late? Cut in this order</h4>
      <ol>
        <li><b>Step 6</b> (compare): saves 45 s.</li>
        <li>The <b>D2</b> tab in step 3: saves 20 s.</li>
        <li><b>Step 7</b>: just say &ldquo;Arabic works the same way&rdquo;: saves 40 s.</li>
        <li>Never cut steps 5 and 8: citations and access are what the room remembers.</li>
      </ol>
    </div>
    <div class="box">
      <h4>Three rules on stage</h4>
      <ul>
        <li><b>Talk while it loads.</b> Every AI answer or dashboard has a line to cover the wait.</li>
        <li><b>Never troubleshoot live.</b> If something stalls, say one sentence and move to the next step.</li>
        <li><b>The screen beats this script.</b> If a number differs, read the screen.</li>
      </ul>
    </div>
  </div>
  <div class="box qbox">
    <h4>The questions you&rsquo;ll ask, word for word</h4>
    <table class="qs">
      <tr><td class="w">Step 5 &middot; type</td><td><span class="q">What damages were awarded in TM-2024-428?</span></td></tr>
      <tr><td class="w">Step 6 &middot; type</td><td><span class="q">Compare the outcomes of TM-2024-428 and TM-2024-407.</span></td></tr>
      <tr><td class="w">Step 7 &middot; click the chip</td><td><span class="ar" dir="rtl" lang="ar">ما شروط التسوية في القضية TM-2024-421؟</span></td></tr>
      <tr><td class="w">Step 8 &middot; as Omar, first chip</td><td><span class="q">What damages were awarded in TM-2024-428?</span></td></tr>
    </table>
    <div class="who">Switch user (bottom-left card): <b>step 8 &rarr; Omar Al Qahtani</b> (Legal-KSA) &middot; <b>step 9 &rarr; back to Priya Menon</b></div>
  </div>
  <p class="note">Timing check: {total_talk // 60} min {total_talk % 60:02d} s of talk at {WPM} words a minute + {total_wait // 60} min {total_wait % 60:02d} s of clicks and waiting. Every figure was read from the running app on 12 Nov 2026.</p>
</div>"""

    page2 = """
<div class="page">
  <h3 class="sec">Before you start</h3>
  <div class="twocol" style="margin-top:0">
    <div class="box">
      <div class="when">30 minutes before</div>
      <ul class="check">
        <li><span class="tick"></span><div>Is <b>start.cmd</b> running? Its window must stay open (closing it stops the app). If not, double-click <b>D:\\Ferrero\\start.cmd</b> and wait for the browser to open <b>http://localhost:8090</b>.</div></li>
        <li><span class="tick"></span><div><b>Don&rsquo;t run ocr.cmd today.</b> Text recognition takes all the CPU and memory, and every answer slows down. If a window titled <i>Ferrero text recognition</i> is open, close it.</div></li>
        <li><span class="tick"></span><div><b>Warm up the assistant</b> (one billed question, a few cents): Assistant &rarr; click <i>What damages were awarded in TM-2024-428?</i>. Expect AED 2,288,000 with citations in under 30 s. Then reload the page so the demo starts clean.</div></li>
        <li><span class="tick"></span><div><b>Warm up the dashboards</b>: Dashboards &rarr; <b>D1</b> tab. Wait for 37 &middot; 2 &middot; 8 &middot; 4. This also proves the Superset server is reachable from the room&rsquo;s network.</div></li>
        <li><span class="tick"></span><div>Test the venue Wi-Fi; keep a phone hotspot ready. The assistant (Amazon Bedrock) and the dashboards (Superset) both need internet.</div></li>
      </ul>
    </div>
    <div class="box">
      <div class="when">Two minutes before</div>
      <ul class="check">
        <li><span class="tick"></span><div>User card (bottom left) shows <b>Priya Menon &middot; Legal-Ops</b>.</div></li>
        <li><span class="tick"></span><div>On <b>Overview</b>, Country = <i>All countries</i>, Mark = <i>All marks</i>; the assistant panel is closed.</div></li>
        <li><span class="tick"></span><div>Light theme (moon icon, top right). One Chrome window, one tab, <b>F11</b> full screen; zoom 100% on the laptop, 110&ndash;125% on a large screen.</div></li>
        <li><span class="tick"></span><div>Notifications off (Focus assist / Do not disturb). Share <b>only the browser window</b>.</div></li>
        <li><span class="tick"></span><div>This script open on a second screen or printed: page 1 is all you need on stage.</div></li>
      </ul>
    </div>
  </div>

  <h3 class="sec" style="margin-top:14px">If something goes wrong</h3>
  <table class="fix">
    <tr><td>An answer takes longer than 30 s</td><td>Keep talking: &ldquo;it&rsquo;s reading the judgment and checking the tracker&rdquo;. The ticked steps show progress. Past 60 s or an error: click <b>New conversation</b> and send once more (a failed turn is rolled back). Still stuck? Say &ldquo;the network is slow here; this is the answer it gives&rdquo; and show the screenshot from this script.</td></tr>
    <tr><td>Dashboards blank, or &ldquo;Dashboards are unavailable&rdquo;</td><td>Skip step 3: &ldquo;the same tiles you just saw on the Overview: it&rsquo;s the same case data.&rdquo; Don&rsquo;t debug on stage.</td></tr>
    <tr><td>&ldquo;Ferrero is temporarily unavailable&rdquo;</td><td>The start.cmd window was closed. Double-click start.cmd, wait about 20 s, reload.</td></tr>
    <tr><td>Wrong person on screen</td><td>User card, bottom left &rarr; pick Priya Menon (or Omar Al Qahtani in step 8).</td></tr>
    <tr><td>Someone asks why &ldquo;today&rdquo; is 5 November</td><td>&ldquo;The demo data is frozen at 5 November so the figures match the test set; in production it&rsquo;s the real date.&rdquo;</td></tr>
  </table>

  <h3 class="sec" style="margin-top:14px">Don&rsquo;t claim on stage</h3>
  <div class="box warn"><ul>""" + "".join(f"<li>{d}</li>" for d in DONT) + """</ul></div>
</div>"""

    req_rows = "".join(
        f'<tr class="{"key" if tag == "Key requirement" else ""}"><td class="id">{rid}</td><td><b>{name}</b>'
        f'{f" <span class=chip>{tag}</span>" if tag else ""}</td><td class="st">{steps_}</td><td>{proof}</td></tr>'
        for rid, name, tag, steps_, proof in REQS)
    msgs = "".join(
        f'<div class="msg"><div class="i">{i}</div><h4>{h}</h4><p>{p}</p><div class="r">{r}</div></div>'
        for i, (h, p, r) in enumerate(MESSAGES, 1))
    page3 = f"""
<div class="page">
  <h3 class="sec">The BRD in one page: five messages to land</h3>
  <div class="msgs">{msgs}</div>

  <h3 class="sec">Every requirement, and where you prove it</h3>
  <table class="req">
    <thead><tr><th>ID</th><th>BRD requirement</th><th>Step</th><th>What the room sees</th></tr></thead>
    <tbody>{req_rows}</tbody>
  </table>

  <div class="twocol">
    <div>
      <h3 class="sec">Dashboards in the spec, all live</h3>
      <table class="roles">
        <tr><th>ID</th><th>Dashboard</th><th>Audience and question</th></tr>
        <tr><td><b>D1</b></td><td>Legal Case Overview</td><td>Legal team: what needs attention?</td></tr>
        <tr><td><b>D2</b></td><td>Leadership Command</td><td>Leadership: does enforcement pay?</td></tr>
        <tr><td><b>D3</b></td><td>Intake &amp; Triage</td><td>Legal Ops: keeping up with reports?</td></tr>
        <tr><td><b>D4</b></td><td>Infringers &amp; Outcomes</td><td>Brand protection: next budget?</td></tr>
        <tr><td><b>DS-1</b></td><td>Case Detail</td><td>Everyone: one case, plus &ldquo;Ask Ferrero&rdquo;</td></tr>
      </table>
    </div>
    <div>
      <h3 class="sec">Who sees what (R5)</h3>
      <table class="roles">
        <tr><th>Role (Entra ID group)</th><th>Cases and figures</th><th>Documents</th></tr>
        <tr><td>Legal-UAE / Legal-KSA</td><td>own country</td><td>own country</td></tr>
        <tr><td>Legal-MENA</td><td>EG, JO, KW, QA, OM, TR, IN</td><td>same</td></tr>
        <tr><td>Legal-Ops, Leadership</td><td>all</td><td>all</td></tr>
        <tr><td>Procurement</td><td>all</td><td><b>none</b></td></tr>
      </table>
    </div>
  </div>
  <p class="note">Requirement IDs and wording follow the requirements map in the Ferrero technical proposal (R1&ndash;R11). Dashboard
  scope comes from the demo pack&rsquo;s Dashboard_Specs, and the roles from its Semantic_Model.</p>
</div>"""

    pages_steps = [
        f'<div class="page">{steps[1]}{steps[2]}</div>',
        f'<div class="page">{steps[3]}</div>',
        f'<div class="page">{steps[4]}</div>',
        f'<div class="page">{steps[5]}</div>',
        f'<div class="page">{steps[6]}{steps[7]}</div>',
        f'<div class="page">{steps[8]}</div>',
        f'<div class="page">{steps[9]}</div>',
    ]

    qa = "".join(f"<div><h4>{q}</h4><p>{a}</p></div>" for q, a in QA)
    page_last = f"""
<div class="page">
  {steps[10]}
  <h3 class="sec" style="margin-top:6px">Likely questions, short answers</h3>
  <div class="qa">{qa}</div>
</div>
<div class="page">
  <h3 class="sec">Numbers cheat sheet <span class="muted" style="font-weight:400;font-size:8.6pt">(read from the app on 12 Nov 2026; app date 5 Nov 2026)</span></h3>
  <div class="twocol" style="margin-top:4px">
    <div>
      <table class="nums">
        <thead><tr><th>Overview tile</th><th>Priya (Legal-Ops)</th><th>Omar (Legal-KSA)</th></tr></thead>
        <tbody>
          <tr><td>Cases in scope</td><td>120</td><td>23</td></tr>
          <tr><td>Open cases</td><td>37</td><td>9</td></tr>
          <tr><td>Opened in last 30 days</td><td>2</td><td>0</td></tr>
          <tr><td>Hearings in next 30 days</td><td>8</td><td>2</td></tr>
          <tr><td>Overdue actions</td><td>4</td><td>1</td></tr>
          <tr><td>Closed this year</td><td>28</td><td>4</td></tr>
          <tr><td>Recovery rate</td><td>64.1%</td><td>96.3%</td></tr>
          <tr><td>Win rate</td><td>88.0% (66/75)</td><td>100% (13/13)</td></tr>
          <tr><td>Legal spend</td><td>AED 5.8M</td><td>AED 1.3M</td></tr>
          <tr><td>Average age, open cases</td><td>251 days</td><td>349 days</td></tr>
        </tbody>
      </table>
      <h3 class="sec" style="margin-top:12px">Documents page (Priya)</h3>
      <ul class="kv">
        <li>150 files from the case libraries (78 Arabic, 72 English)</li>
        <li><b>109</b> searchable by Ferrero, <b>692</b> passages</li>
        <li>Read from scans <b>3 of 40</b>; 37 awaiting text recognition</li>
        <li><b>4</b> password-protected: listed, never opened; <b>0</b> not linked to a case</li>
        <li>Arabic scan <b>157264</b>: 94% &middot; flagged power of attorney <b>141551</b>: 89%</li>
        <li>Procurement (Noor Al Hashimi): no documents at all</li>
      </ul>
    </div>
    <div>
      <h3 class="sec" style="margin-top:0">Dashboards</h3>
      <ul class="kv">
        <li><b>D2</b>: claimed AED 152,193,967; awarded + settled 40,378,715; recovered 25,878,960; spend 5,826,000; spend-to-recovery 0.23; average 197.6 days to close</li>
        <li><b>D3</b>: 9 reports in 30 days; 224 mailbox reports; triage SLA met 57.1%; median 30 h to triage; 20.5% become cases; 38 app takedowns, 16.5 days on average</li>
        <li><b>D4</b>: 27 active infringers; 32 repeat offenders; 2.93 cases per infringer; takedown success 61.3%; AED 215,658 recovered per case</li>
      </ul>
      <h3 class="sec" style="margin-top:12px">Demo cases</h3>
      <ul class="kv">
        <li><b>TM-2024-428</b> VELORA v. Zahrat Al Sahra Trading (Dubai CFI, unfair competition): won; claimed 3,334,000, awarded and recovered 2,288,000; counsel spend 107,000; opened 19 Oct 2024, closed 26 May 2025 (219 days); Youssef Nasser with Gulf IP Partners</li>
        <li><b>TM-2024-407</b> VELORA v. Bright Star Foodstuff (Sharjah): lost; AED 225,000 claim dismissed on 26 Mar 2025 for insufficient evidence</li>
        <li><b>TM-2024-421</b> VELORA v. Hazel Bite Foods (Abu Dhabi): settled for AED 49,000</li>
        <li>Top infringers: Souq Al Hala Online and DealHub Marketplace Seller 4471, 7 cases each</li>
      </ul>
      <h3 class="sec" style="margin-top:12px">Quality</h3>
      <ul class="kv">
        <li>Golden set: 30 questions (25 document, 5 case data; 22 English, 8 Arabic) + 3 access probes</li>
        <li>77 automated tests pass (offline; run on 12 Nov 2026)</li>
        <li>Model in this demo: Claude Sonnet 5 on Amazon Bedrock (us-east-1)</li>
      </ul>
    </div>
  </div>
</div>"""

    body = page1 + page2 + page3 + "".join(pages_steps) + page_last
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Ferrero live demo script</title>
<style>{CSS}</style></head><body>{body}</body></html>"""


def check() -> None:
    print(f"{'step':<5}{'slot':>6}{'talk':>6}{'wait':>6}{'total':>7}  title")
    total = 0
    for s in STEPS:
        talk, wait, slot = timing(s)
        total += talk + wait
        flag = "  <-- over" if talk + wait > slot + 5 else ""
        print(f"{s['n']:<5}{slot:>5}s{talk:>5}s{wait:>5}s{talk + wait:>6}s  {re.sub('<[^>]+>|&[a-z]+;', '', s['title'])}{flag}")
    print(f"total {total // 60}:{total % 60:02d} of {secs(STEPS[-1]['end']) // 60}:{secs(STEPS[-1]['end']) % 60:02d} scripted")


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    check()
    print("wrote", OUT)
