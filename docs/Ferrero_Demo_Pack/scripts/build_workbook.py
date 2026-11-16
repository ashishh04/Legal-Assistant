import pandas as pd, numpy as np, datetime as dt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.comments import Comment
from specs import DASHBOARDS, SUBPAGES, DAX, RELATIONSHIPS, RLS

OUT = 'out'
PINK = 'D6297A'; DARK = '242831'; TINT = 'FFF1F6'; LIGHT = 'F4F5F7'
H_FONT = Font(name='Arial', bold=True, color='FFFFFF', size=10); B_FONT = Font(name='Arial', size=10)
T_FONT = Font(name='Arial', bold=True, size=14, color=DARK); S_FONT = Font(name='Arial', bold=True, size=11, color=PINK)
H_FILL = PatternFill('solid', fgColor=PINK); T_FILL = PatternFill('solid', fgColor=TINT)
thin = Side(style='thin', color='DADDE3'); BORDER = Border(top=thin, bottom=thin, left=thin, right=thin)

TABLES = ['dim_mark', 'dim_court', 'dim_infringer', 'dim_user', 'fact_case', 'fact_case_event', 'fact_document', 'fact_mailbox', 'fact_intake_form', 'fact_appstore', 'fact_invoice', 'golden_set']
DATE_COLS = {'opened_date', 'closed_date', 'next_hearing_date', 'next_action_due', 'last_action_date', 'event_date', 'doc_date', 'received_at', 'triaged_at', 'submitted_at',
             'detected_date', 'takedown_requested_date', 'removed_date', 'invoice_date', 'first_seen'}
AMOUNT_COLS = {'claim_amount_local', 'claim_amount_aed', 'awarded_amount_local', 'awarded_amount_aed', 'settlement_amount_local', 'settlement_amount_aed', 'recovered_amount_local',
               'recovered_amount_aed', 'external_fees_aed', 'amount_aed', 'legal_spend_aed', 'est_downloads', 'estimated_units'}
dfs = {t: pd.read_csv(f'{OUT}/csv/{t}.csv') for t in TABLES}
for t, df in dfs.items():
    for c in df.columns:
        if c in DATE_COLS: df[c] = pd.to_datetime(df[c], errors='coerce')
        elif df[c].dtype == object: df[c] = df[c].fillna('')

wb = Workbook(); wb.remove(wb.active)

def write_df(ws, df, start_row=1, table_name=None, style='TableStyleLight9'):
    cols = list(df.columns)
    for j, c in enumerate(cols, 1):
        cell = ws.cell(row=start_row, column=j, value=c); cell.font = H_FONT; cell.fill = H_FILL; cell.alignment = Alignment(vertical='center', wrap_text=False)
    for i, row in enumerate(df.itertuples(index=False), start_row + 1):
        for j, v in enumerate(row, 1):
            if isinstance(v, (pd.Timestamp, dt.datetime)):
                v = None if pd.isna(v) else v.to_pydatetime()
            elif isinstance(v, (np.integer,)): v = int(v)
            elif isinstance(v, (np.floating,)): v = None if np.isnan(v) else float(v)
            elif isinstance(v, (np.bool_,)): v = bool(v)
            elif isinstance(v, float) and np.isnan(v): v = None
            cell = ws.cell(row=i, column=j, value=v); cell.font = B_FONT
            name = cols[j - 1]
            if name in DATE_COLS and v is not None: cell.number_format = 'yyyy-mm-dd hh:mm' if name in ('received_at', 'triaged_at') else 'yyyy-mm-dd'
            elif name in AMOUNT_COLS: cell.number_format = '#,##0'
            elif name == 'ocr_confidence': cell.number_format = '0.00'
    for j, c in enumerate(cols, 1):
        width = max(len(str(c)), *(min(len(str(x)), 45) for x in df[c].astype(str).head(200))) + 2
        ws.column_dimensions[get_column_letter(j)].width = min(max(width, 9), 48)
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    if table_name:
        ref = f'A{start_row}:{get_column_letter(len(cols))}{start_row + len(df)}'
        tbl = Table(displayName=table_name, ref=ref); tbl.tableStyleInfo = TableStyleInfo(name=style, showRowStripes=True)
        ws.add_table(tbl)

