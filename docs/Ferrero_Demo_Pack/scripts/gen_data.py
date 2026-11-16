"""Synthetic, internally consistent demo data for the Ferrero case-intelligence demo.
All marks, parties, people, courts' case numbers and amounts are fictional."""
import random, json, os, datetime as dt
import pandas as pd

random.seed(20261105)
TODAY = dt.date(2026, 11, 5)
OUT = 'out'; os.makedirs(f'{OUT}/csv', exist_ok=True)

def d(y, m, dd): return dt.date(y, m, dd)
def rand_date(a, b): return a + dt.timedelta(days=random.randint(0, (b - a).days))
def pick(seq, weights=None): return random.choices(seq, weights=weights, k=1)[0]

# ---------------- dimensions ----------------
marks = pd.DataFrame([
    ('MK-01', 'VELORA', 'فيلورا', 'Hazelnut spread', '30', 'UAE-TM-284517', 'UAE, KSA, Egypt, Jordan, Kuwait, Qatar, Oman, Turkey, India'),
    ('MK-02', 'CRISPINO', 'كريسبينو', 'Wafer bars', '30', 'UAE-TM-291044', 'UAE, KSA, Egypt, Kuwait, Qatar, Oman'),
    ('MK-03', 'DOLCETTA', 'دولتشيتا', 'Boxed pralines', '30', 'UAE-TM-276903', 'UAE, KSA, Egypt, Jordan, Kuwait, Qatar, Oman, Turkey, India'),
    ('MK-04', 'MINTIQ', 'مينتيك', 'Mints and chewing gum', '30', 'UAE-TM-302118', 'UAE, KSA, Egypt, Kuwait'),
    ('MK-05', 'PICCOLINI', 'بيكوليني', 'Children’s chocolate treats with toy', '28, 30', 'UAE-TM-298330', 'UAE, KSA, Egypt, Jordan, Kuwait, Qatar, Oman, Turkey'),
    ('MK-06', 'AURELIA', 'أوريليا', 'Gold-wrapped hazelnut chocolates', '30', 'UAE-TM-310472', 'UAE, KSA, Egypt, Jordan, Kuwait, Qatar, Oman, Turkey, India'),
], columns=['mark_id', 'mark_name', 'mark_name_ar', 'product_category', 'nice_classes', 'uae_registration_no', 'registered_in'])

courts = pd.DataFrame([
    ('CT-01', 'UAE', 'Dubai', 'Dubai Court of First Instance – Commercial', 'محكمة دبي الابتدائية – الدائرة التجارية', 'Civil / commercial court', 'AED'),
    ('CT-02', 'UAE', 'Abu Dhabi', 'Abu Dhabi Commercial Court', 'محكمة أبوظبي التجارية', 'Civil / commercial court', 'AED'),
    ('CT-03', 'UAE', 'Abu Dhabi', 'Ministry of Economy – Trademark Office', 'وزارة الاقتصاد – إدارة العلامات التجارية', 'Administrative (trademark office)', 'AED'),
    ('CT-04', 'UAE', 'Dubai', 'Dubai Customs – IPR Department', 'جمارك دبي – إدارة حقوق الملكية الفكرية', 'Customs', 'AED'),
    ('CT-05', 'UAE', 'Sharjah', 'Sharjah Federal Court of First Instance', 'محكمة الشارقة الاتحادية الابتدائية', 'Civil / commercial court', 'AED'),
    ('CT-06', 'KSA', 'Riyadh', 'Riyadh Commercial Court', 'المحكمة التجارية بالرياض', 'Civil / commercial court', 'SAR'),
    ('CT-07', 'KSA', 'Riyadh', 'Saudi Authority for Intellectual Property – Enforcement', 'الهيئة السعودية للملكية الفكرية – الإنفاذ', 'Administrative (IP authority)', 'SAR'),
    ('CT-08', 'KSA', 'Jeddah', 'Jeddah Commercial Court', 'المحكمة التجارية بجدة', 'Civil / commercial court', 'SAR'),
    ('CT-09', 'Egypt', 'Cairo', 'Cairo Economic Court', 'المحكمة الاقتصادية بالقاهرة', 'Civil / commercial court', 'EGP'),
    ('CT-10', 'Jordan', 'Amman', 'Amman Court of First Instance', 'محكمة بداية عمان', 'Civil / commercial court', 'JOD'),
    ('CT-11', 'Kuwait', 'Kuwait City', 'Kuwait Commercial Court', 'المحكمة التجارية بالكويت', 'Civil / commercial court', 'KWD'),
    ('CT-12', 'Qatar', 'Doha', 'Qatar Investment and Trade Court', 'محكمة الاستثمار والتجارة بقطر', 'Civil / commercial court', 'QAR'),
    ('CT-13', 'Oman', 'Muscat', 'Muscat Commercial Court', 'المحكمة التجارية بمسقط', 'Civil / commercial court', 'OMR'),
    ('CT-14', 'Turkey', 'Istanbul', 'Istanbul 1st Civil Court for Intellectual Property Rights', 'محكمة إسطنبول المدنية الأولى لحقوق الملكية الفكرية', 'Specialised IP court', 'TRY'),
    ('CT-15', 'India', 'New Delhi', 'Delhi High Court – IP Division', 'المحكمة العليا بدلهي – قسم الملكية الفكرية', 'Specialised IP court', 'INR'),
], columns=['court_id', 'country', 'city', 'court_name_en', 'court_name_ar', 'court_type', 'currency'])
FX = {'AED': 1.0, 'SAR': 0.98, 'EGP': 0.075, 'JOD': 5.18, 'KWD': 11.95, 'QAR': 1.01, 'OMR': 9.54, 'TRY': 0.11, 'INR': 0.044, 'USD': 3.67}
COUNTRY_W = {'UAE': 46, 'KSA': 18, 'Egypt': 8, 'Jordan': 5, 'Kuwait': 5, 'Qatar': 4, 'Oman': 4, 'Turkey': 5, 'India': 5}
ACCESS_BY_COUNTRY = {'UAE': 'Legal-UAE', 'KSA': 'Legal-KSA'}

