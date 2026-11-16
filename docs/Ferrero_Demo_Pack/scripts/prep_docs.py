"""Select the cases that get full sample documents, emit docs_spec.json for the docx builder,
align fact_document rows with the real files, and build the golden set."""
import pandas as pd, json, random, datetime as dt
random.seed(7)
OUT = 'out'
c = pd.read_csv(f'{OUT}/csv/fact_case.csv', parse_dates=['opened_date', 'closed_date', 'next_hearing_date', 'next_action_due', 'last_action_date'])
marks = pd.read_csv(f'{OUT}/csv/dim_mark.csv').set_index('mark_id')
courts = pd.read_csv(f'{OUT}/csv/dim_court.csv').set_index('court_id')
inf = pd.read_csv(f'{OUT}/csv/dim_infringer.csv').set_index('infringer_id')
users = pd.read_csv(f'{OUT}/csv/dim_user.csv').set_index('user_id')
docs = pd.read_csv(f'{OUT}/csv/fact_document.csv')
CLAIMANT = {'en': 'Dolce Group International S.A.', 'ar': 'شركة دولتشي جروب إنترناشيونال'}
CUR_AR = {'AED': 'درهم إماراتي', 'SAR': 'ريال سعودي', 'EGP': 'جنيه مصري', 'JOD': 'دينار أردني', 'KWD': 'دينار كويتي', 'QAR': 'ريال قطري', 'OMR': 'ريال عماني', 'TRY': 'ليرة تركية', 'INR': 'روبية هندية'}
COURT_CASES = {'CT-01', 'CT-02', 'CT-05', 'CT-06', 'CT-08', 'CT-09', 'CT-10', 'CT-11', 'CT-12', 'CT-13', 'CT-14', 'CT-15'}
used = set()
def sel(mask, name):
    pool = c[mask & ~c.case_id.isin(used)]
    assert len(pool), name
    r = pool.iloc[0]; used.add(r.case_id); return r

S = {}
S['judgment_en_won'] = sel((c.outcome == 'Won') & (c.country == 'UAE') & c.court_id.isin(['CT-01', 'CT-02', 'CT-05']) & c.case_type.str.startswith(('Trademark infringement', 'Packaging', 'Unfair')), 'judgment_en_won')
S['judgment_ar_ksa'] = sel(c.outcome.isin(['Won', 'Partially won']) & (c.country == 'KSA') & c.court_id.isin(['CT-06', 'CT-08']), 'judgment_ar_ksa')
S['judgment_en_lost'] = sel((c.outcome == 'Lost') & (c.country == 'UAE') & c.court_id.isin(['CT-01', 'CT-02', 'CT-05']), 'judgment_en_lost')
S['settlement_en'] = sel((c.outcome == 'Settled') & (c.country == 'UAE') & c.court_id.isin(['CT-01', 'CT-02', 'CT-05']) & c.external_firm.notna(), 'settlement_en')
S['cease_desist_en'] = sel((c.stage == 'Notice sent') & (c.country == 'UAE'), 'cease_desist_en')
S['cease_desist_ar'] = sel((c.country == 'Egypt') & c.case_type.str.startswith('Trademark infringement'), 'cease_desist_ar')
S['customs_ar'] = sel((c.case_type == 'Customs seizure') & (c.status == 'Closed'), 'customs_ar')
S['investigation_en'] = sel((c.country == 'UAE') & c.stage.isin(['Investigation', 'Filed', 'Hearing']) & c.case_type.isin(['Trademark infringement – counterfeit goods', 'Online marketplace listing']), 'investigation_en')
S['licence_en'] = sel((c.case_type == 'Parallel import / grey market'), 'licence_en')
S['claim_en'] = sel((c.country == 'UAE') & c.stage.isin(['Hearing', 'Filed']) & c.court_id.isin(['CT-01', 'CT-02', 'CT-05']), 'claim_en')
S['takedown_en'] = sel((c.case_type == 'Mobile app infringement') & (c.status == 'Closed'), 'takedown_en')
S['tm_office_ar'] = sel((c.case_type == 'Trademark opposition / cancellation') & (c.outcome == 'Won'), 'tm_office_ar')

