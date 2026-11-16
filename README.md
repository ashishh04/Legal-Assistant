# Ferrero case intelligence: document sync and assistant

The AI part of the Ferrero case-intelligence demo (spec and data in `docs/Ferrero_Demo_Pack`):

- **Document sync** (`python -m ferrero.sync`) takes case documents from a folder or from SharePoint, ties each one to its case, and indexes it for search under that case's access group.
- **Ferrero assistant** (`python -m ferrero.web`) answers questions in English or Arabic. It draws on the case documents (with citations) and on the case tracker, which holds the same data as the Power BI dashboards. It only ever sees what the signed-in user may see.
- **Evaluation** (`python -m ferrero.eval`) scores the assistant on the pack's golden set, plus a few access-control probes.

All data is fictional. "Dolce Group International S.A." stands in for the customer's legal entity.

## Quick start (Windows)

Double-click **`start.cmd`**. On first run it creates the Python environment and indexes the documents; then it starts the app and opens http://127.0.0.1:8000. Close the window to stop it.

Or step by step in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env                 # then put your ANTHROPIC_API_KEY in .env
.venv\Scripts\python -m ferrero.sync   # index docs\Ferrero_Demo_Pack\documents
.venv\Scripts\python -m ferrero.web    # open http://127.0.0.1:8000
.venv\Scripts\python -m pytest         # 67 offline tests; no API key or network needed
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
- **No sign-in yet:** anyone who can reach the port can pick any persona and use the assistant, which is billed to the AWS account in `.env`. Until Entra ID sign-in replaces the persona picker, limit the port to known addresses in the server's firewall or security group.

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

**Demo identity:** the web page lets you pick one of the ten `dim_user` personas, and each conversation is bound to the user who started it. This is for the demo only. Before anyone else can reach the app, replace it with Entra ID sign-in: validate the token and map its group claims to `security.ROLES`. The server listens on 127.0.0.1 by default.

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
- The system prompt and the tool list never change during a conversation. Per-user context (who is asking, and the case opened from Power BI) goes into one appended `system` message. Conversations live on the server and are only ever appended to, which keeps the prompt cache warm and Claude's thinking valid across turns. A failed turn is rolled back, so the user can simply resend.
- Document passages are returned as `search_result` blocks, so every claim from a document carries a citation to the exact paragraph. The UI lists each citation with the quoted text and its SharePoint path.
- The demo date is fixed at 5 November 2026 (`FERRERO_DEMO_TODAY`), matching the notebook's `DEMO_TODAY`. SQL uses `demo_today()`, so "next 30 days" matches the golden set.
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

`frontend/` is a React 19 + TypeScript + Tailwind 4 app (Vite 7). `npm run build` writes it into `src/ferrero/web/dist`, and `python -m ferrero.web` serves it at http://127.0.0.1:8000. The original single-file chat page is still at `/classic`.

| Page | What it shows |
|---|---|
| Overview | KPI row (open cases, hearings in 30 days, overdue actions, recovery and win rates, legal spend); open cases by stage and country; amounts by year; outcomes; upcoming hearings with an "Ask" per case. One filter row scopes the page. |
| Cases | Searchable, sortable case tracker with stage, outcome, next step and overdue flags |
| Case detail (DS-1) | Facts, amounts in local currency and AED, next step, timeline, documents with their sync status, counsel spend, "Ask Ferrero about this case" |
| Assistant | Full-page chat in English or Arabic, with cited sources and the steps Ferrero took |
| Documents | The document sync: searchable files, scans read by text recognition (with confidence) or waiting for it, password-protected files, with reasons |
| Document viewer | A document's indexed text by section; for scans, each page image beside its recognised text and per-page confidence |
| Dashboards | The Superset dashboards (D1–D4, DS-1) embedded with guest tokens, one tab each; see "Superset dashboards" below. Without a Superset account: plain frames from `FERRERO_SUPERSET_DASHBOARDS`, or the planned D1–D4 set |

The persona switcher at the bottom of the sidebar applies the access rules everywhere: KPIs, charts, cases, documents and Ferrero's answers. A light and a dark theme are available. Deep links of the form `/?case=TM-2024-428` (from Power BI or Superset) open the case with Ferrero beside it.

```powershell
cd frontend
npm install
npm run build   # production build into src/ferrero/web/dist
npm run dev     # http://localhost:5173 with hot reload; /api is proxied to python -m ferrero.web on :8000
```

Charts follow the dataviz rules:
- the palette is validated against the app's surfaces, in light and dark;
- bars are at most 24px thick, with hairline grids;
- every multi-series chart has a legend;
- every chart has a table view and hover or focus tooltips.

### Superset dashboards

The Dashboards page embeds the Superset dashboards whose title contains "Ferrero" (`Ferrero · D1 Legal Case Overview` … `Ferrero · DS-1 Case Detail`) with Superset's embedded SDK. The browser never signs in to Superset: for each dashboard it asks `POST /api/dashboards/guest-token`, and the backend (`ferrero.web.superset`) signs in with the account in `.env` and asks Superset for a guest token limited to that dashboard. The token carries row rules built from the persona's role, the same rules as everywhere else in Ferrero:
- datasets with a `country` column: only the countries the persona may see (listed positively, so an unknown country stays hidden);
- datasets with only a `case_id`: only the persona's cases;
- document datasets: no rows for roles without documents (Procurement).