users = pd.DataFrame([
    ('U-01', 'Mariam Al Suwaidi', 'Head of Legal', 'Leadership', 'UAE', 'Leadership', 'mariam.alsuwaidi@demo.local'),
    ('U-02', 'Daniel Weber', 'Regional General Counsel', 'Leadership', 'UAE', 'Leadership', 'daniel.weber@demo.local'),
    ('U-03', 'Khalid Rahman', 'Senior IP Counsel', 'IP', 'UAE', 'Legal-UAE', 'khalid.rahman@demo.local'),
    ('U-04', 'Sara Haddad', 'IP Counsel', 'IP', 'UAE', 'Legal-UAE', 'sara.haddad@demo.local'),
    ('U-05', 'Omar Al Qahtani', 'Litigation Counsel', 'Litigation', 'KSA', 'Legal-KSA', 'omar.alqahtani@demo.local'),
    ('U-06', 'Lina Mansour', 'Legal Counsel, MENA', 'Litigation', 'Egypt', 'Legal-MENA', 'lina.mansour@demo.local'),
    ('U-07', 'Youssef Nasser', 'Brand Protection Manager', 'Brand Protection', 'UAE', 'Legal-UAE', 'youssef.nasser@demo.local'),
    ('U-08', 'Priya Menon', 'Legal Operations Lead', 'Legal Operations', 'UAE', 'Legal-Ops', 'priya.menon@demo.local'),
    ('U-09', 'Ahmed Darwish', 'Paralegal', 'IP', 'UAE', 'Legal-UAE', 'ahmed.darwish@demo.local'),
    ('U-10', 'Noor Al Hashimi', 'Procurement Manager', 'Procurement', 'UAE', 'Procurement', 'noor.alhashimi@demo.local'),
], columns=['user_id', 'full_name', 'job_title', 'team', 'country', 'entra_group', 'email'])
LEAD_BY_COUNTRY = {'UAE': ['U-03', 'U-04', 'U-07'], 'KSA': ['U-05'], 'Egypt': ['U-06'], 'Jordan': ['U-06'], 'Kuwait': ['U-05', 'U-06'],
                   'Qatar': ['U-06', 'U-03'], 'Oman': ['U-06'], 'Turkey': ['U-06'], 'India': ['U-03', 'U-06']}
FIRMS = {'UAE': ['Gulf IP Partners', 'Najm & Co. Advocates'], 'KSA': ['Riyadh Law Chambers'], 'Egypt': ['Nile Counsel LLP'], 'Jordan': ['Levant Legal Group'],
         'Kuwait': ['Gulf IP Partners'], 'Qatar': ['Gulf IP Partners'], 'Oman': ['Najm & Co. Advocates'], 'Turkey': ['Bosphorus IP Law'], 'India': ['Indus Legal Associates']}