def fmt(n): return f'{int(n):,}'
def dstr(x): return '' if pd.isna(x) else pd.Timestamp(x).strftime('%d %B %Y')
AR_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
def dar(x):
    if pd.isna(x): return ''
    t = pd.Timestamp(x); return f'{t.day} {AR_MONTHS[t.month - 1]} {t.year}'
PRODUCT_AR = {'Hazelnut spread': 'كريمة البندق القابلة للدهن', 'Wafer bars': 'ألواح الويفر', 'Boxed pralines': 'علب البرالين', 'Mints and chewing gum': 'النعناع والعلكة',
              'Children’s chocolate treats with toy': 'حلوى الشوكولاتة للأطفال مع لعبة', 'Gold-wrapped hazelnut chocolates': 'شوكولاتة البندق بالغلاف الذهبي'}
def diso(x): return '' if pd.isna(x) else pd.Timestamp(x).strftime('%Y-%m-%d')
spec = {'claimant': CLAIMANT, 'docs': []}
DOC_META = {  # key: (doc_type in fact_document, language, file stem, pages)
    'judgment_en_won': ('Judgment', 'EN', 'Judgment', 3), 'judgment_ar_ksa': ('Judgment', 'AR', 'Judgment', 3), 'judgment_en_lost': ('Judgment', 'EN', 'Judgment', 2),
    'settlement_en': ('Settlement agreement', 'EN', 'Settlement_Agreement', 3), 'cease_desist_en': ('Cease-and-desist letter', 'EN', 'Cease_and_Desist', 2),
    'cease_desist_ar': ('Cease-and-desist letter', 'AR', 'Cease_and_Desist', 2), 'customs_ar': ('Customs seizure notice', 'AR', 'Customs_Seizure_Notice', 1),
    'investigation_en': ('Investigation report', 'EN', 'Investigation_Report', 3), 'licence_en': ('Licence agreement', 'EN', 'Licence_Agreement', 3),
    'claim_en': ('Statement of claim', 'EN', 'Statement_of_Claim', 3), 'takedown_en': ('Takedown notice', 'EN', 'Takedown_Notice', 1),
    'tm_office_ar': ('Trademark office decision', 'AR', 'Trademark_Office_Decision', 2),
}
for key, r in S.items():
    dtype, lang, stem, pages = DOC_META[key]
    m = marks.loc[r.mark_id]; i = inf.loc[r.infringer_id]; ct = courts.loc[r.court_id]; u = users.loc[r.lead_counsel_id]
    end = r.closed_date if not pd.isna(r.closed_date) else pd.Timestamp('2026-11-05')
    if dtype in ('Judgment', 'Trademark office decision', 'Settlement agreement'): doc_date = end
    elif dtype == 'Cease-and-desist letter': doc_date = r.opened_date + pd.Timedelta(days=random.randint(10, 30))
    elif dtype == 'Statement of claim': doc_date = r.opened_date + pd.Timedelta(days=random.randint(40, 90))
    else: doc_date = r.opened_date + pd.Timedelta(days=random.randint(5, 25))
    if key == 'licence_en': doc_date = r.opened_date - pd.Timedelta(days=730)
    if doc_date > end: doc_date = end
    court_ref = f'{random.randint(180, 2900)}/{doc_date.year}'
    fname = f'{r.case_id}_{stem}_{lang}.docx'
    d = dict(key=key, doc_type=dtype, language=lang, file=fname, pages=pages, case_id=r.case_id, title=r.title, case_type=r.case_type, country=r.country,
             court_en=ct.court_name_en, court_ar=ct.court_name_ar, court_city=ct.city, court_ref=court_ref, mark=m.mark_name, mark_ar=m.mark_name_ar,
             mark_reg=m.uae_registration_no, mark_class=str(m.nice_classes), mark_product=m.product_category, infringer=i.infringer_name_en, infringer_ar=i.infringer_name_ar,
             infringer_type=i.infringer_type, infringer_city=i.city, lead_counsel=u.full_name, lead_title=u.job_title, firm=(r.external_firm if isinstance(r.external_firm, str) else ''),
             currency=r.currency, currency_ar=CUR_AR[r.currency], claim_local=fmt(r.claim_amount_local), claim_aed=fmt(r.claim_amount_aed), awarded_local=fmt(r.awarded_amount_local),
             awarded_aed=fmt(r.awarded_amount_aed), settlement_local=fmt(r.settlement_amount_local), settlement_aed=fmt(r.settlement_amount_aed),
             opened=dstr(r.opened_date), closed=dstr(r.closed_date), doc_date=dstr(doc_date), doc_date_iso=diso(doc_date), next_hearing=dstr(r.next_hearing_date),
             opened_ar=dar(r.opened_date), doc_date_ar=dar(doc_date), mark_product_ar=PRODUCT_AR[m.product_category],
             stage=r.stage, outcome=r.outcome, status=r.status, sharepoint=r.sharepoint_library, access_group=r.access_group, sensitivity=r.sensitivity,
             seized_units=random.choice([1200, 3600, 8400, 14500, 22000]), test_units=random.choice([3, 5, 8, 12]), unit_price=random.choice([9, 12, 15, 18, 24]))
    spec['docs'].append(d)
    # align fact_document: replace one row of the same case+type, else append
    mask = (docs.case_id == r.case_id) & (docs.doc_type == dtype)
    row = dict(case_id=r.case_id, doc_type=dtype, doc_type_ar=docs[docs.doc_type == dtype].doc_type_ar.iloc[0], title=fname, language=lang, doc_date=diso(doc_date), pages=pages,
               scanned=False, ocr_confidence=None, sensitivity=r.sensitivity, access_group=r.access_group, library_path=f'{r.sharepoint_library}/{fname}', index_status='Indexed',
               skip_reason='', chunks=pages * 5, sample_file=True)
    if mask.any():
        idx = docs[mask].index[0]
        for k, v in row.items(): docs.at[idx, k] = v
    else:
        row['doc_id'] = f'DOC-{len(docs) + 1:04d}'; docs = pd.concat([docs, pd.DataFrame([row])], ignore_index=True)
