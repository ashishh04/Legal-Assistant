# Ferrero Case Intelligence: presenter script

Talk track for Ferrero-Solution-Approach.pptx. Each "## Slide N: title" section becomes that slide's speaker notes when the deck is built, and a page of the printable script; edit the words here, not in PowerPoint.

How to use it: read the plain text aloud. Lines in colour are cues, not script: the timing, the transition to the next slide, a question to ask the room, and what to answer if someone asks. The slides take about 32 minutes, and the live demo about 10 more.

## Slide 1: Ferrero Case Intelligence

Timing: about 1 minute.

Good morning, and thank you for your time. Today we will walk you through Ferrero Case Intelligence: the problem it solves for your legal and brand-protection team, what we are building, how it works, how it is secured and measured, and how we take it from today's working build to production. Then I will show it to you live.

If you remember one line, make it the one on the slide: every case in view, every answer cited. The dashboards give each audience one view of the whole portfolio, and the assistant answers from the case files, with the exact paragraph behind every statement.

On the right is the life of every question, which we will come back to. You ask in English or Arabic. Ferrero routes the question to the files or the case data, filters by your access, answers, and cites the paragraph it used.

## Slide 2: Agenda

Timing: about 30 seconds.

Ten parts. First the problem, and what we are building. Then the approach on one page, the principles behind it, how it works, and the product screen by screen. Then security and quality, the move from demo to production, the plan, and where we are today, before the live demo.

Please stop me at any point. This is meant to be a conversation, not a lecture.

## Slide 3: How Case Work Flows Today

Timing: about 2 minutes.

Let us start with how case work flows today, in five stages.

Detect: infringements reach the team through six channels, namely the infringement mailbox, intake forms, app-store monitoring, brand-protection vendors, distributors and customs. Triage: legal operations sorts each report and decides which ones become cases. Enforce: counsel and external firms pursue notices, claims and takedowns in nine countries, each with its own courts and deadlines. File: the judgments, letters and agreements sit in SharePoint folders, in English and Arabic. Report: the status of each case lives in per-country Excel trackers, which are rolled up by hand for leadership.

The pills underneath are where it hurts: six channels to watch, triage speed that nobody can see, nine sets of deadlines, files read one by one, and reports rebuilt by hand.

Transition: put simply, there is no single view of a case. That gives us six challenges.

## Slide 4: Case Insight Depends on Manual Work

Timing: about 2 minutes.

Here are the six challenges. The first is the key requirement: there is no consolidated view of the cases. Trackers, the mailbox, intake forms and app-store reports sit apart, so legal, leadership and procurement have no shared dashboard.

Second, answers are found by hand. A simple question, such as what was awarded in a case, means opening files one by one, and that costs lawyer time. Third, that invites mistakes, and a generic chatbot is worse, because it guesses with confidence.

The last three are requirements on any answer. It must be verifiable, with the document and the paragraph behind it. Confidential legal material must never reach anyone not cleared to read it; each country team sees only its own cases. And the files come in two languages, with party names in both scripts, and some scans with no text layer at all.

So what is needed is the line at the bottom: one view of every case for every audience, and an assistant that answers only from your files, with sources.

## Slide 5: Four Audiences, Four Questions

Timing: about 1.5 minutes.

Each audience asks a different question. The legal team asks: what needs my attention this week, and where does every case stand? Leadership asks: is enforcement paying for itself, and where are we exposed? Legal operations asks: are we keeping up with incoming reports, and which channels turn into real cases? And enforcement asks: which infringers and routes deserve the next budget?

Each question maps to one dashboard, D1 to D4, shown in the pills.

And everyone, whatever their role, asks the same thing about a case: what does the file actually say? That is the assistant's job.

## Slide 6: Two Capabilities on One Case Model

Timing: about 1.5 minutes.

So we are building two capabilities on one case model. Four dashboards, one per audience. Two languages, English and Arabic, for questions, files and answers. Six access roles that come from your Entra ID groups. And one case model that brings the trackers, mailbox, intake, app-store and invoice data together.