INFRINGERS = [
    ('Al Noor General Trading LLC', 'النور للتجارة العامة ذ.م.م', 'Distributor', 'UAE', 'Dubai'), ('Sweet Deals Foodstuff Trading', 'سويت ديلز لتجارة المواد الغذائية', 'Importer', 'UAE', 'Dubai'),
    ('Golden Taste Distribution FZE', 'جولدن تيست للتوزيع م.م.ح', 'Importer', 'UAE', 'Dubai'), ('Hazel Bite Foods LLC', 'هيزل بايت للأغذية ذ.م.م', 'Manufacturer', 'UAE', 'Sharjah'),
    ('Choco Palace Sweets', 'قصر الشوكولاتة للحلويات', 'Retailer', 'UAE', 'Abu Dhabi'), ('QuickCart Online Store', 'كويك كارت للتسوق الإلكتروني', 'Online seller', 'UAE', 'Dubai'),
    ('AppWorks Studio FZ-LLC', 'آب ووركس ستوديو', 'App developer', 'UAE', 'Dubai'), ('Dessert Kingdom Trading', 'مملكة الحلويات للتجارة', 'Retailer', 'UAE', 'Dubai'),
    ('Emirates Candy House', 'بيت الحلوى الإماراتي', 'Retailer', 'UAE', 'Ajman'), ('Bright Star Foodstuff LLC', 'النجم الساطع للمواد الغذائية', 'Distributor', 'UAE', 'Dubai'),
    ('Marina Gifts and Chocolates', 'مارينا للهدايا والشوكولاتة', 'Retailer', 'UAE', 'Dubai'), ('Zahrat Al Sahra Trading', 'زهرة الصحراء للتجارة', 'Importer', 'UAE', 'Sharjah'),
    ('Nutty Delight General Trading', 'ناتي ديلايت للتجارة العامة', 'Distributor', 'UAE', 'Dubai'), ('DealHub Marketplace Seller 4471', 'بائع ديل هب 4471', 'Online seller', 'UAE', 'Dubai'),
    ('Al Falah Sweets Factory', 'مصنع الفلاح للحلويات', 'Manufacturer', 'UAE', 'Ras Al Khaimah'), ('Pixel Fun Games Ltd', 'بيكسل فن للألعاب', 'App developer', 'UAE', 'Dubai'),
    ('Riyadh Sweets Trading Est.', 'مؤسسة حلويات الرياض التجارية', 'Distributor', 'KSA', 'Riyadh'), ('Al Majd Foodstuff Co.', 'شركة المجد للمواد الغذائية', 'Importer', 'KSA', 'Jeddah'),
    ('Najd Chocolate Factory', 'مصنع نجد للشوكولاتة', 'Manufacturer', 'KSA', 'Riyadh'), ('Souq Al Hala Online', 'سوق الحلا أونلاين', 'Online seller', 'KSA', 'Riyadh'),
    ('Dammam Sweet Corner', 'ركن الحلويات بالدمام', 'Retailer', 'KSA', 'Dammam'), ('Al Rawabi Trading Co.', 'شركة الروابي التجارية', 'Distributor', 'KSA', 'Jeddah'),
    ('Jeddah Candy Imports', 'جدة لاستيراد الحلوى', 'Importer', 'KSA', 'Jeddah'), ('Taif Nuts and Sweets', 'الطائف للمكسرات والحلويات', 'Retailer', 'KSA', 'Taif'),
    ('Nile Sweets Company', 'شركة حلويات النيل', 'Manufacturer', 'Egypt', 'Cairo'), ('Cairo Candy Distribution', 'القاهرة لتوزيع الحلوى', 'Distributor', 'Egypt', 'Cairo'),
    ('Alexandria Foods Import', 'الإسكندرية لاستيراد الأغذية', 'Importer', 'Egypt', 'Alexandria'), ('Giza Online Mart', 'الجيزة مارت أونلاين', 'Online seller', 'Egypt', 'Giza'),
    ('Amman Confectionery Co.', 'شركة عمان للحلويات', 'Manufacturer', 'Jordan', 'Amman'), ('Petra Sweets Trading', 'البتراء لتجارة الحلويات', 'Distributor', 'Jordan', 'Amman'),
    ('Kuwait Sweet Mart', 'الكويت سويت مارت', 'Retailer', 'Kuwait', 'Kuwait City'), ('Al Salmiya Foodstuff', 'السالمية للمواد الغذائية', 'Importer', 'Kuwait', 'Salmiya'),
    ('Doha Delights Trading', 'الدوحة ديلايتس للتجارة', 'Distributor', 'Qatar', 'Doha'), ('Pearl Sweets WLL', 'بيرل سويتس ذ.م.م', 'Retailer', 'Qatar', 'Doha'),
    ('Muscat Candy Traders', 'تجار الحلوى بمسقط', 'Distributor', 'Oman', 'Muscat'), ('Sohar Foods LLC', 'صحار للأغذية ش.م.م', 'Importer', 'Oman', 'Sohar'),
    ('Istanbul Şeker Gıda A.Ş.', 'اسطنبول شكر غيدا', 'Manufacturer', 'Turkey', 'Istanbul'), ('Bosphorus Sweets Ltd', 'بوسفور سويتس', 'Distributor', 'Turkey', 'Istanbul'),
    ('Anadolu Online Market', 'أناضول ماركت أونلاين', 'Online seller', 'Turkey', 'Ankara'), ('Delhi Confectioners Pvt Ltd', 'دلهي للحلويات المحدودة', 'Manufacturer', 'India', 'New Delhi'),
    ('Mumbai Sweet Traders', 'تجار الحلويات بمومباي', 'Distributor', 'India', 'Mumbai'), ('ChocoApp Technologies', 'تشوكو آب تكنولوجيز', 'App developer', 'India', 'Bangalore'),
    ('velora-outlet.shop (registrant)', 'مسجل نطاق velora-outlet.shop', 'Domain registrant', 'UAE', 'Unknown'), ('aurelia-gifts.store (registrant)', 'مسجل نطاق aurelia-gifts.store', 'Domain registrant', 'KSA', 'Unknown'),
    ('FunKids Apps SARL', 'فن كيدز آبس', 'App developer', 'Egypt', 'Cairo'),
]
infringers = pd.DataFrame([(f'INF-{i+1:03d}',) + t for i, t in enumerate(INFRINGERS)],
                          columns=['infringer_id', 'infringer_name_en', 'infringer_name_ar', 'infringer_type', 'country', 'city'])

CASE_TYPES = ['Trademark infringement – counterfeit goods', 'Customs seizure', 'Trademark opposition / cancellation', 'Domain name / cybersquatting',
              'Online marketplace listing', 'Mobile app infringement', 'Packaging imitation / passing off', 'Parallel import / grey market', 'Unfair competition']
CT_W = [30, 14, 8, 5, 14, 8, 10, 6, 5]
STAGES = ['Intake', 'Investigation', 'Notice sent', 'Filed', 'Hearing', 'Judgment', 'Appeal', 'Settled', 'Closed']
SOURCES = ['Infringement mailbox', 'Intake form', 'Customs notification', 'App store monitoring', 'Brand protection vendor', 'Distributor report']

def court_for(country, ctype):
    cc = courts[courts.country == country]
    if ctype == 'Customs seizure' and country == 'UAE': return 'CT-04'
    if ctype == 'Trademark opposition / cancellation':
        if country == 'UAE': return 'CT-03'
        if country == 'KSA': return 'CT-07'
    if ctype in ('Mobile app infringement', 'Domain name / cybersquatting', 'Online marketplace listing') and random.random() < 0.5:
        if country == 'UAE': return pick(['CT-03', 'CT-01'])
        if country == 'KSA': return 'CT-07'
    pool = cc[cc.court_type.str.startswith(('Civil', 'Specialised'))]
    return pick(list(pool.court_id))