Switching persona re-embeds the dashboard with a new token. "Case dashboard" on a case page opens DS-1 limited to that case (`/dashboards?d=DS-1&case=TM-2024-428`).

Set up:
1. In `.env`: `FERRERO_SUPERSET_URL`, `FERRERO_SUPERSET_USERNAME`, `FERRERO_SUPERSET_PASSWORD`. The account needs "can grant guest token on SecurityRestApi" (Admin has it). Ferrero turns on "Embed dashboard" for any matching dashboard that lacks it (`FERRERO_SUPERSET_AUTO_EMBED=false` to stop that).
2. Superset needs the `EMBEDDED_SUPERSET` feature flag (on at http://13.206.33.195:8088, version 6.1), and its `GUEST_ROLE_NAME` role needs read access to the Ferrero datasets, or the charts show a permission error.
3. Check the connection: `.venv\Scripts\python -m ferrero.web.superset` signs in, lists the dashboards (turning embedding on where needed), checks framing for `http://localhost:<FERRERO_PORT>` and issues one guest token, printing OK or FAILED with the reason for each step. A restricted persona never gets a token for a dashboard whose datasets Superset won't list, because its row rules couldn't be built.
4. Superset only lets the sites in its `frame-ancestors` list embed it. That server allows `http://localhost:8090`, so `.env` sets `FERRERO_PORT=8090` and `start.cmd` opens http://localhost:8090. To use another address, add it to `TALISMAN_CONFIG["content_security_policy"]["frame-ancestors"]` in `superset_config.py`. When the address isn't allowed, the page says which addresses are.

**Note for this machine:** its Windows Application Control policy blocks the native Rolldown (Vite 8) and Rollup bundler binaries. The build therefore uses Vite 7 with Rollup's official WebAssembly build, set by the `overrides` entry in `package.json`. esbuild, Tailwind and LightningCSS run natively. On an unrestricted machine the override can be dropped.

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
| `FERRERO_DEMO_TODAY` | `2026-11-05` | frozen "today" |
| `FERRERO_LLM_PROVIDER` | detected from the credentials present | `anthropic`, `bedrock` or `foundry` |
| `FERRERO_FALLBACK_MODEL` | Foundry `claude-opus-4-8`, Bedrock none | client-side refusal fallback |
| `FERRERO_PACK_DIR`, `FERRERO_DATA_DIR` | `docs/Ferrero_Demo_Pack`, `data` | input pack and generated data |
| `FERRERO_SP_*` | – | SharePoint sync (tenant, client id/secret, hostname, site, library) |
| `FERRERO_DOCUMENTS_DIR` | `documents_full` (once built), else `documents_150`, else `documents` | folder the local sync and OCR read (its `<folder>_meta/manifest.csv` is used automatically) |
| `FERRERO_SUPERSET_URL`, `_USERNAME`, `_PASSWORD` | – | Superset server and the account that grants guest tokens (embedded dashboards) |
| `FERRERO_SUPERSET_TITLE`, `_AUTO_EMBED`, `_ALLOWED_DOMAINS`, `_AUTH_PROVIDER` | `Ferrero`, `true`, any, `db` | which dashboards, whether Ferrero turns embedding on, embed domains, login provider |
| `FERRERO_SUPERSET_DASHBOARDS` | – | fallback without an account: `Title\|URL;Title\|URL` shown in plain frames |
| `FERRERO_PORT` | `8000` | web app port (`start.cmd` opens http://localhost:&lt;port&gt;) |
| `FERRERO_OCR_ENGINE` | `auto` | `auto` (the server if `FERRERO_OCR_URL` is set, else cached results only), `server`, `local`, `off` |
| `FERRERO_OCR_URL` | – | OpenAI-compatible endpoint serving `baidu/Unlimited-OCR-2` |
| `FERRERO_OCR_MODEL_DIR` / `FERRERO_OCR_MODE` | `models/Unlimited-OCR-2` / `gundam` | local model folder; `gundam` reads the page plus detail tiles (the model's default), `base` the page only (faster) |
| `FERRERO_OCR_EXPERTS` | `auto` | local engine on a CPU: `ram`, `mapped` or `int8` (see "Memory" above); `auto` picks `mapped` when less than 8 GB is free |
| `FERRERO_OCR_MIN_CONFIDENCE` / `FERRERO_OCR_REVIEW_CONFIDENCE` | `0.80` / `0.90` | below the first a scan is not indexed; pages below the second are flagged for review |

## Known limits and next steps

- **Text recognition on a CPU is slow** (minutes per page; much slower when the machine is short of memory). For production, serve Unlimited-OCR-2 on a GPU (`FERRERO_OCR_URL`), where a page takes seconds. Confidence is the model's own token probability: calibrate the two thresholds on a sample of real scans.
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
  web/       FastAPI app + static chat page
  eval/      golden-set runner, overrides, cli
tests/       offline tests (fake Messages API, mocked Graph, fake OCR engine; test_ocr_local.py runs in .venv-ocr)
docs/        the data pack (input; never modified)
models/      Unlimited-OCR-2 weights and code (downloaded; not in git)
copilot_studio/   assets for the optional Copilot Studio version (kept separate from this build)
```