docs['sample_file'] = docs['sample_file'].fillna(False).astype(bool)
docs.to_csv(f'{OUT}/csv/fact_document.csv', index=False)
json.dump(spec, open(f'{OUT}/docs_spec.json', 'w'), ensure_ascii=False, indent=1)

# ---------------- golden set ----------------
def D(k): return next(x for x in spec['docs'] if x['key'] == k)
g = []
j = D('judgment_en_won')
g += [('documents', 'EN', f"What damages were awarded in {j['case_id']}?", f"{j['currency']} {j['awarded_local']} in compensation, per the judgment of {j['court_en']} dated {j['doc_date']} (operative part).", j['file'], 'Operative part'),
      ('documents', 'AR', f"ما مبلغ التعويض المحكوم به في القضية {j['case_id']}؟", f"{j['awarded_local']} {j['currency_ar']} بموجب حكم {j['court_ar']} بتاريخ {j['doc_date']} (منطوق الحكم).", j['file'], 'Operative part'),
      ('documents', 'EN', f"Who was the defendant in {j['case_id']} and what was the claim amount?", f"{j['infringer']}; the claim was {j['currency']} {j['claim_local']}.", j['file'], 'Parties / Facts')]
j = D('judgment_ar_ksa')
g += [('documents', 'AR', f"ما الذي قضت به المحكمة التجارية في القضية {j['case_id']}؟", f"الحكم لصالح المدعية بتعويض قدره {j['awarded_local']} {j['currency_ar']} ومنع المدعى عليها {j['infringer_ar']} من استخدام العلامة {j['mark_ar']}.", j['file'], 'منطوق الحكم'),
      ('documents', 'EN', f"What was the outcome of {j['case_id']} in Saudi Arabia?", f"{j['outcome']}: {j['court_en']} awarded {j['currency']} {j['awarded_local']} and ordered {j['infringer']} to cease use of the {j['mark']} mark (judgment dated {j['doc_date']}).", j['file'], 'Operative part')]