def infringer_for(country, ctype):
    pool = infringers[infringers.country == country]
    if ctype == 'Mobile app infringement':
        p2 = pool[pool.infringer_type == 'App developer']
        if len(p2): pool = p2
        else: pool = infringers[infringers.infringer_type == 'App developer']
    elif ctype == 'Domain name / cybersquatting':
        p2 = infringers[infringers.infringer_type == 'Domain registrant']; pool = p2
    elif ctype == 'Online marketplace listing':
        p2 = pool[pool.infringer_type == 'Online seller']
        if len(p2) and random.random() < 0.7: pool = p2
    elif ctype in ('Customs seizure', 'Parallel import / grey market'):
        p2 = pool[pool.infringer_type.isin(['Importer', 'Distributor'])]
        if len(p2): pool = p2
    if ctype not in ('Mobile app infringement', 'Domain name / cybersquatting'):
        p2 = pool[~pool.infringer_type.isin(['App developer', 'Domain registrant'])]
        if len(p2): pool = p2
    return pick(list(pool.infringer_id))

# ---------------- cases ----------------
cases = []
seq = {2024: 400, 2025: 400, 2026: 400}
year_counts = {2024: 38, 2025: 48, 2026: 34}
for year, n in year_counts.items():
    for _ in range(n):
        seq[year] += 1
        cid = f'TM-{year}-{seq[year]}'
        start = d(year, 1, 1); end = d(year, 12, 31) if year < 2026 else d(2026, 10, 28)
        opened = rand_date(start, end)
        country = pick(list(COUNTRY_W), list(COUNTRY_W.values()))
        ctype = pick(CASE_TYPES, CT_W)
        if country != 'UAE' and ctype == 'Customs seizure': ctype = 'Trademark infringement – counterfeit goods'
        court = court_for(country, ctype)
        cur = courts.set_index('court_id').loc[court, 'currency']
        mark = pick(list(marks.mark_id), [30, 14, 18, 8, 16, 14])
        inf = infringer_for(country, ctype)
        src = {'Customs seizure': 'Customs notification', 'Mobile app infringement': 'App store monitoring'}.get(ctype) or pick(SOURCES, [34, 22, 4, 4, 24, 12])
        age_days = (TODAY - opened).days
        # closure probability grows with age
        p_closed = min(0.92, 0.05 + age_days / 650)
        closed = random.random() < p_closed
        if ctype == 'Customs seizure' and age_days > 240: closed = True
        admin = ctype in ('Customs seizure', 'Trademark opposition / cancellation', 'Domain name / cybersquatting', 'Online marketplace listing', 'Mobile app infringement')
        # claim amount
        if ctype in ('Customs seizure',): claim_aed = random.randint(40, 900) * 1000
        elif admin: claim_aed = 0 if random.random() < 0.6 else random.randint(50, 400) * 1000
        else: claim_aed = random.randint(150, 3500) * 1000
        if closed:
            dur = min(age_days - 1, int(random.gauss(300 if not admin else 120, 90)))
            dur = max(20, dur)
            closed_date = opened + dt.timedelta(days=dur)
            if ctype == 'Trademark opposition / cancellation': outcome = pick(['Won', 'Lost', 'Settled', 'Withdrawn'], [55, 20, 15, 10])
            elif admin: outcome = pick(['Takedown achieved', 'Won', 'Settled', 'Withdrawn', 'Lost'], [45, 25, 12, 10, 8])
            else: outcome = pick(['Won', 'Partially won', 'Settled', 'Lost', 'Withdrawn'], [38, 20, 24, 12, 6])
            stage = 'Settled' if outcome == 'Settled' else 'Closed'
            status = 'Closed'
        else:
            closed_date = None; outcome = 'Pending'; status = 'Open'
            if admin: stage = pick(['Intake', 'Investigation', 'Notice sent', 'Filed'], [10, 25, 35, 30])
            else:
                if age_days < 45: stage = pick(['Intake', 'Investigation', 'Notice sent'], [40, 40, 20])
                elif age_days < 150: stage = pick(['Investigation', 'Notice sent', 'Filed', 'Hearing'], [15, 30, 35, 20])
                else: stage = pick(['Filed', 'Hearing', 'Judgment', 'Appeal'], [20, 45, 20, 15])
        awarded = settlement = recovered = 0
        if outcome == 'Won': awarded = int(claim_aed * random.uniform(0.4, 0.9) // 1000 * 1000)
        elif outcome == 'Partially won': awarded = int(claim_aed * random.uniform(0.15, 0.45) // 1000 * 1000)
        elif outcome == 'Settled': settlement = int(max(claim_aed, 60000) * random.uniform(0.2, 0.6) // 1000 * 1000)
        if awarded: recovered = int(awarded * pick([0, 0.5, 1.0, random.uniform(0.2, 0.9)], [15, 20, 40, 25]) // 1000 * 1000)
        if settlement: recovered = int(settlement * pick([1.0, 0.5, 0.0], [70, 20, 10]))
        # local currency is the source of truth (rounded to thousands); AED is the converted figure
        def loc(a): return int(round(a / FX[cur], -3))
        claim_local, awarded_local, settlement_local, recovered_local = loc(claim_aed), loc(awarded), loc(settlement), loc(recovered)
        claim_aed, awarded, settlement, recovered = [int(round(v * FX[cur])) for v in (claim_local, awarded_local, settlement_local, recovered_local)]
        lead = pick(LEAD_BY_COUNTRY[country])
        firm = pick(FIRMS[country]) if (not admin or random.random() < 0.3) else ''
        priority = pick(['High', 'Medium', 'Low'], [25, 50, 25])
        risk = pick(['High', 'Medium', 'Low'], [20, 50, 30]) if status == 'Open' else ''
        lang = pick(['EN', 'AR', 'EN/AR'], [45, 30, 25]) if country in ('UAE', 'KSA', 'Egypt', 'Jordan', 'Kuwait', 'Qatar', 'Oman') else 'EN'
        access = ACCESS_BY_COUNTRY.get(country, 'Legal-MENA')
        sens = pick(['Confidential', 'Internal', 'Restricted'], [60, 25, 15])
        next_hearing = None; next_action = ''; next_due = None
        is_court = courts.set_index('court_id').loc[court, 'court_type'].startswith(('Civil', 'Specialised'))
        if status == 'Open':
            if stage == 'Filed' and not is_court:
                next_action = 'Await decision from the authority'; next_due = TODAY + dt.timedelta(days=random.randint(5, 45))
            elif stage in ('Filed', 'Hearing', 'Appeal'):
                next_hearing = TODAY + dt.timedelta(days=random.randint(3, 75))
                next_action = 'Prepare hearing bundle' if stage != 'Appeal' else 'File appeal submissions'
                next_due = next_hearing - dt.timedelta(days=5)
            elif stage == 'Notice sent':
                next_action = 'Follow up on cease-and-desist response'; next_due = TODAY + dt.timedelta(days=random.randint(-10, 20))
            elif stage == 'Investigation':
                next_action = 'Complete test purchase and evidence report'; next_due = TODAY + dt.timedelta(days=random.randint(-7, 25))
            elif stage == 'Intake':
                next_action = 'Triage and assign counsel'; next_due = TODAY + dt.timedelta(days=random.randint(-5, 7))
            elif stage == 'Judgment':
                next_action = 'Await judgment / assess appeal'; next_due = TODAY + dt.timedelta(days=random.randint(5, 40))
        last_action = closed_date if closed_date else TODAY - dt.timedelta(days=random.randint(0, 40))
        cases.append(dict(case_id=cid, title=f'{marks.set_index("mark_id").loc[mark, "mark_name"]} v. {infringers.set_index("infringer_id").loc[inf, "infringer_name_en"]}',
                          mark_id=mark, infringer_id=inf, case_type=ctype, country=country, court_id=court, source_channel=src,
                          opened_date=opened, status=status, stage=stage, outcome=outcome, closed_date=closed_date, priority=priority, risk_rating=risk,
                          lead_counsel_id=lead, external_firm=firm, currency=cur,
                          claim_amount_local=claim_local, claim_amount_aed=claim_aed, awarded_amount_local=awarded_local, awarded_amount_aed=awarded,
                          settlement_amount_local=settlement_local, settlement_amount_aed=settlement, recovered_amount_local=recovered_local, recovered_amount_aed=recovered, next_hearing_date=next_hearing, next_action=next_action, next_action_due=next_due,
                          last_action_date=last_action, language=lang, sensitivity=sens, access_group=access,
                          sharepoint_library=f'/sites/Legal/Cases/{country}/{cid}'))
cases = pd.DataFrame(cases).sort_values('opened_date').reset_index(drop=True)
# renumber per year in date order
counters = {}
for i, r in cases.iterrows():
    y = r.opened_date.year; counters[y] = counters.get(y, 400) + 1
    cases.at[i, 'case_id'] = f'TM-{y}-{counters[y]}'
    cases.at[i, 'sharepoint_library'] = f'/sites/Legal/Cases/{r.country}/TM-{y}-{counters[y]}'
# make ~12% of infringers repeat offenders by reassigning a few cases
special = ('Domain name / cybersquatting', 'Mobile app infringement')
rep = cases[~cases.case_type.isin(special)].sample(6, random_state=3).index
for i in rep:
    c = cases.loc[i]
    pool = cases[(cases.country == c.country) & (cases.index != i) & (~cases.case_type.isin(special))]
    if len(pool): cases.at[i, 'infringer_id'] = pool.sample(1, random_state=int(i)).iloc[0].infringer_id
for i, r in cases[cases.case_type == 'Domain name / cybersquatting'].iterrows():
    nm = infringers.set_index('infringer_id').loc[r.infringer_id, 'infringer_name_en'].lower()
    cases.at[i, 'mark_id'] = 'MK-01' if 'velora' in nm else 'MK-06'
cases['title'] = cases.apply(lambda r: f'{marks.set_index("mark_id").loc[r.mark_id, "mark_name"]} v. {infringers.set_index("infringer_id").loc[r.infringer_id, "infringer_name_en"]}', axis=1)
cases['days_open'] = cases.apply(lambda r: ((r.closed_date or TODAY) - r.opened_date).days, axis=1)

# ---------------- events ----------------
EVENT_FLOW = ['Case opened', 'Evidence collected', 'Test purchase completed', 'Cease-and-desist sent', 'Response received', 'Statement of claim filed',
              'Hearing held', 'Expert report filed', 'Judgment issued', 'Appeal filed', 'Settlement signed', 'Payment received', 'Takedown confirmed', 'Case closed']
events = []
eid = 0
for _, c in cases.iterrows():
    end = c.closed_date or TODAY
    n = random.randint(3, 9) if c.status == 'Closed' else random.randint(2, 6)
    flow = ['Case opened']
    pool = ['Evidence collected', 'Test purchase completed', 'Cease-and-desist sent', 'Response received']
    if c.stage in ('Filed', 'Hearing', 'Judgment', 'Appeal', 'Closed', 'Settled') and c.case_type not in ('Customs seizure',):
        pool += ['Statement of claim filed', 'Hearing held', 'Expert report filed']
    if c.outcome in ('Won', 'Partially won', 'Lost'): pool += ['Judgment issued']
    if c.outcome == 'Settled': pool += ['Settlement signed', 'Payment received']
    if c.outcome == 'Takedown achieved': pool += ['Takedown confirmed']
    if c.stage == 'Appeal': pool += ['Appeal filed']
    flow += [e for e in EVENT_FLOW if e in pool][: n - 1]
    if c.status == 'Closed': flow.append('Case closed')
    dates = sorted([c.opened_date] + [rand_date(c.opened_date, end) for _ in range(len(flow) - 1)])
    if c.status == 'Closed': dates[-1] = end
    for ev, dd in zip(flow, dates):
        eid += 1
        fee = 0
        if ev in ('Statement of claim filed', 'Hearing held', 'Expert report filed', 'Appeal filed'): fee = random.randint(8, 60) * 1000
        elif ev in ('Test purchase completed', 'Evidence collected'): fee = random.randint(2, 12) * 1000
        elif ev == 'Cease-and-desist sent': fee = random.randint(3, 9) * 1000
        events.append(dict(event_id=f'EV-{eid:05d}', case_id=c.case_id, event_date=dd, event_type=ev,
                           description=f'{ev} – {c.title}', owner_user_id=c.lead_counsel_id, external_fees_aed=fee))
events = pd.DataFrame(events)

# ---------------- documents ----------------
DOC_TYPES = {'Judgment': ('Judgment', 'حكم'), 'Cease-and-desist letter': ('Cease-and-desist letter', 'إنذار قانوني'), 'Statement of claim': ('Statement of claim', 'صحيفة دعوى'),
             'Settlement agreement': ('Settlement agreement', 'اتفاقية تسوية'), 'Investigation report': ('Investigation report', 'تقرير تحقيق'),
             'Customs seizure notice': ('Customs seizure notice', 'إخطار حجز جمركي'), 'Licence agreement': ('Licence agreement', 'اتفاقية ترخيص'),
             'Takedown notice': ('Takedown notice', 'إخطار إزالة'), 'Trademark office decision': ('Trademark office decision', 'قرار إدارة العلامات التجارية'),
             'Evidence – test purchase': ('Evidence – test purchase', 'دليل – شراء اختباري'), 'Power of attorney': ('Power of attorney', 'وكالة قانونية'),
             'Expert report': ('Expert report', 'تقرير خبير')}
docs = []; did = 0
for _, c in cases.iterrows():
    types = ['Power of attorney'] if random.random() < 0.5 else []
    types += ['Evidence – test purchase'] if random.random() < 0.6 else []
    if c.stage not in ('Intake',): types.append('Cease-and-desist letter')
    if c.case_type == 'Customs seizure': types.append('Customs seizure notice')
    if c.case_type == 'Trademark opposition / cancellation' and c.status == 'Closed': types.append('Trademark office decision')
    if c.case_type in ('Mobile app infringement', 'Online marketplace listing', 'Domain name / cybersquatting') and c.stage != 'Intake': types.append('Takedown notice')
    if c.stage in ('Filed', 'Hearing', 'Judgment', 'Appeal', 'Closed', 'Settled') and c.case_type not in ('Customs seizure', 'Trademark opposition / cancellation'):
        if random.random() < 0.8: types.append('Statement of claim')
        if random.random() < 0.3: types.append('Expert report')
    if c.outcome in ('Won', 'Partially won', 'Lost'): types.append('Judgment')
    if c.outcome == 'Settled': types.append('Settlement agreement')
    if random.random() < 0.35: types.append('Investigation report')
    if c.case_type == 'Parallel import / grey market': types.append('Licence agreement')
    end = c.closed_date or TODAY
    for t in dict.fromkeys(types):
        did += 1
        ar_bias = 0.65 if c.country in ('KSA', 'Egypt', 'Jordan', 'Kuwait', 'Qatar', 'Oman') else (0.35 if c.country == 'UAE' else 0.05)
        if t in ('Judgment', 'Trademark office decision', 'Customs seizure notice') and c.country != 'India' and c.country != 'Turkey': ar_bias = 0.8
        lang = 'AR' if random.random() < ar_bias else 'EN'
        scanned = random.random() < (0.5 if t in ('Judgment', 'Customs seizure notice', 'Power of attorney', 'Trademark office decision') else 0.25)
        ocr = round(random.uniform(0.82, 0.99), 2) if scanned else None
        status = 'Indexed'
        skip = ''
        r = random.random()
        if r < 0.04: status, skip = 'Skipped', 'Password-protected PDF'
        elif r < 0.07: status, skip = 'Skipped', 'OCR confidence below threshold'
        elif r < 0.10: status, skip = 'Pending', 'Queued for reindex'
        if scanned and ocr and ocr < 0.85: status, skip = 'Indexed (flagged)', 'Low-confidence pages flagged for review'
        pages = random.randint(1, 4) if t in ('Cease-and-desist letter', 'Takedown notice', 'Power of attorney', 'Customs seizure notice') else random.randint(4, 28)
        ddate = rand_date(c.opened_date, end)
        name = f'{c.case_id}_{t.replace(" ", "_").replace("–", "").replace("__", "_")}_{lang}.{"pdf" if scanned or t == "Judgment" else "docx"}'
        docs.append(dict(doc_id=f'DOC-{did:04d}', case_id=c.case_id, doc_type=t, doc_type_ar=DOC_TYPES[t][1], title=name, language=lang, doc_date=ddate,
                         pages=pages, scanned=scanned, ocr_confidence=ocr, sensitivity=c.sensitivity, access_group=c.access_group,
                         library_path=f'{c.sharepoint_library}/{name}', index_status=status, skip_reason=skip,
                         chunks=0 if status.startswith(('Skipped', 'Pending')) else pages * random.randint(3, 6)))
docs = pd.DataFrame(docs)

# ---------------- mailbox ----------------
REPORTERS = ['Consumer', 'Distributor', 'Customs', 'Brand protection vendor', 'Internal sales', 'Marketplace platform', 'Anonymous']
CHANNELS = ['Online marketplace', 'Social media', 'Physical store', 'Mobile app', 'Website / domain', 'Customs', 'Wholesale market']
mails = []; mid = 0
def new_mail(received, country, mark, linked=None, status=None, reporter=None, channel=None):
    global mid
    mid += 1
    reporter = reporter or pick(REPORTERS, [30, 20, 6, 20, 12, 7, 5])
    channel = channel or pick(CHANNELS, [30, 18, 20, 8, 8, 8, 8])
    mname = marks.set_index('mark_id').loc[mark, 'mark_name']
    subj = pick([f'Suspected counterfeit {mname} products – {country}', f'Report: fake {mname} listing', f'{mname} imitation packaging seen in {country}',
                 f'Unauthorised {mname} app', f'Complaint about {mname} product quality (suspected fake)', f'Seizure notice – goods bearing {mname}'])
    if status is None:
        age = (TODAY - received.date()).days
        status = 'New' if age < 3 else pick(['Triaged – monitoring', 'Dismissed – not infringing', 'Duplicate', 'Linked to case', 'Triaged – no action'], [25, 20, 12, 8, 35])
    triaged = None if status == 'New' else received + dt.timedelta(hours=random.choice([4, 8, 20, 30, 50, 80, 120]))
    sla_h = 48
    breached = bool(triaged and (triaged - received).total_seconds() / 3600 > sla_h)
    assigned = pick(['U-07', 'U-09', 'U-04', 'U-08'], [45, 30, 15, 10])
    mails.append(dict(email_id=f'EM-{mid:04d}', received_at=received, reporter_type=reporter, sender_domain=pick(['gmail.com', 'outlook.com', 'brandguard-demo.com', 'customs.gov.demo', 'distributor-demo.ae', 'marketplace-demo.com', 'company-demo.local']),
                      subject=subj, country=country, mark_id=mark, channel=channel, triage_status=status, triaged_at=triaged, sla_hours=sla_h, sla_breached=breached,
                      linked_case_id=linked or '', assigned_to=assigned))
for _, c in cases[cases.source_channel == 'Infringement mailbox'].iterrows():
    rcv = dt.datetime.combine(c.opened_date - dt.timedelta(days=random.randint(1, 10)), dt.time(random.randint(7, 19), random.randint(0, 59)))
    new_mail(rcv, c.country, c.mark_id, linked=c.case_id, status='Linked to case')
# background mail with a rising weekly trend
start = dt.datetime(2024, 1, 2); weeks = int((dt.datetime.combine(TODAY, dt.time()) - start).days / 7)
for w in range(weeks):
    n = max(0, int(random.gauss(0.9 + w * 0.012, 0.8)))
    for _ in range(n):
        rcv = start + dt.timedelta(days=w * 7 + random.randint(0, 6), hours=random.randint(7, 20), minutes=random.randint(0, 59))
        if rcv.date() > TODAY: continue
        country = pick(list(COUNTRY_W), list(COUNTRY_W.values())); mark = pick(list(marks.mark_id), [30, 14, 18, 8, 16, 14])
        new_mail(rcv, country, mark)
mailbox = pd.DataFrame(mails).sort_values('received_at').reset_index(drop=True)

# ---------------- intake forms ----------------
forms = []; fid = 0
def new_form(sub, country, mark, linked='', status=None):
    global fid
    fid += 1
    status = status or pick(['Under review', 'Converted to case', 'Rejected – insufficient evidence', 'Merged into existing case', 'Monitoring'], [20, 0, 30, 25, 25])
    forms.append(dict(form_id=f'IF-{fid:04d}', submitted_at=sub, submitter_team=pick(['Sales', 'Marketing', 'Distributor', 'Customer care', 'Brand protection vendor', 'Supply chain']),
                      mark_id=mark, country=country, infringement_type=pick(['Counterfeit product', 'Lookalike packaging', 'Unauthorised online listing', 'Infringing app', 'Infringing domain', 'Grey-market import']),
                      evidence_files=random.randint(0, 6), estimated_units=random.choice([0, 50, 200, 500, 1200, 5000, 12000]), status=status, converted_case_id=linked))
for _, c in cases[cases.source_channel == 'Intake form'].iterrows():
    new_form(c.opened_date - dt.timedelta(days=random.randint(1, 14)), c.country, c.mark_id, linked=c.case_id, status='Converted to case')
for _ in range(62):
    new_form(rand_date(d(2024, 1, 5), TODAY), pick(list(COUNTRY_W), list(COUNTRY_W.values())), pick(list(marks.mark_id)))
intake = pd.DataFrame(forms).sort_values('submitted_at').reset_index(drop=True)

# ---------------- app store monitoring ----------------
apps = []; aid = 0
APPNAMES = ['{m} Rewards', '{m} Kids Game', '{m} Recipes', '{m} Fan Club', '{m} Wallpapers', '{m} Shop', '{m} Quiz', '{m} Stickers', '{m} Coupons', '{m} Puzzle']
def new_app(detected, country, mark, linked='', status=None):
    global aid
    aid += 1
    mname = marks.set_index('mark_id').loc[mark, 'mark_name']
    store = pick(['Google Play', 'Apple App Store', 'Huawei AppGallery', 'Samsung Galaxy Store'], [45, 35, 15, 5])
    status = status or pick(['Detected', 'Reported to store', 'Takedown requested', 'Removed', 'Rejected by store', 'Re-listed'], [10, 15, 15, 45, 8, 7])
    req = detected + dt.timedelta(days=random.randint(1, 10)) if status not in ('Detected',) else None
    removed = req + dt.timedelta(days=random.randint(2, 30)) if status in ('Removed', 'Re-listed') else None
    dev = pick(list(infringers[infringers.infringer_type == 'App developer'].infringer_name_en) + ['Unknown developer', 'Indie Apps 2024', 'Candy Games Studio'])
    apps.append(dict(app_id=f'APP-{aid:03d}', store=store, app_name=pick(APPNAMES).format(m=mname), developer=dev, mark_id=mark, country=country, detected_date=detected,
                     status=status, takedown_requested_date=req, removed_date=removed, est_downloads=random.choice([500, 1000, 5000, 10000, 50000, 100000]),
                     linked_case_id=linked))
for _, c in cases[cases.source_channel == 'App store monitoring'].iterrows():
    new_app(c.opened_date - dt.timedelta(days=random.randint(1, 7)), c.country, c.mark_id, linked=c.case_id,
            status='Removed' if c.status == 'Closed' else pick(['Reported to store', 'Takedown requested', 'Rejected by store']))
for _ in range(58):
    new_app(rand_date(d(2024, 1, 5), TODAY), pick(list(COUNTRY_W), list(COUNTRY_W.values())), pick(list(marks.mark_id)))
appstore = pd.DataFrame(apps).sort_values('detected_date').reset_index(drop=True)

# ---------------- invoices ----------------
inv = []; iid = 0
for _, c in cases[cases.external_firm != ''].iterrows():
    n = random.randint(1, 4) if c.status == 'Closed' else random.randint(1, 2)
    end = c.closed_date or TODAY
    for _ in range(n):
        iid += 1
        cat = pick(['Counsel fees', 'Court fees', 'Investigation', 'Translation', 'Expert fees', 'Customs handling'], [45, 20, 12, 10, 8, 5])
        amt = {'Counsel fees': random.randint(12, 90), 'Court fees': random.randint(5, 40), 'Investigation': random.randint(4, 18), 'Translation': random.randint(2, 9),
               'Expert fees': random.randint(10, 35), 'Customs handling': random.randint(3, 12)}[cat] * 1000
        inv.append(dict(invoice_id=f'INV-{iid:04d}', case_id=c.case_id, firm=c.external_firm, invoice_date=rand_date(c.opened_date, end), category=cat,
                        amount_aed=amt, status=pick(['Paid', 'Approved', 'Under review'], [75, 15, 10])))
invoices = pd.DataFrame(inv)

# ---------------- derived helper columns ----------------
cases['legal_spend_aed'] = cases.case_id.map(invoices.groupby('case_id').amount_aed.sum()).fillna(0).astype(int)
cases['mark_name'] = cases.mark_id.map(marks.set_index('mark_id').mark_name)
cases['infringer_name'] = cases.infringer_id.map(infringers.set_index('infringer_id').infringer_name_en)
cases['infringer_type'] = cases.infringer_id.map(infringers.set_index('infringer_id').infringer_type)
cases['court_name'] = cases.court_id.map(courts.set_index('court_id').court_name_en)
cases['lead_counsel'] = cases.lead_counsel_id.map(users.set_index('user_id').full_name)
infringers['case_count'] = infringers.infringer_id.map(cases.groupby('infringer_id').size()).fillna(0).astype(int)
infringers['repeat_offender'] = infringers.case_count >= 2
infringers['first_seen'] = infringers.infringer_id.map(cases.groupby('infringer_id').opened_date.min())

# ---------------- write ----------------
tables = {'dim_mark': marks, 'dim_court': courts, 'dim_infringer': infringers, 'dim_user': users, 'fact_case': cases, 'fact_case_event': events,
          'fact_document': docs, 'fact_mailbox': mailbox, 'fact_intake_form': intake, 'fact_appstore': appstore, 'fact_invoice': invoices}
for name, df in tables.items():
    df.to_csv(f'{OUT}/csv/{name}.csv', index=False)
    print(f'{name:18s} {len(df):5d} rows')
json.dump({k: json.loads(v.to_json(orient='records', date_format='iso')) for k, v in tables.items()}, open(f'{OUT}/data.json', 'w'))
print('cases by status:', cases.status.value_counts().to_dict())
print('outcomes:', cases.outcome.value_counts().to_dict())
print('claim total AED', cases.claim_amount_aed.sum(), 'awarded', cases.awarded_amount_aed.sum(), 'settled', cases.settlement_amount_aed.sum(), 'recovered', cases.recovered_amount_aed.sum())
