# Ferrero case intelligence: document sync and assistant

The AI part of the Ferrero case-intelligence demo (spec and data in `docs/Ferrero_Demo_Pack`):

- **Document sync** (`python -m ferrero.sync`) takes case documents from a folder or from SharePoint, ties each one to its case, and indexes it for search under that case's access group.
- **Ferrero assistant** (`python -m ferrero.web`) answers questions in English or Arabic. It draws on the case documents (with citations) and on the case tracker, which holds the same data as the Power BI dashboards. It only ever sees what the signed-in user may see.
- **Evaluation** (`python -m ferrero.eval`) scores the assistant on the pack's golden set, plus a few access-control probes.
- **Case records** (in the web app; `python -m ferrero.records` for checks) let the team register, assign, follow up and close cases and keep the case file: visual trademark comparisons, photos of infringing products and other evidence, follow-ups with deadlines and automatic reminders, the business-consultation check before enforcement, and an audit trail of every change. See "Case records" below.

All data is fictional. "Dolce Group International S.A." stands in for the customer's legal entity.

## Quick start (Windows)

Double-click **`start.cmd`**. On first run it creates the Python environment and indexes the documents; then it starts the app and opens http://127.0.0.1:8000. Close the window to stop it.

Everyone signs in. Before the first start, put a starting password in `.env` (`FERRERO_DEMO_PASSWORD=...`, at least 10 characters): every account in the user directory can then sign in with its e-mail address (for example `priya.menon@demo.local`) and that password, and choose its own from the account menu. See "Signing in" below.

Or step by step in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env                 # then put your ANTHROPIC_API_KEY in .env
.venv\Scripts\python -m ferrero.sync   # index docs\Ferrero_Demo_Pack\documents
.venv\Scripts\python -m ferrero.web    # open http://127.0.0.1:8000
.venv\Scripts\python -m pytest         # 134 offline tests; no API key or network needed
```

Scanned PDFs need text recognition first: double-click **`ocr.cmd`** (see "Text recognition").

Without credentials, the sync, the tests and the web page all still work; the chat answers with a message asking for credentials. To use Claude on Amazon Bedrock instead of an Anthropic API key, see "Assistant" below.

## Deploying to a server (Docker)

`Dockerfile` and `docker-compose.yml` run the web app on a Linux server with Docker.
- **What goes in the image:** the code, the built frontend, the case-tracker CSVs, the corpus catalogue, the document index (`data/index.sqlite`) and the cached text recognition (`data/ocr`).
- **What stays out:** the PDFs, because the app reads only the index. `.env` stays next to `docker-compose.yml` on the server and is passed in at run time, never built into the image.
- **Dependencies** are pinned to the tested versions in `deploy/constraints.txt`.

On Windows (PowerShell, in this folder), package it (about 4 MB) and copy it to the server together with `.env`:

```powershell
tar -czf ferrero-deploy.tgz --exclude=__pycache__ --exclude=*.egg-info --exclude=.running --exclude=batch.log Dockerfile docker-compose.yml .dockerignore pyproject.toml README.md deploy src docs/Ferrero_Demo_Pack/csv docs/Ferrero_Demo_Pack/documents_full_meta data/index.sqlite data/sync_status.csv data/ocr
ssh -i <key.pem> ubuntu@<server> "mkdir -p ferrero"
scp -i <key.pem> ferrero-deploy.tgz .env ubuntu@<server>:ferrero/
```

On the server:

```bash
cd ~/ferrero && tar -xzf ferrero-deploy.tgz && rm ferrero-deploy.tgz && chmod 600 .env
sudo docker compose up -d --build      # serves http://<server>/; `sudo docker compose ps` shows "healthy" when it's ready
```

To update, repeat these steps. If documents or the frontend changed, first run `python -m ferrero.sync` or `npm run build` here.

- **Port and dashboards:**
  - The app is published on port 80; `FERRERO_HTTP_PORT` changes it.
  - Superset embeds dashboards only in pages whose address is on its `frame-ancestors` list. That list includes http://3.75.206.231, but only on port 80.
  - Keep the app on plain HTTP while Superset is on HTTP, because an HTTPS page can't frame an HTTP one.
  - The server must be able to reach `FERRERO_SUPERSET_URL` to get guest tokens.
- **Sign-in:** set `FERRERO_PASSWORD` (the platform administrator, admin@ferrero.com, who then adds users and gives them passwords) in the server's `.env` too, or nobody can sign in. The app runs on plain HTTP there, so the session cookie can't be marked Secure and passwords cross the network unencrypted: put HTTPS in front (a reverse proxy with a certificate) before real users sign in, and keep limiting the port to known addresses in the security group until then. With HTTPS, the cookie becomes Secure by itself (`FERRERO_COOKIE_SECURE=auto`).
- **Users' records** (case changes, evidence files, follow-ups, the audit trail) live in the `ferrero-records` Docker volume, mounted at `/app/data/records`, so rebuilding the image keeps them. Back the volume up, for example `sudo docker run --rm -v ferrero_ferrero-records:/r -v "$PWD":/b alpine tar czf /b/records-backup.tgz -C /r .` (the volume's full name starts with the compose project's name; `sudo docker volume ls` lists it).

## How it works

```
SharePoint /sites/Legal/Cases/{country}/{case}/    or a local folder (+ optional manifest)
        │  ferrero.sync: extract text (DOCX, PDF, TXT) → tie the file to a case → split into sections
        ▼