It consolidates: one model behind four dashboards. It answers: questions in either language, from the case files and the tracker, with every document claim cited. And it protects: each person sees only the cases their role allows, in every chart, list, document and answer.

Because the dashboards, the case pages and the assistant share the same data and the same access rules, the numbers always agree.

## Slide 7: How Each Challenge Is Resolved

Timing: about 1.5 minutes.

Here is each of the six challenges, and how it is resolved.

No consolidated view becomes one case model with four dashboards and a page for every case. Answers found by hand become questions in plain language, answered in seconds. The risk of wrong answers is handled by answering only from the evidence: when the files are silent, Ferrero says so instead of guessing.

Verifiability: every document claim links to its paragraph and its SharePoint path. Confidentiality: access is enforced in the data, so a case you may not open is treated as if it does not exist. And Arabic is treated as an equal, with every scanned file listed and queued, never silently dropped.

## Slide 8: The Approach on One Page

Timing: about 2 minutes.

This is the whole approach on one slide.

On the left are the sources: the case data, meaning the trackers, the mailbox and intake forms, app-store monitoring and counsel invoices; and the case libraries in SharePoint.

In the middle are two engines. The case model holds cases, events, intake, app-store detections and invoices in one set of tables, and each person gets a read-only copy holding only the rows they may see. The document sync ties each file to its case, splits it into sections and indexes it with that case's access group. Notice the arrow between them: each file inherits its case's access.

On the right is what people use: the dashboards and case pages, and the Ferrero assistant. The second arrow is the "Ask Ferrero" button: from any case page you open the assistant on that case.

The banner is the key design decision: access is decided by the case and enforced in the data layer, never by the prompt. The model cannot leak what it was never given.

## Slide 9: Six Principles Behind the Design

Timing: about 1.5 minutes.

Six principles sit behind every design choice.

One: answers come from evidence. When the files are silent, Ferrero says so. Two: access is decided by the case and enforced in the data and in every tool; a hidden case looks exactly like a missing one. Three: one set of numbers everywhere, so a dashboard and an answer never disagree.

Four: files are tied to cases by their content, not their names; a case number in a file name must agree with the text inside. Five: English and Arabic as equals. Six: everything is measured, and gaps are reported, never hidden. A skipped file is listed with its reason, and when a document and the tracker disagree, the answer says so.

## Slide 10: The Life of a Question

Timing: about 1.5 minutes.

Here is the life of a question, in six steps.

You ask, in English or Arabic, from the assistant or straight from a case page. Ferrero decides where the answer lies: in the documents, in the case data, or both. It searches the case files, but only within your access groups. It reads counts, deadlines and amounts from your own copy of the case data. Then Claude writes the answer only from the passages and rows it was given, in the language of your question. Finally, each claim from a document is linked to its paragraph, file and SharePoint path.

The banner is what makes it safe: a case you may not open is reported exactly like one that does not exist, in every tool.

If asked which model: the demo runs Claude Sonnet 5 on Amazon Bedrock, and the same code also runs on Microsoft Foundry or the Claude API.

## Slide 11: Four Dashboards, One Set of Numbers

Timing: about 1.5 minutes.

Four dashboards, one set of numbers. D1 is the legal team's overview: open and new cases, hearings in the next 30 days, overdue actions, ageing and caseload by counsel. D2 is the leadership view: claimed, awarded and recovered amounts, recovery and win rates, legal spend and exceptions. D3 covers intake and triage, and D4 infringers and enforcement outcomes.

They are built in Apache Superset, and on the right you see D1 running inside Ferrero itself. For each person, Ferrero asks Superset for a short-lived pass that carries that person's row filters, so a country user sees only their country's numbers, and nobody signs in to Superset separately.

DS-1, the case drill-through, opens from any case page, limited to that case. All the data on screen is synthetic.