j = D('judgment_en_lost')
g += [('documents', 'EN', f"Why was the claim in {j['case_id']} dismissed?", f"The court found insufficient evidence that the defendant targeted UAE consumers and dismissed the claim; each party bore its own costs (judgment dated {j['doc_date']}).", j['file'], 'Reasoning'),
      ('documents', 'EN', f"Compare the outcomes of {D('judgment_en_won')['case_id']} and {j['case_id']}.", f"{D('judgment_en_won')['case_id']}: won, {D('judgment_en_won')['currency']} {D('judgment_en_won')['awarded_local']} awarded. {j['case_id']}: lost, claim dismissed for insufficient evidence of targeting UAE consumers.", f"{D('judgment_en_won')['file']}; {j['file']}", 'Operative parts')]
j = D('settlement_en')
g += [('documents', 'EN', f"What were the settlement terms in {j['case_id']}?", f"{j['infringer']} pays {j['currency']} {j['settlement_local']} in two instalments, destroys remaining stock under supervision, and undertakes not to use the {j['mark']} mark; the claimant withdraws the case on receipt of the final instalment.", j['file'], 'Clause 2–4'),
      ('documents', 'AR', f"ما شروط التسوية في القضية {j['case_id']}؟", f"يدفع {j['infringer_ar']} مبلغ {j['settlement_local']} {j['currency_ar']} على قسطين، ويتلف المخزون المتبقي تحت الإشراف، ويتعهد بعدم استخدام العلامة {j['mark_ar']}.", j['file'], 'البند 2–4')]
j = D('cease_desist_en')
g += [('documents', 'EN', f"What deadline did the cease-and-desist letter in {j['case_id']} set?", f"14 days from the date of the letter ({j['doc_date']}) to cease use, provide sales figures and sign the undertaking.", j['file'], 'Demands'),
      ('documents', 'EN', f"Which trademark registration is cited in the {j['case_id']} notice?", f"{j['mark']}, UAE registration {j['mark_reg']}, class {j['mark_class']}.", j['file'], 'Rights')]
j = D('cease_desist_ar')
g += [('documents', 'AR', f"ما المهلة الممنوحة في الإنذار القانوني في القضية {j['case_id']}؟", f"خمسة عشر يوماً من تاريخ الإنذار ({j['doc_date']}) للتوقف عن الاستيراد والبيع وتقديم تعهد كتابي.", j['file'], 'المطالب'),
      ('documents', 'EN', f"Who sent the cease-and-desist letter in {j['case_id']}?", f"{j['firm']} on behalf of {CLAIMANT['en']}, dated {j['doc_date']}.", j['file'], 'Header')]
j = D('customs_ar')
g += [('documents', 'AR', f"كم عدد الوحدات المحجوزة في القضية {j['case_id']}؟", f"{j['seized_units']:,} وحدة تحمل العلامة {j['mark_ar']}، بموجب إخطار {j['court_ar']} بتاريخ {j['doc_date']}.", j['file'], 'تفاصيل الحجز'),
      ('documents', 'EN', f"What did Dubai Customs seize in {j['case_id']} and what was the estimated value?", f"{j['seized_units']:,} units bearing the {j['mark']} mark imported by {j['infringer']}; estimated value {j['currency']} {j['claim_local']}.", j['file'], 'Seizure details')]
j = D('investigation_en')
g += [('documents', 'EN', f"What did the test purchase in {j['case_id']} find?", f"{j['test_units']} units bought from {j['infringer']} at {j['currency']} {j['unit_price']} each; all failed the authentication checklist (hologram, batch code, packaging print).", j['file'], 'Findings'),
      ('analytics', 'EN', f"What is the next action on {j['case_id']}?", "Routed to the case model: next action and due date from the case tracker.", 'fact_case', '')]