data/index.sqlite   passages + full-text index, each passage tagged with its case's access group
data/sync_status.csv   one row per file: Indexed / Indexed (flagged) / Skipped / Pending, with the reason

Browser ── FastAPI (ferrero.web) ── Assistant: Claude (claude-opus-5-5) in a tool loop
                                     ├─ search_case_documents ┐ document index, filtered to the user's access groups;
                                     ├─ read_case_document    ┘ passages come back as citable search results
                                     ├─ get_case              ┐ case tracker (pack CSVs) as a per-user, read-only
                                     └─ query_case_data       ┘ SQLite database holding only the rows the user may see
```

### Access control

Access is enforced in the data layer and the tools, never by the prompt. A case or document the user may not see is reported exactly like one that doesn't exist.

| Entra group | Cases and case data | Documents |
|---|---|---|
| Legal-UAE / Legal-KSA | their own country | their own country |
| Legal-MENA | Egypt, Jordan, Kuwait, Qatar, Oman, Turkey, India | same |
| Legal-Ops, Leadership | all | all |
| Procurement | all | none (the document catalogue doesn't exist for this role) |

The case tracker also filters the mailbox, intake-form and app-store tables by country. The pack's RLS table leaves those three unfiltered, although D3's spec requires the filter.

**Identity:** everyone signs in (see "Signing in"), and the server takes the user from the session for every request: nothing the browser sends can choose who is asking. A conversation with Ferrero belongs to the user who started it. The server listens on 127.0.0.1 by default.

### Document sync

A file is indexed only when it can be tied to a case in the tracker, because the case decides who may read it. The case is found in this order:
1. a manifest row (see below) or the document catalogue (`fact_document`, by file name);
2. a case number in the file name, provided the text doesn't name a different case;
3. exactly one case number in the text.

Files found through steps 2 and 3 must also mention the case's mark or infringer (English or Arabic). That keeps out documents that merely reuse a case number, such as the 60 "Contoso Holding" judgments the user added to `documents/` and then excluded. Everything that isn't indexed gets a reason in `data/sync_status.csv`:
- no matching case;
- case not in the tracker;
- name and text disagree;
- content doesn't match the case;
- scan too faint to read reliably (OCR confidence below threshold);
- password-protected PDF;
- duplicate of another file.

Image-only scans wait as *Pending – waiting for text recognition* until their text has been recognised (see "Text recognition" below); they are retried on every run.

Arabic PDFs whose text layer uses presentation-form glyphs are normalised, then indexed with a review flag, because dates and amounts in mixed-direction lines may come out in visual order.

- **Incremental:** unchanged files are skipped. A local folder is rescanned in full each time; SharePoint uses the Graph delta API, and its cursor only advances when a batch fully succeeds. `--full` reprocesses everything.
- **Manifests:** for a corpus such as `documents_150/`, the sync automatically reads `documents_150_meta/manifest.csv`, which maps each file to its case and library path. It never relies on the deliberately messy file names, discards the password column unread, and prints how its statuses compare with the manifest's expected ones.
  `.venv\Scripts\python -m ferrero.sync --path docs\Ferrero_Demo_Pack\documents_150`
- **Full corpus:** `documents_full/` has a file for every catalogue row (508): the 150 corpus files copied unchanged (scans keep their cached text recognition) plus 358 text PDFs written from the case data by `python scripts\pdf_corpus\extend_corpus.py` (run with the system Python, which has PyMuPDF and python-docx, and needs Word). Every case's "Documents on file" then has its files. It is the default folder once its manifest exists.
- **SharePoint:** `--source sharepoint` with the `FERRERO_SP_*` settings in `.env`. It needs an app registration with `Sites.Selected` granted on the Legal site only. It is tested against a mocked Graph API, not yet against a real tenant.

### Text recognition (scanned PDFs)

41 of the 150 corpus PDFs are image-only scans: no text layer, so nothing to index until their text is recognised. Ferrero reads them with Baidu's [Unlimited-OCR-2](https://github.com/baidu/Unlimited-OCR) (MIT licence), a 3.3B-parameter vision-language OCR model that returns each page's text with its layout (titles, paragraphs, tables). `ferrero.ocr` turns that layout into sections, so citations into a scan point at a paragraph under its real heading, exactly like Word and PDF documents.

- **Confidence.** For every recognised token the model's probability is kept (layout markup excluded). A page's confidence is the geometric mean over its text, so a few badly misread characters pull it down instead of disappearing in an average; a document's is the mean over its pages. Documents below `FERRERO_OCR_MIN_CONFIDENCE` (0.80) are not indexed (*OCR confidence below threshold*); pages below `FERRERO_OCR_REVIEW_CONFIDENCE` (0.90) are indexed but flagged for review. Example: on one of the corpus's deliberately degraded scans the model read almost everything but wrote "POA-2625" for "POA-2025": plain average 0.93, geometric mean 0.89, so the page is flagged for review. The per-token probabilities are cached, so the thresholds can be recalibrated without recognising again.
- **Cache.** Results are stored per file content in `data/ocr/` (`<sha256>.json`, plus the page images for the viewer). A scan is recognised once, however often it is renamed, copied or re-synced; every finished page is saved, so a run can be stopped and resumed.
- **Viewer.** In the web app, every document opens in a viewer; scans show each page next to its recognised text and confidence, so a reviewer can check names, dates and amounts against the original.
- **Assistant.** Passages from scans are marked "text recognised from a scanned copy", so Ferrero can say so when it quotes them.

Two ways to run the model:

| Engine | Where | Speed | Set up |
|---|---|---|---|
| `local` | in-process, Hugging Face Transformers; NVIDIA GPU if present, else CPU | seconds per page on a GPU; minutes per page on a laptop CPU | `.venv-ocr` (below) |
| `server` | Baidu's SGLang server on a GPU (their recommended deployment), or any OpenAI-compatible endpoint serving the model | seconds per page | `FERRERO_OCR_URL=http://gpu-host:10000/v1` |