If asked about the other drill-throughs: DS-1 is the drill-through built for this demo; the others are part of the project plan, in week four.

## Slide 12: One Page for Every Case

Timing: about 1 minute.

Every case has one page: the parties, court and counsel; the amounts in local currency and in dirhams; the timeline and the next action; the documents on file; and the counsel spend.

Each document shows whether Ferrero can search it and, if not, why. Here all four documents of this case are searchable.

Two buttons sit at the top. "Case dashboard" opens the Superset case drill-through for this case only. "Ask Ferrero about this case" opens the assistant with this case in focus. So you go from a chart, to a case, to a cited answer, in two clicks.

## Slide 13: Every Answer Cited, or Refused

Timing: about 1.5 minutes.

Every answer is cited, or refused.

On the left, a question about the damages awarded in a case. The answer gives the amount, and each statement carries a number that opens the quoted paragraph, with the file, the section and the SharePoint path. A lawyer can check it in one click.

On the right, the same kind of question from a Legal-KSA user about a UAE case. Ferrero gives no figures and no hint that the case exists; it simply says the case is not in the files available to them.

And when a document and the tracker disagree, Ferrero gives both and names each source, rather than silently picking one.

## Slide 14: Arabic Case Files, Answered in Arabic

Timing: about 1 minute.

Arabic is handled natively. Here an Arabic question about the settlement terms in a case is answered in Arabic, right to left, with citations into the Arabic agreement.

Underneath, one normaliser treats diacritics, tatweel, letter variants and Arabic-Indic digits the same way for documents and questions. A mark or a party named in either script still ties a file to its case. And Arabic PDFs with shaped-glyph text layers are repaired and flagged, so dates and amounts get a second look.

In the demo corpus, 251 of the 508 files are in Arabic.

## Slide 15: Every File Accounted For

Timing: about 1.5 minutes.

Every file is accounted for.

The sync collects files from SharePoint through the Graph delta API, or from a folder with a manifest, and skips anything unchanged. It matches each file to its case from the manifest or the catalogue first; a case number in a file name or text only counts when the mark or the infringer confirms it. It extracts the text, indexes each section with the case's access group, and reports a status and a reason for every file.

On the right is the Documents page. Every one of the 508 documents in the catalogue has a file. 467 are searchable, in about three thousand passages. Of the 40 scanned copies, 3 have already been read by text recognition and 37 are queued. And 4 password-protected files are listed but never opened. Nothing is silently dropped.

## Slide 16: Access Decided by the Case

Timing: about 1.5 minutes.

Access is decided by the case.

The table shows the six roles, which come from Entra ID groups. The UAE and KSA teams see their own country. The MENA team sees the other seven countries. Legal Ops and Leadership see everything. Procurement sees the case data for all countries but has no document catalogue at all. Mailbox, intake and app-store data are filtered by country too.

The controls on the right: access is enforced in the data, because each person gets a read-only copy holding only their rows, and every search is filtered by access group. There are no hints about hidden cases. Each conversation is bound to the person who started it. And in production, sign-in moves to Entra ID.

The banner is a good demo moment: switch the persona, and every number on every page changes, the dashboards included.

## Slide 17: Measured Before It Ships

Timing: about 1.5 minutes.

Quality is measured before anything ships.

The golden set has 30 questions: 25 answered from documents and 5 from case data, 22 in English and 8 in Arabic. Three access probes check that nothing restricted leaks. And more than 75 offline tests cover the sync, the access rules, the assistant, the dashboards and the web app, with no network needed.

Every answer is checked for the right route, the right source, the right language and no leaks, and a Claude judge compares it with the reference answer.

We have verified English and Arabic cited answers, case counts and access refusals live. The full golden-set run comes next, before UAT, and during UAT the golden set grows with your own questions.

If asked for a score: we will share the full golden-set result after that run; we are not quoting a number today.

## Slide 18: From Demo to Production

Timing: about 1.5 minutes.

From demo to production. The demo runs the real code on synthetic data, and each row shows the stand-in today and what replaces it in your tenant.