def title(ws, text, sub=None, row=1):
    ws.cell(row=row, column=1, value=text).font = T_FONT
    if sub: ws.cell(row=row + 1, column=1, value=sub).font = Font(name='Arial', size=10, italic=True, color='5F6673')

# ---------------- README ----------------
ws = wb.create_sheet('README')
title(ws, 'Ferrero case-intelligence demo – data pack', 'Synthetic, internally consistent data for the Fabric lakehouse, the Power BI dashboards and the Ferrero assistant demo. Generated 5 Nov 2026.')
lines = [
 ('What this is', ''),
 ('', 'Every source the proposal names, as one consistent data model: case trackers, the infringement mailbox, intake forms, app-store monitoring, documents, events and external-counsel invoices. Amounts, dates and parties agree across tables, the twelve sample documents and the golden set, so a figure on a dashboard matches the answer Ferrero gives.'),
 ('All data is fictional', ''),
 ('', 'Marks (VELORA, CRISPINO, DOLCETTA, MINTIQ, PICCOLINI, AURELIA), parties, people, courts’ case numbers, amounts and outcomes are invented. “Dolce Group International S.A.” stands in for the customer’s legal entity. Swap in the real mark portfolio and entity names at kickoff; nothing else needs to change.'),
 ('Period and scale', ''),
 ('', 'January 2024 to October 2026 (today = 5 November 2026). 120 cases, 9 countries (UAE first), 6 marks, 45 infringers, 10 internal users in 6 Entra ID groups for the row-level-security demo.'),
 ('How to load into Fabric', ''),
 ('', '1. Create a Lakehouse in the demo workspace (F4 capacity). 2. Upload the csv/ folder to Files/ferrero_demo/csv. 3. Run notebook Ferrero_Demo_Load.ipynb: it writes one Delta table per CSV plus dim_date. 4. Build the semantic model from the Semantic_Model and DAX_Measures sheets, apply the RLS roles, and build the four dashboards from Dashboard_Specs. 5. Upload the documents/ folder to the SharePoint case libraries listed in fact_document[library_path] for the Ferrero document sync.'),
 ('Sheets', ''),
 ('', 'Summary – live counts and totals computed from the data sheets (formulas). Dashboard_Specs – the four demo dashboards and six drill-through pages. DAX_Measures – measures to paste into the semantic model. Semantic_Model – relationships and RLS roles. Data_Dictionary – every column. dim_* and fact_* – the data (Excel tables; identical to the CSVs). golden_set – 30 evaluation questions for the assistant.'),
 ('Legend', ''),
 ('', 'Pink header rows are data; no cells in the data sheets are meant to be edited by hand (regenerate with gen_data.py). The Summary sheet is formula-driven and recalculates if data changes.'),
 ('Conventions', ''),
 ('', 'Local-currency amounts are the source of truth, rounded to the nearest thousand; AED columns are converted at fixed demo rates (SAR 0.98, EGP 0.075, JOD 5.18, KWD 11.95, QAR 1.01, OMR 9.54, TRY 0.11, INR 0.044). Case IDs follow the pilot format TM-YYYY-NNN. access_group is the Entra ID group that may open the case and its documents.'),
]
r = 4
for h, body in lines:
    if h: ws.cell(row=r, column=1, value=h).font = S_FONT
    else:
        c = ws.cell(row=r, column=1, value=body); c.font = B_FONT; c.alignment = Alignment(wrap_text=True, vertical='top'); ws.row_dimensions[r].height = 15 * (len(body) // 120 + 1)
    r += 1
ws.column_dimensions['A'].width = 140
r += 1
ws.cell(row=r, column=1, value='Row counts (live)').font = S_FONT; r += 1
for t in TABLES:
    ws.cell(row=r, column=1, value=f'=CONCATENATE("{t}: ", COUNTA({t}!A:A)-1, " rows")').font = B_FONT; r += 1

# ---------------- data sheets ----------------
for t in TABLES:
    ws = wb.create_sheet(t); write_df(ws, dfs[t], table_name=f'tbl_{t}')

# ---------------- Summary (formulas) ----------------
ws = wb.create_sheet('Summary', 1)
title(ws, 'Summary – computed from the data sheets', 'All figures are formulas over fact_case, fact_mailbox, fact_document, fact_appstore and fact_invoice.')
fc = dfs['fact_case']; col = {c: get_column_letter(i + 1) for i, c in enumerate(fc.columns)}
fm = dfs['fact_mailbox']; mcol = {c: get_column_letter(i + 1) for i, c in enumerate(fm.columns)}
fd = dfs['fact_document']; dcol = {c: get_column_letter(i + 1) for i, c in enumerate(fd.columns)}
fa = dfs['fact_appstore']; acol = {c: get_column_letter(i + 1) for i, c in enumerate(fa.columns)}
fi = dfs['fact_invoice']; icol = {c: get_column_letter(i + 1) for i, c in enumerate(fi.columns)}
def rng(sheet, c): return f"{sheet}!${c}:${c}"
rows = [
 ('Cases', None),
 ('Total cases', f'=COUNTA({rng("fact_case", col["case_id"])})-1'),
 ('Open cases', f'=COUNTIF({rng("fact_case", col["status"])},"Open")'),
 ('Closed cases', f'=COUNTIF({rng("fact_case", col["status"])},"Closed")'),
 ('Open cases with a hearing in the next 30 days', f'=COUNTIFS({rng("fact_case", col["status"])},"Open",{rng("fact_case", col["next_hearing_date"])},">="&DATE(2026,11,5),{rng("fact_case", col["next_hearing_date"])},"<="&DATE(2026,12,5))'),
 ('Open cases with an overdue action', f'=COUNTIFS({rng("fact_case", col["status"])},"Open",{rng("fact_case", col["next_action_due"])},"<"&DATE(2026,11,5))'),
 ('Average days open (open cases)', f'=AVERAGEIFS({rng("fact_case", col["days_open"])},{rng("fact_case", col["status"])},"Open")'),
 ('Average days to close (closed cases)', f'=AVERAGEIFS({rng("fact_case", col["days_open"])},{rng("fact_case", col["status"])},"Closed")'),
 ('Amounts (AED)', None),
 ('Total claimed', f'=SUM({rng("fact_case", col["claim_amount_aed"])})'),
 ('Total awarded', f'=SUM({rng("fact_case", col["awarded_amount_aed"])})'),
 ('Total settled', f'=SUM({rng("fact_case", col["settlement_amount_aed"])})'),
 ('Total recovered', f'=SUM({rng("fact_case", col["recovered_amount_aed"])})'),
 ('Recovery rate (recovered / awarded + settled)', '=IFERROR(B16/(B14+B15),0)'),
 ('Legal spend (invoices)', f'=SUM({rng("fact_invoice", icol["amount_aed"])})'),
 ('Outcomes', None),
 ('Won', f'=COUNTIF({rng("fact_case", col["outcome"])},"Won")'),
 ('Partially won', f'=COUNTIF({rng("fact_case", col["outcome"])},"Partially won")'),
 ('Settled', f'=COUNTIF({rng("fact_case", col["outcome"])},"Settled")'),
 ('Takedown achieved', f'=COUNTIF({rng("fact_case", col["outcome"])},"Takedown achieved")'),
 ('Lost', f'=COUNTIF({rng("fact_case", col["outcome"])},"Lost")'),
 ('Withdrawn', f'=COUNTIF({rng("fact_case", col["outcome"])},"Withdrawn")'),
 ('Win rate (won + partially + settled + takedown) / decided', '=IFERROR((B20+B21+B22+B23)/(B20+B21+B22+B23+B24),0)'),
 ('Intake and triage', None),
 ('Mailbox reports', f'=COUNTA({rng("fact_mailbox", mcol["email_id"])})-1'),
 ('Reports linked to a case', f'=COUNTIF({rng("fact_mailbox", mcol["triage_status"])},"Linked to case")'),
 ('SLA breaches', f'=COUNTIF({rng("fact_mailbox", mcol["sla_breached"])},TRUE)'),
 ('App-store detections', f'=COUNTA({rng("fact_appstore", acol["app_id"])})-1'),
 ('Apps removed', f'=COUNTIF({rng("fact_appstore", acol["status"])},"Removed")'),
 ('Documents', None),
 ('Documents', f'=COUNTA({rng("fact_document", dcol["doc_id"])})-1'),
 ('Indexed (incl. flagged)', f'=COUNTIF({rng("fact_document", dcol["index_status"])},"Indexed*")'),
 ('Skipped', f'=COUNTIF({rng("fact_document", dcol["index_status"])},"Skipped")'),
 ('Arabic documents', f'=COUNTIF({rng("fact_document", dcol["language"])},"AR")'),
 ('Scanned documents (OCR)', f'=COUNTIF({rng("fact_document", dcol["scanned"])},TRUE)'),
]
r = 4
for label, f in rows:
    if f is None: ws.cell(row=r, column=1, value=label).font = S_FONT
    else:
        ws.cell(row=r, column=1, value=label).font = B_FONT
        c = ws.cell(row=r, column=2, value=f); c.font = B_FONT; c.number_format = '0.0%' if 'rate' in label.lower() else '#,##0'
    r += 1
ws.column_dimensions['A'].width = 52; ws.column_dimensions['B'].width = 16
# by-country block
r += 1; ws.cell(row=r, column=1, value='Cases by country').font = S_FONT; r += 1
for j, h in enumerate(['Country', 'Cases', 'Open', 'Claimed (AED)', 'Recovered (AED)'], 1):
    c = ws.cell(row=r, column=j, value=h); c.font = H_FONT; c.fill = H_FILL
r += 1
for country in ['UAE', 'KSA', 'Egypt', 'Jordan', 'Kuwait', 'Qatar', 'Oman', 'Turkey', 'India']:
    ws.cell(row=r, column=1, value=country).font = B_FONT
    ws.cell(row=r, column=2, value=f'=COUNTIF({rng("fact_case", col["country"])},A{r})').font = B_FONT
    ws.cell(row=r, column=3, value=f'=COUNTIFS({rng("fact_case", col["country"])},A{r},{rng("fact_case", col["status"])},"Open")').font = B_FONT
    c = ws.cell(row=r, column=4, value=f'=SUMIF({rng("fact_case", col["country"])},A{r},{rng("fact_case", col["claim_amount_aed"])})'); c.font = B_FONT; c.number_format = '#,##0'
    c = ws.cell(row=r, column=5, value=f'=SUMIF({rng("fact_case", col["country"])},A{r},{rng("fact_case", col["recovered_amount_aed"])})'); c.font = B_FONT; c.number_format = '#,##0'
    r += 1
for j in (3, 4, 5): ws.column_dimensions[get_column_letter(j)].width = 16

# ---------------- Dashboard specs ----------------
ws = wb.create_sheet('Dashboard_Specs', 2)
title(ws, 'Demo dashboards – four to build, six drill-through pages', 'D1 and D2 are the two main dashboards from the proposal; D3 and D4 are the two sub-dashboards that show the most in a demo. Pages and KPIs are indicative and agreed with the customer before kickoff.')
r = 4
for d in DASHBOARDS:
    ws.cell(row=r, column=1, value=f"{d['id']}  {d['name']}" + ('   (main dashboard)' if d['main'] else '   (sub-dashboard)')).font = Font(name='Arial', bold=True, size=12, color='FFFFFF')
    for j in range(1, 5): ws.cell(row=r, column=j).fill = H_FILL
    r += 1
    for label, val in [('Audience', d['audience']), ('Purpose', d['purpose']), ('Question it answers', d['question']), ('KPI tiles', ' · '.join(d['kpis'])),
                       ('Slicers', ', '.join(d['slicers'])), ('Drill-through', '; '.join(d['drill'])), ('Tables used', ', '.join(d['tables'])), ('Row-level security', d['rls']), ('Demo talking point', d['demo'])]:
        ws.cell(row=r, column=1, value=label).font = Font(name='Arial', bold=True, size=10, color=PINK)
        c = ws.cell(row=r, column=2, value=val); c.font = B_FONT; c.alignment = Alignment(wrap_text=True, vertical='top'); ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        ws.row_dimensions[r].height = 15 * (len(val) // 110 + 1); r += 1
    ws.cell(row=r, column=1, value='Visuals').font = Font(name='Arial', bold=True, size=10, color=PINK)
    for j, h in enumerate(['#', 'Visual', 'Type', 'Fields / measures'], 1):
        c = ws.cell(row=r, column=j, value=h if j > 1 else 'Visuals'); c.font = Font(name='Arial', bold=True, size=10, color=DARK); c.fill = T_FILL
    r += 1
    for k, (v, typ, fields) in enumerate(d['visuals'], 1):
        ws.cell(row=r, column=1, value=k).font = B_FONT; ws.cell(row=r, column=2, value=v).font = B_FONT; ws.cell(row=r, column=3, value=typ).font = B_FONT
        c = ws.cell(row=r, column=4, value=fields); c.font = B_FONT; c.alignment = Alignment(wrap_text=True); r += 1
    r += 1
ws.cell(row=r, column=1, value='Drill-through pages (the six sub-dashboards in the proposal)').font = S_FONT; r += 1
for j, h in enumerate(['ID', 'Page', 'Content'], 1):
    c = ws.cell(row=r, column=j, value=h); c.font = H_FONT; c.fill = H_FILL
r += 1
for sid, name, content in SUBPAGES:
    ws.cell(row=r, column=1, value=sid).font = B_FONT; ws.cell(row=r, column=2, value=name).font = B_FONT
    c = ws.cell(row=r, column=3, value=content); c.font = B_FONT; c.alignment = Alignment(wrap_text=True); ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4); r += 1
ws.column_dimensions['A'].width = 22; ws.column_dimensions['B'].width = 40; ws.column_dimensions['C'].width = 28; ws.column_dimensions['D'].width = 70

# ---------------- DAX ----------------
ws = wb.create_sheet('DAX_Measures', 3)
title(ws, 'DAX measures for the semantic model', 'Paste into a measure table named _Measures. dim_date is a standard date table marked as such; TODAY() can be replaced by a parameter for a frozen demo date (5 Nov 2026).')
write_df(ws, pd.DataFrame(DAX, columns=['Measure', 'DAX', 'Home table', 'Format', 'Used in']), start_row=4, table_name='tbl_dax')
ws.column_dimensions['A'].width = 26; ws.column_dimensions['B'].width = 120; ws.column_dimensions['C'].width = 16; ws.column_dimensions['D'].width = 10; ws.column_dimensions['E'].width = 14

# ---------------- Semantic model ----------------
ws = wb.create_sheet('Semantic_Model', 4)
title(ws, 'Semantic model – relationships and row-level security', 'Star schema around fact_case; dim_date spans 2024-01-01 to 2027-12-31 (created by the notebook).')
write_df(ws, pd.DataFrame(RELATIONSHIPS, columns=['From table', 'From column', 'To table', 'To column', 'Cardinality', 'Cross-filter', 'State']), start_row=4, table_name='tbl_rel')
r = 4 + len(RELATIONSHIPS) + 3
ws.cell(row=r, column=1, value='Row-level security roles (Entra ID group → DAX filter)').font = S_FONT; r += 1
for j, h in enumerate(['Role / Entra group', 'Table', 'Filter', 'Who'], 1):
    c = ws.cell(row=r, column=j, value=h); c.font = H_FONT; c.fill = H_FILL
r += 1
for role, tbl, flt, who in RLS:
    for j, v in enumerate([role, tbl, flt, who], 1): ws.cell(row=r, column=j, value=v).font = B_FONT
    r += 1
for j, w in enumerate([22, 18, 48, 48, 14, 14, 44], 1): ws.column_dimensions[get_column_letter(j)].width = w

# ---------------- Data dictionary ----------------
DD = {
 'dim_mark': {'mark_id': 'Mark key', 'mark_name': 'Fictional mark (Latin)', 'mark_name_ar': 'Mark in Arabic script', 'product_category': 'Product line', 'nice_classes': 'Nice classes', 'uae_registration_no': 'UAE registration number (fictional)', 'registered_in': 'Countries where registered'},
 'dim_court': {'court_id': 'Court key', 'country': 'Country', 'city': 'City', 'court_name_en': 'Court or authority (EN)', 'court_name_ar': 'Court or authority (AR)', 'court_type': 'Civil / specialised IP / administrative / customs', 'currency': 'Currency of amounts before that court'},
 'dim_infringer': {'infringer_id': 'Infringer key', 'infringer_name_en': 'Name (EN)', 'infringer_name_ar': 'Name (AR)', 'infringer_type': 'Distributor, Retailer, Online seller, Importer, App developer, Manufacturer, Domain registrant', 'country': 'Country', 'city': 'City', 'case_count': 'Cases against this party', 'repeat_offender': 'TRUE when 2 or more cases', 'first_seen': 'Date of first case'},
 'dim_user': {'user_id': 'User key', 'full_name': 'Name', 'job_title': 'Title', 'team': 'Team', 'country': 'Country', 'entra_group': 'Entra ID group used for RLS and document access', 'email': 'Demo e-mail'},
 'fact_case': {'case_id': 'TM-YYYY-NNN', 'title': 'Mark v. infringer', 'mark_id': '→ dim_mark', 'infringer_id': '→ dim_infringer', 'case_type': 'Enforcement route', 'country': 'Country', 'court_id': '→ dim_court', 'source_channel': 'How the case started', 'opened_date': 'Date opened', 'status': 'Open / Closed', 'stage': 'Intake → Investigation → Notice sent → Filed → Hearing → Judgment → Appeal → Settled → Closed', 'outcome': 'Won, Partially won, Settled, Takedown achieved, Lost, Withdrawn, Pending', 'closed_date': 'Date closed', 'priority': 'High / Medium / Low', 'risk_rating': 'Open cases only', 'lead_counsel_id': '→ dim_user', 'external_firm': 'External counsel (fictional)', 'currency': 'Local currency', 'claim_amount_local': 'Claim in local currency (source of truth)', 'claim_amount_aed': 'Claim converted to AED', 'awarded_amount_local': 'Awarded by judgment (local)', 'awarded_amount_aed': 'Awarded (AED)', 'settlement_amount_local': 'Settlement sum (local)', 'settlement_amount_aed': 'Settlement (AED)', 'recovered_amount_local': 'Cash actually recovered (local)', 'recovered_amount_aed': 'Recovered (AED)', 'next_hearing_date': 'Next hearing (open court cases)', 'next_action': 'Next step', 'next_action_due': 'Due date of next step', 'last_action_date': 'Last activity', 'language': 'Language of the file', 'sensitivity': 'Internal / Confidential / Restricted', 'access_group': 'Entra group that may open the case', 'sharepoint_library': 'Document library path', 'days_open': 'Days from opened to closed or today', 'legal_spend_aed': 'Sum of invoices', 'mark_name': 'Denormalised mark', 'infringer_name': 'Denormalised infringer', 'infringer_type': 'Denormalised type', 'court_name': 'Denormalised court', 'lead_counsel': 'Denormalised counsel'},
 'fact_case_event': {'event_id': 'Event key', 'case_id': '→ fact_case', 'event_date': 'Date', 'event_type': 'Case opened, Evidence collected, Hearing held, Judgment issued …', 'description': 'Text', 'owner_user_id': '→ dim_user', 'external_fees_aed': 'Fees attributable to the event'},
 'fact_document': {'doc_id': 'Document key', 'case_id': '→ fact_case', 'doc_type': 'Judgment, Cease-and-desist letter, …', 'doc_type_ar': 'Type in Arabic', 'title': 'File name', 'language': 'EN / AR', 'doc_date': 'Document date', 'pages': 'Pages', 'scanned': 'TRUE when image-only (OCR needed)', 'ocr_confidence': 'OCR confidence for scanned files', 'sensitivity': 'Sensitivity label', 'access_group': 'Entra group', 'library_path': 'SharePoint path', 'index_status': 'Indexed, Indexed (flagged), Skipped, Pending', 'skip_reason': 'Why skipped or flagged', 'chunks': 'Index chunks', 'sample_file': 'TRUE for the 12 files delivered in documents/'},
 'fact_mailbox': {'email_id': 'Email key', 'received_at': 'Received timestamp', 'reporter_type': 'Who reported', 'sender_domain': 'Sender domain', 'subject': 'Subject', 'country': 'Country', 'mark_id': '→ dim_mark', 'channel': 'Where the infringement was seen', 'triage_status': 'New, Triaged – monitoring, Triaged – no action, Dismissed, Duplicate, Linked to case', 'triaged_at': 'Triage timestamp', 'sla_hours': 'Triage SLA (48 h)', 'sla_breached': 'TRUE when triage exceeded SLA', 'linked_case_id': '→ fact_case when a case was opened', 'assigned_to': '→ dim_user'},
 'fact_intake_form': {'form_id': 'Form key', 'submitted_at': 'Date', 'submitter_team': 'Submitting team', 'mark_id': '→ dim_mark', 'country': 'Country', 'infringement_type': 'Type reported', 'evidence_files': 'Attachments', 'estimated_units': 'Units reported', 'status': 'Under review, Converted to case, Rejected, Merged, Monitoring', 'converted_case_id': '→ fact_case'},
 'fact_appstore': {'app_id': 'App key', 'store': 'Store', 'app_name': 'App name', 'developer': 'Developer', 'mark_id': '→ dim_mark', 'country': 'Store country', 'detected_date': 'Detected', 'status': 'Detected, Reported to store, Takedown requested, Removed, Rejected by store, Re-listed', 'takedown_requested_date': 'Takedown requested', 'removed_date': 'Removed', 'est_downloads': 'Estimated downloads', 'linked_case_id': '→ fact_case'},
 'fact_invoice': {'invoice_id': 'Invoice key', 'case_id': '→ fact_case', 'firm': 'External firm', 'invoice_date': 'Date', 'category': 'Counsel fees, Court fees, Investigation, Translation, Expert fees, Customs handling', 'amount_aed': 'Amount (AED)', 'status': 'Paid / Approved / Under review'},
 'golden_set': {'gs_id': 'Question key', 'route': 'documents (RAG) or analytics (case model)', 'language': 'EN / AR', 'question': 'Question', 'expected_answer': 'Expected answer', 'source': 'File or table', 'section': 'Section / page'},
}
rows = []
for t in TABLES:
    for c in dfs[t].columns:
        rows.append((t, c, str(dfs[t][c].dtype).replace('object', 'text').replace('datetime64[ns]', 'date').replace('int64', 'integer').replace('float64', 'number').replace('bool', 'boolean'), DD.get(t, {}).get(c, '')))
ws = wb.create_sheet('Data_Dictionary', 5)
title(ws, 'Data dictionary', 'One row per column; types as loaded into the lakehouse.')
write_df(ws, pd.DataFrame(rows, columns=['Table', 'Column', 'Type', 'Description']), start_row=4, table_name='tbl_dd')
ws.column_dimensions['A'].width = 20; ws.column_dimensions['B'].width = 28; ws.column_dimensions['C'].width = 12; ws.column_dimensions['D'].width = 90

wb.save(f'{OUT}/Ferrero_Demo_Data_Pack.xlsx')
print('saved workbook with sheets:', wb.sheetnames)