Double-click **`ocr.cmd`**: on first run it creates the OCR environment and downloads the model, then recognises every scan not yet recognised, indexing each one as soon as it is done. Or step by step:

```powershell
python -m venv .venv-ocr                              # a separate environment: PyTorch is large, the web app doesn't need it
.venv-ocr\Scripts\pip install -e ".[ocr]"             # torch 2.13 (CPU on Windows), transformers 4.52.1: the versions Baidu tested
.venv-ocr\Scripts\python -m ferrero.ocr download      # 6.7 GB, pinned revision, into models\Unlimited-OCR-2
.venv-ocr\Scripts\python -m ferrero.ocr               # recognise every scan not yet recognised (shortest first)
.venv-ocr\Scripts\python -m ferrero.ocr status        # what has been recognised, with per-page confidence
.venv-ocr\Scripts\python -m ferrero.ocr stop          # stop a running batch after its current page
```

A run saves every page as it finishes, so it can be stopped (Ctrl+C, closing its window, or `stop`) and restarted at any time; it runs below normal priority, only one run at a time, and `--log FILE` keeps a progress log. With `FERRERO_OCR_URL` set, the document sync recognises new scans itself (no separate step). Without it, the sync uses whatever `python -m ferrero.ocr` has recognised and leaves the rest pending.

**On a CPU.** Baidu's code targets CUDA. `ferrero.ocr.local` runs it unchanged on a CPU with three run-time adjustments: Transformers is told that a missing Triton is fine (its kernels only run on CUDA, behind Baidu's own try/except); two `.cuda()` calls become no-ops; and on CPUs without native bfloat16, large matrix products run in float32 (about 5x faster) while the weights stay bfloat16.

**Memory.** The model holds 6.7 GB of weights, 4.8 GB of them in the routed experts (64 per layer, 6 used per token). With less memory free, every token waits for the disk. `--experts` (or `FERRERO_OCR_EXPERTS`) chooses how the experts are held: `ram` (as loaded), `mapped` (read-only memory map of the model files: bit-for-bit the same weights, which Windows can drop and re-read cheaply; the default when less than 8 GB is free) or `int8` (half the memory, about 0.8% different per product). Measured on this project's laptop (Core i5-1235U, 16 GB, about 2 GB free while WSL, an IDE and browsers ran): as loaded 0.4 tokens/s, `mapped` 1–2 tokens/s, `int8` 0.7 tokens/s. A one-page power of attorney (890 tokens) took 16 minutes, so the 77 scanned pages take most of a day on that machine, and less with more free memory (closing WSL/Docker frees about 7 GB). On a GPU it is seconds per page.

### Assistant