The persona switcher becomes Entra ID sign-in. The folder of 508 files becomes your SharePoint case libraries, through Microsoft Graph. The local full-text index becomes Azure AI Search, with an Arabic analyzer, vectors and the access filter. Scans are read on this laptop's processor today, which is slow; in production they go through OCR on a GPU or Document Intelligence before indexing. Your own trackers and intake data replace the data pack. The dashboards already run in Superset, embedded per persona; in production they connect to your data, in Superset or Power BI. And Claude runs on Amazon Bedrock or Microsoft Foundry, in your region.

The case logic, the access rules and the assistant stay the same.

## Slide 19: Live in Five Weeks, Handed Over in Six

Timing: about 2 minutes.

The plan: live in five weeks, handed over in six.

Week one is the foundation: environments, identity and model access. Weeks two and three are the main build: SharePoint sync with permissions, OCR and Arabic search tuning, the production search index and the case-data pipelines. The dashboards and drill-throughs finish in week four, embedded in Ferrero. Week five is UAT and go-live, and week six is hypercare and handover.

There are five acceptance points, M1 to M4 and the hypercare exit, each with a clear scope at the bottom of the slide.

This plan is indicative; we confirm it with you in a clarification workshop.

## Slide 20: What We Need from You, and When

Timing: about 1.5 minutes.

This is the slide to agree on today.

Three decisions are needed in week one: the hosting region and data residency; where Claude runs, Amazon Bedrock or Microsoft Foundry; and the BI platform for the dashboards, Superset or Power BI. And Legal stays in control: Legal owns the corpus, the access groups and acceptance.

Most inputs are needed in week one as well: a project owner and KPI owners; the cloud subscription and Claude access; the Entra ID app registration; read access to the case libraries with their permission mapping; the trackers, mailbox, intake and app data; and the dashboard KPIs, agreed in a workshop. Later come the domain and certificate, and the UAT participants with their sample questions.

If an input is late, only the work that depends on it moves, and we tell you the same week.

Ask: can we name an owner for each of these today?

## Slide 21: Where We Are Today

Timing: about 1.5 minutes.

Where we are today. The product runs end to end on synthetic data: six app pages; a file for every one of the 508 catalogue documents, 467 of them searchable; a 30-question golden set with 3 access probes; and more than 75 offline tests.

Done: the case model with the Overview, Cases and Case pages, under all six roles; the 508 English and Arabic documents, each with a status; the Superset dashboards D1 to D4 and DS-1, embedded and filtered per persona; and the bilingual assistant answering live on Claude Sonnet 5.

Next: text recognition for the remaining 37 scans, which is running; Entra ID sign-in; the SharePoint sync and the production search index on your tenant; the full golden-set run before UAT; and locking down the dashboard guest role and embed domains for production.

Transition: now let me show you.

## Slide 22: Live Demo

Timing: about 10 minutes.

Switch to the browser. The live-demo script has the exact clicks; this is the path.

1. Start on the Overview as Priya, Legal Operations, and point at the KPI tiles.

2. Open Dashboards and show D1. Mention the other tabs, and skip the "Legal & Brand Protection" draft tab.

3. Open case TM-2024-428: facts, amounts, timeline, and all four documents searchable.

4. Click "Ask Ferrero about this case", ask what was awarded, and open a citation.

5. Ask: compare the outcomes of TM-2024-428 and TM-2024-407.

6. Click the Arabic suggestion about the settlement terms in TM-2024-421.

7. Switch the persona to Omar, Legal-KSA: the KPIs and dashboards change. Ask about TM-2024-428; the answer is that it is not in the files available to him.

8. Finish on the Documents page: searchable files, a scan with its recognised text, and the password-protected files, each with its reason.

## Slide 23: Thank You

Timing: about 30 seconds.

Thank you. Every case in view, every answer cited.

We are happy to go deeper on any part, and to agree the week-one decisions and owners today.