j = D('licence_en')
g += [('documents', 'EN', f"What territory does the licence agreement in {j['case_id']} cover?", f"The United Arab Emirates only; sales outside the territory are a material breach (clause 3).", j['file'], 'Clause 3'),
      ('documents', 'EN', f"What is the royalty rate in the {j['mark']} licence agreement?", "4.5% of net sales, payable quarterly (clause 6).", j['file'], 'Clause 6')]
j = D('claim_en')
g += [('documents', 'EN', f"What relief is sought in the statement of claim for {j['case_id']}?", f"Compensation of {j['currency']} {j['claim_local']}, an injunction, destruction of infringing goods, publication of the judgment and costs.", j['file'], 'Relief sought'),
      ('documents', 'AR', f"ما المبلغ المطالب به في صحيفة الدعوى في القضية {j['case_id']}؟", f"{j['claim_local']} {j['currency_ar']} تعويضاً، مع المنع والإتلاف والنشر والرسوم.", j['file'], 'الطلبات')]
j = D('takedown_en')
g += [('documents', 'EN', f"Which app was reported in {j['case_id']} and on which store?", f"An app by {j['infringer']} using the {j['mark']} mark, reported to Google Play on {j['doc_date']}.", j['file'], 'Notice')]
j = D('tm_office_ar')
g += [('documents', 'AR', f"ما قرار إدارة العلامات التجارية في القضية {j['case_id']}؟", f"قبول الاعتراض ورفض تسجيل العلامة المتعارضة المقدمة من {j['infringer_ar']} لتشابهها مع العلامة {j['mark_ar']}.", j['file'], 'القرار'),
      ('documents', 'EN', f"What was decided in the trademark opposition {j['case_id']}?", f"The opposition was upheld and the conflicting application by {j['infringer']} was refused for similarity with {j['mark']} (decision dated {j['doc_date']}).", j['file'], 'Decision')]
# refusal and analytics checks
g += [('documents', 'EN', 'What is the claim amount in case TM-2023-150?', 'Refusal: no such case in the files available to the reader.', '', ''),
      ('documents', 'EN', 'What is the weather in Dubai today?', 'Refusal: off-topic; the case files cannot answer.', '', ''),
      ('analytics', 'EN', 'How many open cases do we have in KSA?', f"{int(((c.status == 'Open') & (c.country == 'KSA')).sum())} open cases (case model).", 'fact_case', ''),
      ('analytics', 'EN', 'Which infringer has the most cases?', f"{inf.sort_values('case_count', ascending=False).iloc[0].infringer_name_en} ({int(inf.case_count.max())} cases).", 'dim_infringer', ''),
      ('analytics', 'AR', 'كم عدد القضايا المفتوحة التي لها جلسة خلال الثلاثين يوماً القادمة؟', f"{int(((c.status == 'Open') & (c.next_hearing_date <= pd.Timestamp('2026-12-05'))).sum())} قضية (نموذج القضايا).", 'fact_case', ''),
      ('analytics', 'EN', 'Total damages awarded in 2025?', f"AED {fmt(c[(c.closed_date.dt.year == 2025)].awarded_amount_aed.sum())} across cases closed in 2025 (case model).", 'fact_case', '')]
golden = pd.DataFrame([dict(gs_id=f'GS-{i+1:03d}', route=a, language=b, question=q, expected_answer=ans, source=src, section=sec) for i, (a, b, q, ans, src, sec) in enumerate(g)])
golden.to_csv(f'{OUT}/csv/golden_set.csv', index=False)
print(len(spec['docs']), 'documents specified;', len(golden), 'golden-set questions')
for x in spec['docs']: print(f"  {x['key']:18s} {x['case_id']}  {x['title'][:45]:45s} {x['country']:7s} {x['outcome']:17s} {x['file']}")