- Model `claude-opus-5-5` at effort `medium` by default (`FERRERO_MODEL`, `FERRERO_EFFORT`). Server-side refusal fallback is enabled (`fallbacks: "default"`).
- The system prompt and the tool list never change during a conversation. Per-user context (today's date, who is asking, and the case opened from Power BI) goes into one appended `system` message. Conversations live on the server and are only ever appended to, which keeps the prompt cache warm and Claude's thinking valid across turns. A failed turn is rolled back, so the user can simply resend.
- Document passages are returned as `search_result` blocks, so every claim from a document carries a citation to the exact paragraph. The UI lists each citation with the quoted text and its SharePoint path.
- **The date.** The whole app works to one "today": the pages, the reminders, `reporting_date()` in the assistant's SQL, and the date the assistant is told at the start of each conversation.
  - It is the real date, asked for each time it is needed, so a running app moves on at midnight. Open cases' `days_open`, "overdue" and "the next 30 days" are all counted from it.
  - Midnight is the server's own unless `FERRERO_TIMEZONE` names a time zone (for example `Asia/Dubai`); a server in another region otherwise changes date at its own midnight.
  - `FERRERO_DEMO_TODAY=2026-11-05` fixes the date instead, at the data pack's `DEMO_TODAY`. Use it for a demonstration against the sample data as delivered: without it, the sample deadlines keep ageing (15 next actions are overdue on 19 November 2026, against 4 on the 5th).
  - The evaluation always runs as of 5 November 2026, the day its reference answers were written for, whatever the calendar says.
  - The Superset dashboards are built as of 5 November 2026 in Superset itself, so their date-based tiles (open, overdue, next 30 days) differ from the app's once the date moves on.
- **Amazon Bedrock:** install the extra with `pip install -e ".[bedrock]"`, then set `AWS_REGION`, AWS credentials (keys, `AWS_PROFILE` or `AWS_BEARER_TOKEN_BEDROCK`) and `BEDROCK_MODEL_ID` (e.g. `anthropic.claude-sonnet-5`). With no `ANTHROPIC_API_KEY` set, Bedrock is selected automatically. Requests go through the SDK's Bedrock Mantle client (the Messages API on Bedrock). Verified on 11 Nov 2026 with Claude Sonnet 5 in us-east-1.
- **Microsoft Foundry:** set `FERRERO_LLM_PROVIDER=foundry` plus `ANTHROPIC_FOUNDRY_RESOURCE` and `ANTHROPIC_FOUNDRY_API_KEY` to run on Claude in Azure.
- **Differences between providers:**
  - On Bedrock and Foundry, refusal fallback runs client-side and is optional (`FERRERO_FALLBACK_MODEL`).
  - Some setups can't take a mid-conversation `system` message: Claude Sonnet 5, and every model on Foundry. There, the per-user context leads the first user message instead.

### Power BI: "Ask Ferrero about this case" (DS-1)

Add this measure, then a button whose action is **Web URL**, with the URL set by conditional formatting to the measure:

```DAX
Ask Ferrero URL = "http://127.0.0.1:8000/?case=" & SELECTEDVALUE ( fact_case[case_id] )
```

The page opens with that case in focus, so questions that name no case are about that case.

## Web frontend

`frontend/` is a React 19 + TypeScript + Tailwind 4 app (Vite 7). `npm run build` writes it into `src/ferrero/web/dist`, and `python -m ferrero.web` serves it at http://127.0.0.1:8000. The original single-file chat page predates sign-in; `/classic` now opens the Assistant page.

| Page | What it shows |
|---|---|
| Landing page | What visitors see at `/` before signing in: what Ferrero does, how it protects the data, and the way in |
| Sign in · Signed out | E-mail address and password, "keep me signed in", help for a forgotten password, and (test environments) a list of the accounts; the page after signing out |
| Overview | Deliberately simple and workflow-first: the four stages (Register, Assign, Follow up, Close), each with what is waiting there and one click in, then "Needs attention" (the user's deadlines that are overdue or due within 7 days, else everyone's they can see). The detailed figures are on the Dashboards page. |
| Cases | Searchable, sortable case tracker with stage, outcome, next step and overdue flags |
| Case detail (DS-1) | Tabs: **Overview** (facts, amounts in local currency and AED, next step, timeline, documents with their sync status, counsel spend, commercial sensitivity, "Ask Ferrero about this case"), **Evidence & documents**, **Follow-ups**, **Trademark comparison** and **Audit trail**. "Update case" changes status, stage, next step and owner |
| Follow-ups | Every open deadline the user can see, soonest first: follow-ups set on cases, next actions and hearings from the case tracker, grouped as overdue, due today, coming up and later, plus the recently resolved |
| Assistant | Full-page chat in English or Arabic, with cited sources and the steps Ferrero took |
| Documents | The document sync: searchable files, scans read by text recognition (with confidence) or waiting for it, password-protected files, with reasons |
| Document viewer | A document's indexed text by section; for scans, each page image beside its recognised text and per-page confidence |
| Dashboards | The Superset dashboards (D1–D4, DS-1) embedded with guest tokens, one tab each; see "Superset dashboards" below. Without a Superset account: plain frames from `FERRERO_SUPERSET_DASHBOARDS`, or the planned D1–D4 set |

The signed-in user's role applies everywhere: KPIs, charts, cases, documents, evidence, reminders and Ferrero's answers. The account menu at the bottom of the sidebar shows what the user can see, and offers "Change password", "Switch account" and "Sign out". The bell in the top bar holds the user's reminders. A light and a dark theme are available. Deep links of the form `/?case=TM-2024-428` (from Power BI or Superset) open the case with Ferrero beside it.

```powershell
cd frontend
npm install
npm run build   # production build into src/ferrero/web/dist
npm run dev     # http://localhost:5173 with hot reload; /api is proxied to python -m ferrero.web on :8000
```

### Design

The look is set in one place, `frontend/src/index.css`: deep navy for the navigation and the public pages' panels, one blue for everything interactive (the primary action, links, the active page, the current step, citations), and white cards on a cool grey page, each with a dark-theme counterpart. Titles use the Fraunces serif, everything else Inter (IBM Plex Sans Arabic for Arabic); all three are bundled, so nothing is fetched from a font service.

- **Changing the palette** means changing the values in that file only. Components use the names (`brand`, `accent`, `primary`, `surface`, `ink`, the state tones), never a colour of their own; the two exceptions are the mark and the avatar tints.
- **State** has four tones (good, warning, critical, info), each with an ink, a soft fill and a line, and is never colour alone: a state always carries an icon or a dot and a label. Text pairs meet WCAG AA (4.5:1) in both themes.
- **Shared pieces** are in `frontend/src/components/ui.tsx` (cards, buttons, filters, tags, state pills, avatars, figure strips, tabs, notices) and `forms.tsx`; pages are built from these, so a change there carries everywhere.
- **The mark** (`components/Brand.tsx`) is original artwork: a white serif "F" in a blue seal. To use the organisation's own logo, replace the `Monogram` there; the browser-tab icon is in `frontend/index.html`.
- The page itself is served with `Cache-Control: no-cache`, so a new build shows on the next visit without a hard refresh.

Charts follow the dataviz rules:
- the palette is validated against the app's surfaces, in light and dark;
- bars are at most 24px thick, with hairline grids;
- every multi-series chart has a legend;
- every chart has a table view and hover or focus tooltips.

### Superset dashboards

The Dashboards page embeds the Superset dashboards whose title contains "Ferrero" (`Ferrero · D1 Legal Case Overview` … `Ferrero · DS-1 Case Detail`) with Superset's embedded SDK. The browser never signs in to Superset: for each dashboard it asks `POST /api/dashboards/guest-token`, and the backend (`ferrero.web.superset`) signs in with the account in `.env` and asks Superset for a guest token limited to that dashboard. The token carries row rules built from the signed-in user's role, the same rules as everywhere else in Ferrero:
- datasets with a `country` column: only the countries the user may see (listed positively, so an unknown country stays hidden);
- datasets with only a `case_id`: only the user's cases;
- document datasets: no rows for roles without documents (Procurement).

Signing in as someone else re-embeds the dashboard with a new token. "Case dashboard" on a case page opens DS-1 limited to that case (`/dashboards?d=DS-1&case=TM-2024-428`).

Set up:
1. In `.env`: `FERRERO_SUPERSET_URL`, `FERRERO_SUPERSET_USERNAME`, `FERRERO_SUPERSET_PASSWORD`. The account needs "can grant guest token on SecurityRestApi" (Admin has it). Ferrero turns on "Embed dashboard" for any matching dashboard that lacks it (`FERRERO_SUPERSET_AUTO_EMBED=false` to stop that).
2. Superset needs the `EMBEDDED_SUPERSET` feature flag (on at http://13.206.33.195:8088, version 6.1), and its `GUEST_ROLE_NAME` role needs read access to the Ferrero datasets, or the charts show a permission error.
3. Check the connection: `.venv\Scripts\python -m ferrero.web.superset` signs in, lists the dashboards (turning embedding on where needed), checks framing for `http://localhost:<FERRERO_PORT>` and issues one guest token, printing OK or FAILED with the reason for each step. A restricted user never gets a token for a dashboard whose datasets Superset won't list, because its row rules couldn't be built.
4. Superset only lets the sites in its `frame-ancestors` list embed it. That server allows `http://localhost:8090`, so `.env` sets `FERRERO_PORT=8090` and `start.cmd` opens http://localhost:8090. To use another address, add it to `TALISMAN_CONFIG["content_security_policy"]["frame-ancestors"]` in `superset_config.py`. When the address isn't allowed, the page says which addresses are.

**Note for this machine:** its Windows Application Control policy blocks the native Rolldown (Vite 8) and Rollup bundler binaries. The build therefore uses Vite 7 with Rollup's official WebAssembly build, set by the `overrides` entry in `package.json`. esbuild, Tailwind and LightningCSS run natively. On an unrestricted machine the override can be dropped.

## Case records: updates, evidence, follow-ups and the audit trail

The pack's CSVs stay the read-only baseline. What users change or add is stored in `data/records/` (`FERRERO_RECORDS_DIR`) and laid over the pack, so the case pages, the KPIs, the Follow-ups page and Ferrero's answers all show the current state at once.

| Feature | What it does |
|---|---|
| **Registering a case** | "Register a case" on the Overview or the Cases page: the mark infringed, the infringer (on record, or new), the country, how it was reported, the owner and the first action; optionally the court, the amount claimed and the commercial sensitivity assessment. The case gets the next number for its year (TM-2026-435 after the pack's TM-2026-434), starts at Intake, and is stored in `registered_cases` (new infringers in `registered_infringers`); later changes go through the same rules as any case. Users can register only in the countries their role covers. |
| **Workflow** | The Overview shows the four steps (register, assign, follow up, close) with what is waiting at each, then the user's deadlines. Each case has a workflow bar with Reassign, Add follow-up and Close case. A new owner, by registration or reassignment, gets a "Case assigned to you" notification. The Cases list has an Owner filter (My cases) and opens filtered from `?stage=Intake` or `?owner=me`. |
| **Trademark comparison** | On the *Trademark comparison* tab: the registered mark's specimen (`src/ferrero/web/marks/MK-0n.png`, drawn by `scripts/make_mark_specimens.py`; replace them with the certificate images) beside a photo of the product from the case's evidence, indicative similarity of the sign on the product to the mark (`records/similarity.py`: letters different, sounds alike, contains the mark; Arabic signs against the Arabic name), and a recorded assessment: visual, phonetic and conceptual similarity, goods, likelihood of confusion, notes. A new assessment supersedes the last (kept as history, in `mark_comparisons`); each goes in the audit trail. |
| **Photos and evidence** | On a case's *Evidence & documents* tab: drag and drop or choose files, or take a photo on a phone. Categories: product photo, screenshot, cease-and-desist letter, correspondence with authorities, invoice, external counsel document, other evidence. Each item has a title, the date it was taken or dated, where it was found, and notes. Photos show in a gallery and open in a viewer; PDFs preview in place. |
| **Evidence integrity** | Accepted: photos (JPEG, PNG, WebP, GIF, HEIC), PDF, Word, Excel, PowerPoint, e-mails (.msg, .eml), text and CSV, up to 25 MB (`FERRERO_EVIDENCE_MAX_MB`). A file is accepted only if its content matches its extension, so a web page renamed `.jpg` is refused. Files are stored exactly as uploaded, named by their SHA-256, read-only and never deleted. The fingerprint goes into the audit trail, and "Check the file is unchanged" re-verifies it. Withdrawing an item (with a reason) takes it out of the case's evidence but keeps the file and its history. The same file can't be added to a case twice. |
| **Follow-ups and reminders** | On the *Follow-ups* tab: a deadline, given as a start date plus the days allowed (for example a store given 30 days to remove infringing products) or as a date, with an owner (the case owner by default) and a reminder. The owner is reminded before it (7 days by default) and told when it is reached, to follow up and decide; if no decision is recorded 3 days later, Legal Operations is told as well (`FERRERO_REMINDER_LEAD_DAYS`, `FERRERO_ESCALATE_DAYS`). The decision is one of: complied, close the case (with its outcome); done, keep the case open; not complied, escalate (with the next step and, optionally, a new stage); no longer needed. A deadline can be moved, with a reason. The case tracker's next actions and hearings are reminded the same way, to the case's lead counsel. |
| **Notifications** | Under the bell in the top bar: each user's reminders, checked when the app starts, every 15 minutes (`FERRERO_REMINDER_MINUTES`) and after every change. Each reminder is sent once, and only to people who can open the case; a decided follow-up or a closed case clears its reminders. E-mail copies are optional: set `FERRERO_SMTP_HOST` (see `.env.example`). |
| **Commercial sensitivity** | On the case's Overview: business priority (High / Medium / Low), whether the business must be consulted before enforcement (Yes / No), the commercial relationship with the infringer (customer, distributor or reseller, commercial partner, supplier), the consultation's status (not started, in progress, cleared to proceed, hold enforcement), the business contact and notes. While consultation is required and not cleared, the case shows a banner, and moving it into an enforcement stage (notice sent, filed, hearing, judgment, appeal) is refused unless the user gives a reason to go ahead, which is recorded as *enforcement without business clearance*. The Cases list filters on these fields. |
| **Audit trail** | On the *Audit trail* tab: every change to a case (its fields, evidence, follow-ups and decisions) with who made it, their role, when (UTC), each field before and after, and the reason. Entries can't be changed or deleted (SQLite triggers refuse it), and each entry's SHA-256 covers the one before it, so an edited, removed or reordered entry fails the tamper check shown on the tab. "Download CSV" exports one row per changed field. |

**Who may do what:** Legal-UAE, Legal-KSA, Legal-MENA, Legal-Ops and Leadership may update the cases they can see. Evidence follows the document rules: Procurement sees neither the evidence nor the evidence entries in the audit trail, and can't change anything. The owner of a case or follow-up must be able to see that case.

**Dates:** deadlines and "today" follow the app's date, like everything else: the real date, or the fixed one when `FERRERO_DEMO_TODAY` is set (see "The date" under "Assistant"). Audit and upload times are always the real time. To show a deadline being reached, give a follow-up a start date 30 days in the past, with 30 days to act.

**Ferrero (the assistant)** sees the same records: `get_case` returns the business assessment, the follow-ups and the evidence list, and `query_case_data` has the new columns on `fact_case` plus the tables `case_follow_up`, `case_evidence` (metadata only), `case_audit` and `case_mark_comparison`; registered cases are in `fact_case` like the pack's. When consultation is required and not cleared, Ferrero says so whenever it discusses enforcement steps on the case.

```powershell
.venv\Scripts\python -m ferrero.records status      # what the store holds
.venv\Scripts\python -m ferrero.records verify      # audit chain, and every evidence file against its fingerprint
.venv\Scripts\python -m ferrero.records reminders   # create the reminders due (--email also sends them, --date tests a day)
```

`data/records/` is users' data, not derived data: it is never rebuilt, it is left out of git (`.gitignore`) and of the Docker image (`.dockerignore`), and on a server it lives in a Docker volume. Deleting the folder resets every case to the pack's data.

## Signing in

Every page except the landing page and the sign-in page needs a signed-in user, and so does every API call.

- **Accounts** are the people in the user directory (`dim_user`), the platform administrator, and the people the administrator adds; the sign-in name is the e-mail address (the user id, such as `U-08`, also works). Their role, and so what they can see and change, comes from their Entra group as before.
- **Platform administrator:** `admin@ferrero.com` (`FERRERO_ADMIN_EMAIL`), user `U-00`, signs in with `FERRERO_PASSWORD` (also read as `FERRERO_ADMIN_PASSWORD`), which lives only in the server's `.env` and can't be changed in the portal. The administrator sees every case and document and may change cases, but owns none. The **Users** page (`/admin/users`) adds people (name, work e-mail, job title, role, country, temporary password), changes added people's details and role, sets temporary passwords for anyone (they are asked to change them at the next sign-in), and turns access off and on (a disabled account is signed out at once and can't sign in, own cases or receive reminders; its history stays). Added people live in `directory_users`, disabled accounts in `disabled_users`, and every administrative action in `admin_log`, all in `auth.sqlite`.
- **Switch user:** from the account menu or the Users page, the administrator views the portal exactly as another user does: same cases, documents, follow-ups and Overview. A banner shows whose view it is, with the way back. Changes made meanwhile are recorded in the audit trail as "Platform Administrator as Lina Mansour"; administration and password changes are unavailable until the administrator switches back.
- **Passwords:** someone's own password, or a temporary one the administrator gave them, applies first; otherwise the optional starting password `FERRERO_DEMO_PASSWORD`. Without any of these the account can't sign in; there is no built-in password. Passwords are stored only as salted scrypt hashes in `data/records/auth.sqlite`. A new password needs at least 10 characters and can't contain the person's name or e-mail address; changing it signs the person out everywhere else.
- **Sessions:** an HttpOnly cookie holding a random token (only its SHA-256 is stored). A session ends after 12 hours without activity (`FERRERO_SESSION_HOURS`), or 14 days with "keep me signed in" (`FERRERO_SESSION_REMEMBER_DAYS`), on sign-out, or when the password changes. When a session ends, the next click leads back to the sign-in page, and then to where the user was.
- **Protection:** five wrong passwords for a name lock it for 15 minutes, and an unknown name gets the same answer as a wrong password. Every sign-in attempt is logged (`sign_ins` in `auth.sqlite`). Requests that change something must carry the `X-Ferrero` header, which other websites can't add, so a page elsewhere can't act with a signed-in user's cookie.
- **Test accounts:** for a test environment, `FERRERO_LOGIN_SHOW_ACCOUNTS=true` lists the accounts on the sign-in page, which fills in the e-mail address when one is picked. Off by default.

```powershell
.venv\Scripts\python -m ferrero.auth accounts             # everyone with an account: role, password state, access, last sign-in
.venv\Scripts\python -m ferrero.auth set-password U-08    # set someone's password (asked for twice)
.venv\Scripts\python -m ferrero.auth reset U-08           # back to the starting password
.venv\Scripts\python -m ferrero.auth sign-out             # end every session (or: sign-out U-08)
```

For single sign-on later (Microsoft Entra ID), validate the identity provider's token in `current_principal` (`ferrero/web/app.py`) and map its group claims to `security.ROLES`; the rest of the app already takes the user from there.

## Evaluation

```powershell
.venv\Scripts\python -m ferrero.eval            # all 30 golden questions + 3 access probes (asks to confirm)
.venv\Scripts\python -m ferrero.eval --ids GS-001,GS-027 --yes
```

Each question runs in a fresh conversation as U-08 (Legal-Ops, who sees everything). The code checks the route (documents or case tracker), the expected source file, the answer language, and, for the probes, that nothing restricted leaks. A Claude judge with a structured-output schema then compares each answer with the reference. Reports are written to `data/eval/`.

`src/ferrero/eval/overrides.json` corrects two golden rows: GS-017's reference is only a routing note, and GS-028 has a tie. Every run calls the API and is billed to your account.

## Configuration

See `.env.example`. Real environment variables take precedence over `.env`.

| Variable | Default | |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | Claude API key (first-party) |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BEDROCK_MODEL_ID` | – | Claude on Amazon Bedrock |
| `FERRERO_MODEL` / `FERRERO_EFFORT` | `claude-opus-5-5` (or `BEDROCK_MODEL_ID`) / `medium` | model and effort (`low` … `max`) |
| `FERRERO_DEMO_TODAY` | unset: the real date | a fixed "today", e.g. `2026-11-05` for a demonstration on the sample data |
| `FERRERO_TIMEZONE` | unset: the server's time zone | whose midnight starts a new day, e.g. `Asia/Dubai` |
| `FERRERO_LLM_PROVIDER` | detected from the credentials present | `anthropic`, `bedrock` or `foundry` |
| `FERRERO_FALLBACK_MODEL` | Foundry `claude-opus-4-8`, Bedrock none | client-side refusal fallback |
| `FERRERO_PACK_DIR`, `FERRERO_DATA_DIR` | `docs/Ferrero_Demo_Pack`, `data` | input pack and generated data |
| `FERRERO_SP_*` | – | SharePoint sync (tenant, client id/secret, hostname, site, library) |
| `FERRERO_DOCUMENTS_DIR` | `documents_full` (once built), else `documents_150`, else `documents` | folder the local sync and OCR read (its `<folder>_meta/manifest.csv` is used automatically) |
| `FERRERO_SUPERSET_URL`, `_USERNAME`, `_PASSWORD` | – | Superset server and the account that grants guest tokens (embedded dashboards) |
| `FERRERO_SUPERSET_TITLE`, `_AUTO_EMBED`, `_ALLOWED_DOMAINS`, `_AUTH_PROVIDER` | `Ferrero`, `true`, any, `db` | which dashboards, whether Ferrero turns embedding on, embed domains, login provider |
| `FERRERO_SUPERSET_DASHBOARDS` | – | fallback without an account: `Title\|URL;Title\|URL` shown in plain frames |
| `FERRERO_PORT` | `8000` | web app port (`start.cmd` opens http://localhost:&lt;port&gt;) |
| `FERRERO_DEMO_PASSWORD` | – | starting password for every account without its own; without it, only people with their own password can sign in |
| `FERRERO_SESSION_HOURS` / `FERRERO_SESSION_REMEMBER_DAYS` | `12` / `14` | a session ends after this long without activity (with "keep me signed in": days) |
| `FERRERO_LOGIN_SHOW_ACCOUNTS` | `false` | list the accounts on the sign-in page (test environments) |
| `FERRERO_COOKIE_SECURE` | `auto` | Secure flag on the session cookie: `auto` sets it when the page is served over HTTPS |
| `FERRERO_RECORDS_DIR` | `data/records` | case records: changes, evidence files, follow-ups, notifications, audit trail |
| `FERRERO_EVIDENCE_MAX_MB` | `25` | largest evidence file accepted |
| `FERRERO_REMINDER_MINUTES` / `FERRERO_REMINDER_LEAD_DAYS` / `FERRERO_ESCALATE_DAYS` | `15` / `7` / `3` | how often deadlines are checked; how far ahead "due soon" is sent; days after a deadline before Legal Operations is told |
| `FERRERO_SMTP_HOST`, `_PORT`, `_SECURITY`, `_USERNAME`, `_PASSWORD`, `_FROM` | – | e-mail copies of reminders (optional) |
| `FERRERO_NOTIFY_EMAIL_TO`, `FERRERO_PUBLIC_URL` | – | send every reminder e-mail to one mailbox (demo, test); the address used in e-mail links |
| `FERRERO_OCR_ENGINE` | `auto` | `auto` (the server if `FERRERO_OCR_URL` is set, else cached results only), `server`, `local`, `off` |
| `FERRERO_OCR_URL` | – | OpenAI-compatible endpoint serving `baidu/Unlimited-OCR-2` |
| `FERRERO_OCR_MODEL_DIR` / `FERRERO_OCR_MODE` | `models/Unlimited-OCR-2` / `gundam` | local model folder; `gundam` reads the page plus detail tiles (the model's default), `base` the page only (faster) |
| `FERRERO_OCR_EXPERTS` | `auto` | local engine on a CPU: `ram`, `mapped` or `int8` (see "Memory" above); `auto` picks `mapped` when less than 8 GB is free |
| `FERRERO_OCR_MIN_CONFIDENCE` / `FERRERO_OCR_REVIEW_CONFIDENCE` | `0.80` / `0.90` | below the first a scan is not indexed; pages below the second are flagged for review |

## Known limits and next steps

- **Text recognition on a CPU is slow** (minutes per page; much slower when the machine is short of memory). For production, serve Unlimited-OCR-2 on a GPU (`FERRERO_OCR_URL`), where a page takes seconds. Confidence is the model's own token probability: calibrate the two thresholds on a sample of real scans.
- **Case records:**
  - The Superset dashboards read their own copy of the pack's data, so they don't show changes made in Ferrero (registered cases, closed cases, business priority, follow-ups). Ferrero's own pages and KPIs do; a registered case has no "Case dashboard" button.
  - The text of uploaded evidence isn't indexed for Ferrero's document search yet: Ferrero sees the evidence list, not the files' contents.
  - Photos are shown from the original files (no thumbnails), which is fine for tens of photos per case.
- **Search** is SQLite full-text with a light Arabic stemmer. For production, use Azure AI Search with the same fields, an Arabic analyzer, vectors and a security filter on `access_group`.
- Conversations are kept in memory: a restart forgets them, and the page starts a new one.
- **Data-pack defects** stay as they are, and the assistant reports disagreements between sources:
  - `fact_case_event` dates contradict several documents;
  - TM-2024-409's takedown notice disagrees with `fact_appstore`;
  - the DAX measures use `TODAY()` rather than the frozen demo date;
  - three KPI tiles have no measure.

## Layout

```
src/ferrero/
  config.py, security.py, textproc.py, casemodel.py   settings, roles, bilingual text handling, case tracker
  sync/      sources (folder, SharePoint), extract, chunker, index, runner, cli
  ocr/       text recognition for scans: Unlimited-OCR-2 in-process (local) or served (server), output parsing, cache, cli
  assistant/ tools, prompts, agent (Claude tool loop, conversations)
  auth/      signing in: passwords (scrypt), sessions, lockout, cli
  records/   case records: store and audit trail, evidence files, field rules, reminders, e-mail, service, cli
  web/       FastAPI app + static chat page
  eval/      golden-set runner, overrides, cli
tests/       offline tests (fake Messages API, mocked Graph, fake OCR engine; test_ocr_local.py runs in .venv-ocr)
docs/        the data pack (input; never modified)
models/      Unlimited-OCR-2 weights and code (downloaded; not in git)
copilot_studio/   assets for the optional Copilot Studio version (kept separate from this build)
```
