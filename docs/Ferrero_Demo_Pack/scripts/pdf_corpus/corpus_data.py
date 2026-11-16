"""Data layer for the 150-PDF demo corpus.

Loads the pack CSVs, builds a per-case context (EN + AR names, court, counsel, firm, amounts,
event-aligned dates and derived facts that every document of the same case shares), selects
which fact_document rows become real PDFs, and assigns file names.
Everything is deterministic: the same CSVs always give the same corpus.
"""
import csv, hashlib, random, re, datetime as dt
from collections import Counter, defaultdict
from pathlib import Path

PACK = Path(__file__).resolve().parents[2]          # .../Ferrero_Demo_Pack
CSV = PACK / 'csv'
DEMO_TODAY = dt.date(2026, 11, 5)
CLAIMANT = {'en': 'Dolce Group International S.A.', 'ar': 'شركة دولتشي جروب إنترناشيونال'}
CLAIMANT_ADDR = {'en': '5, Rue des Noisetiers, L-1855 Luxembourg, Grand Duchy of Luxembourg (RCS Luxembourg B 41 207)',
                 'ar': '5 شارع دي نوازوتييه، لوكسمبورغ، دوقية لوكسمبورغ الكبرى (السجل التجاري B 41 207)'}
LEGAL_DEPT = {'en': 'Legal Department – Middle East, Turkey & India, Dolce Group International S.A., Jebel Ali Free Zone, Dubai, UAE',
              'ar': 'الإدارة القانونية – الشرق الأوسط وتركيا والهند، شركة دولتشي جروب إنترناشيونال، المنطقة الحرة لجبل علي، دبي'}
DISCLAIMER = {'en': 'Demo document – all parties and facts are fictional', 'ar': 'مستند تجريبي – جميع الأطراف والوقائع خيالية'}
INVESTIGATOR = {'en': 'BrandGuard Investigations FZ-LLC', 'ar': 'براند جارد للتحقيقات (م.م.ح)'}
LAB = {'en': 'Dolce Group Regional Quality & Authentication Laboratory, Jebel Ali', 'ar': 'مختبر الجودة والتحقق الإقليمي لشركة دولتشي جروب، جبل علي'}

# ----------------------------------------------------------------------------- deterministic helpers
def rng(*key):
    h = hashlib.sha256('|'.join(map(str, key)).encode()).hexdigest()
    return random.Random(int(h[:16], 16))

def d(s):
    return dt.date.fromisoformat(s) if s else None

AR_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
HIJRI_MONTHS = ['محرم', 'صفر', 'ربيع الأول', 'ربيع الآخر', 'جمادى الأولى', 'جمادى الآخرة', 'رجب', 'شعبان', 'رمضان', 'شوال', 'ذو القعدة', 'ذو الحجة']

def den(x):  # 08 October 2024
    return x.strftime('%d %B %Y') if x else ''

def dar(x):  # 8 أكتوبر 2024
    return f'{x.day} {AR_MONTHS[x.month - 1]} {x.year}' if x else ''

def dnum(x):  # 08/10/2024
    return x.strftime('%d/%m/%Y') if x else ''

def hijri(x):
    """Tabular (arithmetic) Islamic calendar; may differ from Umm al-Qura by a day."""
    jdn = x.toordinal() + 1721425
    l = jdn - 1948440 + 10632
    n = (l - 1) // 10631
    l = l - 10631 * n + 354
    j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
    l = l - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
    m = (24 * l) // 709
    day = l - (709 * m) // 24
    y = 30 * n + j - 30
    return y, m, day

HIJRI_MONTHS_EN = ['Muharram', 'Safar', 'Rabi al-Awwal', 'Rabi al-Thani', 'Jumada al-Ula', 'Jumada al-Akhirah', 'Rajab', 'Shaban', 'Ramadan',
                   'Shawwal', 'Dhu al-Qadah', 'Dhu al-Hijjah']

def dhijri(x, lang='AR'):
    y, m, day = hijri(x)
    if lang == 'EN':
        return f'{day} {HIJRI_MONTHS_EN[m - 1]} {y} AH'
    return f'{day} {HIJRI_MONTHS[m - 1]} {y}هـ'

def money(n):
    return f'{int(round(n)):,}'

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

# ----------------------------------------------------------------------------- translations
COUNTRY = {'UAE': ('United Arab Emirates', 'الإمارات العربية المتحدة'), 'KSA': ('Kingdom of Saudi Arabia', 'المملكة العربية السعودية'),
           'Egypt': ('Arab Republic of Egypt', 'جمهورية مصر العربية'), 'Jordan': ('Hashemite Kingdom of Jordan', 'المملكة الأردنية الهاشمية'),
           'Kuwait': ('State of Kuwait', 'دولة الكويت'), 'Qatar': ('State of Qatar', 'دولة قطر'), 'Oman': ('Sultanate of Oman', 'سلطنة عُمان'),
           'Turkey': ('Republic of Türkiye', 'الجمهورية التركية'), 'India': ('Republic of India', 'جمهورية الهند')}
CITY_AR = {'Dubai': 'دبي', 'Abu Dhabi': 'أبوظبي', 'Sharjah': 'الشارقة', 'Ajman': 'عجمان', 'Ras Al Khaimah': 'رأس الخيمة', 'Riyadh': 'الرياض',
           'Jeddah': 'جدة', 'Dammam': 'الدمام', 'Taif': 'الطائف', 'Cairo': 'القاهرة', 'Alexandria': 'الإسكندرية', 'Giza': 'الجيزة', 'Amman': 'عمّان',
           'Kuwait City': 'مدينة الكويت', 'Salmiya': 'السالمية', 'Doha': 'الدوحة', 'Muscat': 'مسقط', 'Sohar': 'صحار', 'Istanbul': 'إسطنبول',
           'Ankara': 'أنقرة', 'New Delhi': 'نيودلهي', 'Mumbai': 'مومباي', 'Bangalore': 'بنغالور', 'Unknown': 'غير معروف'}
AREAS = {  # (EN, AR) business areas used for fictional addresses
    'Dubai': [('Deira', 'ديرة'), ('Al Qusais Industrial Area 4', 'منطقة القصيص الصناعية 4'), ('Al Karama', 'الكرامة'), ('Al Quoz Industrial Area 3', 'منطقة القوز الصناعية 3')],
    'Abu Dhabi': [('Mussafah M-12', 'مصفح م-12'), ('Hamdan Street', 'شارع حمدان')], 'Sharjah': [('Industrial Area 6', 'المنطقة الصناعية 6'), ('Al Nahda', 'النهدة')],
    'Ajman': [('Al Jurf Industrial Area', 'منطقة الجرف الصناعية')], 'Ras Al Khaimah': [('Al Hamra Industrial Zone', 'منطقة الحمرا الصناعية')],
    'Riyadh': [('Al Batha', 'البطحاء'), ('Al Sulay Industrial District', 'حي السلي الصناعي')], 'Jeddah': [('Al Balad', 'البلد'), ('Al Safa District', 'حي الصفا')],
    'Dammam': [('Al Faisaliyah District', 'حي الفيصلية')], 'Taif': [('Shihar District', 'حي شهار')], 'Cairo': [('Al Ataba', 'العتبة'), ('Nasr City', 'مدينة نصر')],
    'Alexandria': [('Al Manshiya', 'المنشية')], 'Giza': [('Dokki', 'الدقي')], 'Amman': [('Al Weibdeh', 'اللويبدة'), ('Wasat Al Balad', 'وسط البلد')],
    'Kuwait City': [('Al Mubarakiya', 'المباركية')], 'Salmiya': [('Salem Al Mubarak Street', 'شارع سالم المبارك')], 'Doha': [('Al Sadd', 'السد')],
    'Muscat': [('Ruwi', 'روي')], 'Sohar': [('Sohar Industrial Estate', 'منطقة صحار الصناعية')], 'Istanbul': [('Bayrampaşa', 'بايرام باشا'), ('Eminönü', 'أمين أونو')],
    'Ankara': [('Ostim OSB', 'أوستيم')], 'New Delhi': [('Okhla Industrial Area Phase II', 'منطقة أوخلا الصناعية')], 'Mumbai': [('Masjid Bunder', 'مسجد بندر')],
    'Bangalore': [('Koramangala', 'كورامانجالا')], 'Unknown': [('', '')]}
CASE_TYPE_AR = {'Trademark infringement – counterfeit goods': 'تعدٍّ على علامة تجارية – بضائع مقلدة', 'Online marketplace listing': 'عرض مخالف على منصة تجارة إلكترونية',
                'Mobile app infringement': 'تعدٍّ عبر تطبيق للهاتف المحمول', 'Unfair competition': 'منافسة غير مشروعة', 'Customs seizure': 'حجز جمركي',
                'Domain name / cybersquatting': 'اسم نطاق / سطو إلكتروني', 'Packaging imitation / passing off': 'تقليد العبوة / انتحال',
                'Trademark opposition / cancellation': 'اعتراض / شطب علامة تجارية', 'Parallel import / grey market': 'استيراد موازٍ / سوق رمادية'}
INF_TYPE_AR = {'Distributor': 'موزع', 'Importer': 'مستورد', 'Manufacturer': 'مصنّع', 'Retailer': 'تاجر تجزئة', 'Online seller': 'بائع عبر الإنترنت',
               'App developer': 'مطوّر تطبيقات', 'Domain registrant': 'مسجل اسم نطاق'}
PRODUCT_AR = {'Hazelnut spread': 'كريمة البندق القابلة للدهن', 'Wafer bars': 'ألواح الويفر', 'Boxed pralines': 'علب البرالين', 'Mints and chewing gum': 'النعناع والعلكة',
              'Children’s chocolate treats with toy': 'حلوى الشوكولاتة للأطفال مع لعبة', 'Gold-wrapped hazelnut chocolates': 'شوكولاتة البندق بالغلاف الذهبي'}
PRODUCT_UNIT = {'Hazelnut spread': ('350 g jar', 'برطمان 350 غ'), 'Wafer bars': ('4-bar multipack', 'عبوة من 4 ألواح'), 'Boxed pralines': ('24-piece gift box', 'علبة هدايا 24 قطعة'),
                'Mints and chewing gum': ('40 g tin', 'علبة معدنية 40 غ'), 'Children’s chocolate treats with toy': ('3-pack with toy', 'عبوة من 3 مع لعبة'),
                'Gold-wrapped hazelnut chocolates': ('16-piece box', 'علبة 16 قطعة')}
UNIT_PRICE = {'Hazelnut spread': 24, 'Wafer bars': 9, 'Boxed pralines': 45, 'Mints and chewing gum': 6, 'Children’s chocolate treats with toy': 15, 'Gold-wrapped hazelnut chocolates': 38}  # AED retail
CURRENCY_AR = {'AED': 'درهم إماراتي', 'SAR': 'ريال سعودي', 'EGP': 'جنيه مصري', 'JOD': 'دينار أردني', 'KWD': 'دينار كويتي', 'QAR': 'ريال قطري', 'OMR': 'ريال عماني', 'TRY': 'ليرة تركية', 'INR': 'روبية هندية'}
FX_FROM_AED = {'AED': 1, 'SAR': 1.02, 'EGP': 13.2, 'JOD': 0.193, 'KWD': 0.084, 'QAR': 0.99, 'OMR': 0.105, 'TRY': 9.1, 'INR': 22.6}
VAT = {'UAE': 5, 'KSA': 15, 'Egypt': 14, 'Jordan': 16, 'Kuwait': 0, 'Qatar': 0, 'Oman': 5, 'Turkey': 10, 'India': 18}
LAW = {  # trademark statute cited in letters, claims and judgments
    'UAE': ('Federal Decree-Law No. 36 of 2021 on Trademarks', 'المرسوم بقانون اتحادي رقم 36 لسنة 2021 في شأن العلامات التجارية'),
    'KSA': ('the GCC Trademark Law (Royal Decree No. M/51 of 1435H) and its Implementing Regulations', 'نظام (قانون) العلامات التجارية لدول مجلس التعاون الصادر بالمرسوم الملكي رقم م/51 لعام 1435هـ ولائحته التنفيذية'),
    'Egypt': ('Law No. 82 of 2002 on the Protection of Intellectual Property Rights', 'قانون حماية حقوق الملكية الفكرية رقم 82 لسنة 2002'),
    'Jordan': ('the Trademarks Law No. 33 of 1952, as amended', 'قانون العلامات التجارية رقم 33 لسنة 1952 وتعديلاته'),
    'Kuwait': ('the GCC Trademark Law as implemented by Law No. 13 of 2015', 'قانون العلامات التجارية لدول مجلس التعاون المعمول به بموجب القانون رقم 13 لسنة 2015'),
    'Qatar': ('the GCC Trademark Law as applicable in the State of Qatar', 'قانون العلامات التجارية لدول مجلس التعاون المعمول به في دولة قطر'),
    'Oman': ('the Industrial Property Rights Law (Royal Decree No. 67/2008)', 'قانون حقوق الملكية الصناعية الصادر بالمرسوم السلطاني رقم 67/2008'),
    'Turkey': ('the Industrial Property Law No. 6769', 'قانون الملكية الصناعية التركي رقم 6769'),
    'India': ('the Trade Marks Act, 1999', 'قانون العلامات التجارية الهندي لسنة 1999')}
FIRMS = {  # fictional firms already present in fact_case; offices, people and Arabic names are invented here
    'Najm & Co. Advocates': dict(ar='نجم وشركاه للمحاماة', city='Dubai', addr_en='Office 2104, Al Wasl Business Tower, Sheikh Zayed Road, Dubai, UAE',
                                 addr_ar='مكتب 2104، برج الوصل للأعمال، شارع الشيخ زايد، دبي، الإمارات العربية المتحدة',
                                 people=[('Hassan Najm', 'حسن نجم', 'Managing Partner', 'الشريك المدير'), ('Rania Fakhoury', 'رانيا فاخوري', 'Senior Associate', 'محامٍ أول')], email='najmlaw'),
    'Gulf IP Partners': dict(ar='شركاء الخليج للملكية الفكرية', city='Abu Dhabi', addr_en='Level 9, Al Maqam Tower, Al Maryah Island, Abu Dhabi, UAE',
                             addr_ar='الطابق 9، برج المقام، جزيرة الماريه، أبوظبي، الإمارات العربية المتحدة',
                             people=[('Faisal Al Mutairi', 'فيصل المطيري', 'Partner', 'شريك'), ('Elena Petrova', 'إيلينا بتروفا', 'Counsel', 'مستشار')], email='gulfip'),
    'Riyadh Law Chambers': dict(ar='مكتب الرياض للمحاماة والاستشارات القانونية', city='Riyadh', addr_en='King Fahd Road, Al Olaya District, Riyadh 12212, Saudi Arabia',
                                addr_ar='طريق الملك فهد، حي العليا، الرياض 12212، المملكة العربية السعودية',
                                people=[('Abdulaziz Al Harbi', 'عبدالعزيز الحربي', 'Partner', 'شريك'), ('Saud Al Dosari', 'سعود الدوسري', 'Senior Associate', 'محامٍ أول')], email='riyadhlaw'),
    'Levant Legal Group': dict(ar='مجموعة المشرق القانونية', city='Amman', addr_en='Building 14, Al Abdali Boulevard, Amman 11190, Jordan',
                               addr_ar='بناية 14، بوليفارد العبدلي، عمّان 11190، المملكة الأردنية الهاشمية',
                               people=[('Tariq Haddadin', 'طارق الحدادين', 'Partner', 'شريك'), ('Dana Khoury', 'دانا خوري', 'Associate', 'محامٍ')], email='levantlegal'),
    'Indus Legal Associates': dict(ar='إندس للاستشارات القانونية', city='New Delhi', addr_en='B-41, Connaught Place, New Delhi 110001, India',
                                   addr_ar='B-41 كونوت بليس، نيودلهي 110001، الهند',
                                   people=[('Arjun Mehta', 'أرجون ميهتا', 'Partner', 'شريك'), ('Kavita Rao', 'كافيتا راو', 'Associate', 'محامٍ')], email='induslegal'),
    'Bosphorus IP Law': dict(ar='بوسفور لقانون الملكية الفكرية', city='Istanbul', addr_en='Büyükdere Caddesi No. 185, Levent, 34394 Istanbul, Türkiye',
                             addr_ar='شارع بيوك دره رقم 185، ليفنت، إسطنبول، تركيا',
                             people=[('Emre Yılmaz', 'أمره يلماز', 'Partner', 'شريك'), ('Selin Aksoy', 'سيلين أكسوي', 'Associate', 'محامٍ')], email='bosphorusip'),
    'Nile Counsel LLP': dict(ar='نايل كاونسل للمحاماة', city='Cairo', addr_en='12 Hassan Sabry Street, Zamalek, Cairo, Egypt',
                             addr_ar='12 شارع حسن صبري، الزمالك، القاهرة، جمهورية مصر العربية',
                             people=[('Mostafa El Sherif', 'مصطفى الشريف', 'Partner', 'شريك'), ('Heba Fawzy', 'هبة فوزي', 'Associate', 'محامٍ')], email='nilecounsel'),
}
USER_AR = {'U-01': ('مريم السويدي', 'رئيس الإدارة القانونية'), 'U-02': ('دانيال فيبر', 'المستشار العام الإقليمي'), 'U-03': ('خالد رحمن', 'مستشار أول للملكية الفكرية'),
           'U-04': ('سارة حداد', 'مستشار الملكية الفكرية'), 'U-05': ('عمر القحطاني', 'مستشار التقاضي'), 'U-06': ('لينا منصور', 'المستشار القانوني – الشرق الأوسط وشمال أفريقيا'),
           'U-07': ('يوسف ناصر', 'مدير حماية العلامات التجارية'), 'U-08': ('بريا مينون', 'رئيس العمليات القانونية'), 'U-09': ('أحمد درويش', 'مساعد قانوني'),
           'U-10': ('نور الهاشمي', 'مدير المشتريات')}
EXPERTS = {  # fictional court experts
    'UAE': ('Dr. Samir Al Khatib, registered IP expert (Dubai Courts experts roll No. 1187)', 'د. سامر الخطيب، خبير ملكية فكرية مقيد بجدول الخبراء رقم 1187'),
    'KSA': ('Dr. Fahad Al Otaibi, accredited IP expert (Saudi Authority for IP roll No. 214)', 'د. فهد العتيبي، خبير ملكية فكرية معتمد (قيد رقم 214)'),
    'Egypt': ('Dr. Mahmoud Abdel Hamid, expert at the Ministry of Justice Experts Authority', 'د. محمود عبد الحميد، خبير بمصلحة خبراء وزارة العدل'),
    'Jordan': ('Dr. Rami Al Nabulsi, court-appointed IP expert', 'د. رامي النابلسي، خبير ملكية فكرية منتدب من المحكمة'),
    'Kuwait': ('Eng. Khaled Al Rashidi, expert, Experts Department, Ministry of Justice', 'م. خالد الرشيدي، خبير بإدارة الخبراء بوزارة العدل'),
    'Qatar': ('Dr. Ali Al Kuwari, court-registered IP expert', 'د. علي الكواري، خبير ملكية فكرية مقيد لدى المحكمة'),
    'Oman': ('Dr. Salim Al Balushi, court-appointed IP expert', 'د. سالم البلوشي، خبير ملكية فكرية منتدب'),
    'Turkey': ('Prof. Dr. Ayşe Demir, court-appointed IP expert (bilirkişi)', 'أ. د. عائشة دمير، خبير ملكية فكرية منتدب'),
    'India': ('Dr. R. Srinivasan, Local Commissioner and IP expert', 'د. ر. سرينيفاسان، مفوض محلي وخبير ملكية فكرية')}
MARKETPLACE = {'UAE': 'DealHub', 'KSA': 'Souq Al Hala Online', 'Egypt': 'Giza Online Mart', 'Turkey': 'Anadolu Online Market',
               'Jordan': 'DealHub', 'Kuwait': 'DealHub', 'Qatar': 'DealHub', 'Oman': 'DealHub', 'India': 'DealHub'}
DOC_AR = {'Judgment': 'حكم', 'Cease-and-desist letter': 'إنذار قانوني', 'Statement of claim': 'صحيفة دعوى', 'Settlement agreement': 'اتفاقية تسوية',
          'Investigation report': 'تقرير تحقيق', 'Customs seizure notice': 'إخطار حجز جمركي', 'Licence agreement': 'اتفاقية ترخيص', 'Takedown notice': 'إخطار إزالة',
          'Trademark office decision': 'قرار إدارة العلامات التجارية', 'Evidence – test purchase': 'دليل – شراء اختباري', 'Power of attorney': 'وكالة قانونية',
          'Expert report': 'تقرير خبير'}
SENS_AR = {'Confidential': 'سري', 'Internal': 'داخلي', 'Restricted': 'مقيد'}

# ----------------------------------------------------------------------------- loading
def read(name):
    with open(CSV / name, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))

class Data:
    def __init__(self):
        self.cases = {r['case_id']: r for r in read('fact_case.csv')}
        self.docs = read('fact_document.csv')
        self.doc_fields = list(self.docs[0].keys())
        self.marks = {r['mark_id']: r for r in read('dim_mark.csv')}
        self.infringers = {r['infringer_id']: r for r in read('dim_infringer.csv')}
        self.courts = {r['court_id']: r for r in read('dim_court.csv')}
        self.users = {r['user_id']: r for r in read('dim_user.csv')}
        self.golden = read('golden_set.csv')
        self.golden_fields = list(self.golden[0].keys())
        self.events = defaultdict(list)
        for e in read('fact_case_event.csv'):
            self.events[e['case_id']].append(e)
        self.apps = defaultdict(list)
        for a in read('fact_appstore.csv'):
            if a['linked_case_id']:
                self.apps[a['linked_case_id']].append(a)
        self._ctx = {}

    def ctx(self, case_id):
        if case_id not in self._ctx:
            self._ctx[case_id] = build_ctx(self, case_id)
        return self._ctx[case_id]

# ----------------------------------------------------------------------------- per-case context
def local_reg(mark, country):
    if country == 'UAE':
        return mark['uae_registration_no']
    r = rng('reg', mark['mark_id'], country)
    return {'KSA': f'{r.randint(1436, 1441)}{r.randint(10000, 99999):06d}', 'Egypt': f'{r.randint(180000, 289999)}', 'Jordan': f'{r.randint(98000, 179999)}',
            'Kuwait': f'{r.randint(110000, 189999)}', 'Qatar': f'{r.randint(70000, 139999)}', 'Oman': f'{r.randint(60000, 129999)}',
            'Turkey': f'{r.randint(2012, 2019)}/{r.randint(10000, 99999)}', 'India': f'{r.randint(2100000, 4900000)}'}[country]

def commercial_reg(inf):
    r = rng('cr', inf['infringer_id'])
    c = inf['country']
    if inf['infringer_type'] == 'Domain registrant':
        return ('identity withheld by privacy service', 'الهوية محجوبة بخدمة الخصوصية')
    if c == 'UAE':
        n = f'{r.randint(600000, 1199999)}'; return (f'trade licence No. {n}', f'رخصة تجارية رقم {n}')
    if c == 'KSA':
        pre = {'Riyadh': '1010', 'Jeddah': '4030', 'Dammam': '2050', 'Taif': '4032'}.get(inf['city'], '1010'); n = f'{pre}{r.randint(100000, 999999)}'
        return (f'CR No. {n}', f'سجل تجاري رقم {n}')
    if c == 'India':
        n = f'U15{r.randint(100, 999)}DL{r.randint(2005, 2019)}PTC{r.randint(100000, 399999)}'; return (f'CIN {n}', f'رقم التسجيل {n}')
    if c == 'Turkey':
        n = f'{r.randint(100000, 999999)}'; return (f'trade registry No. {n}', f'سجل تجاري رقم {n}')
    n = f'{r.randint(10000, 99999)}'; return (f'CR No. {n}', f'سجل تجاري رقم {n}')

def short_name(name):
    n = re.sub(r'\((registrant)\)|LLC|FZE|FZ-LLC|Ltd|Pvt|WLL|SARL|A\.Ş\.|Co\.|Est\.|Company|Trading|General|Foodstuff|Foods|Distribution|Technologies|Studio', '', name)
    n = re.sub(r'\s+', ' ', n).strip(' .,')
    words = n.split()
    if not words:
        return name.split()[0]
    if words[0] in ('Al', 'El') and len(words) > 1:
        return ' '.join(words[:2])
    return words[0]

def ev_dates(evs):
    out = {}
    for e in sorted(evs, key=lambda e: e['event_date']):
        out.setdefault(e['event_type'], d(e['event_date']))
    return out

def build_ctx(D, cid):
    c = D.cases[cid]
    m = D.marks[c['mark_id']]; i = D.infringers[c['infringer_id']]; ct = D.courts[c['court_id']]; u = D.users[c['lead_counsel_id']]
    R = rng('ctx', cid)
    country = c['country']; cur = c['currency']
    opened, closed = d(c['opened_date']), d(c['closed_date'])
    end = closed or DEMO_TODAY
    ev = ev_dates(D.events[cid])
    firm = c['external_firm'] or ''
    F = FIRMS.get(firm)
    area = R.choice(AREAS.get(i['city'], [('', '')]))
    unit = R.randint(1, 48)
    if i['infringer_type'] == 'Domain registrant':
        addr_en, addr_ar = 'address withheld (domain privacy service)', 'العنوان محجوب (خدمة خصوصية النطاق)'
    elif i['infringer_type'] in ('Online seller', 'App developer') and R.random() < 0.5:
        addr_en = f'Office {R.randint(101, 1908)}, {area[0]}, {i["city"]}'; addr_ar = f'مكتب {R.randint(101, 1908)}، {area[1]}، {CITY_AR.get(i["city"], i["city"])}'
    else:
        kind = 'Warehouse' if i['infringer_type'] in ('Importer', 'Distributor', 'Manufacturer') else 'Shop'
        kind_ar = 'مستودع' if kind == 'Warehouse' else 'محل'
        addr_en = f'{kind} {unit}, {area[0]}, {i["city"]}'; addr_ar = f'{kind_ar} رقم {unit}، {area[1]}، {CITY_AR.get(i["city"], i["city"])}'
    cr = commercial_reg(i)
    fx = FX_FROM_AED[cur]
    price_local = UNIT_PRICE[m['product_category']] * fx
    def lp(x):  # local price with sensible rounding
        return round(x, 2) if x < 20 else round(x)
    ctx = dict(
        case_id=cid, title=c['title'], case_type=c['case_type'], case_type_ar=CASE_TYPE_AR[c['case_type']],
        country=country, country_en=COUNTRY[country][0], country_ar=COUNTRY[country][1],
        mark=m['mark_name'], mark_ar=m['mark_name_ar'], mark_reg=local_reg(m, country), mark_reg_uae=m['uae_registration_no'],
        nice=m['nice_classes'], product=m['product_category'], product_ar=PRODUCT_AR[m['product_category']],
        unit_en=PRODUCT_UNIT[m['product_category']][0], unit_ar=PRODUCT_UNIT[m['product_category']][1],
        mark_since=2008 + int(hashlib.md5(m['mark_id'].encode()).hexdigest(), 16) % 9, registered_in=m['registered_in'],
        inf=i['infringer_name_en'], inf_ar=i['infringer_name_ar'], inf_type=i['infringer_type'], inf_type_ar=INF_TYPE_AR[i['infringer_type']],
        inf_city=i['city'], inf_city_ar=CITY_AR.get(i['city'], i['city']), inf_country=i['country'], inf_addr_en=addr_en, inf_addr_ar=addr_ar,
        inf_cr_en=cr[0], inf_cr_ar=cr[1], inf_short=short_name(i['infringer_name_en']), inf_entity=i['infringer_type'] != 'Domain registrant',
        repeat=i['repeat_offender'] == 'True', inf_cases=int(i['case_count']),
        court_id=c['court_id'], court=ct['court_name_en'], court_ar=ct['court_name_ar'], court_city=ct['city'], court_city_ar=CITY_AR.get(ct['city'], ct['city']),
        court_type=ct['court_type'], court_like=ct['court_type'] in ('Civil / commercial court', 'Specialised IP court'),
        court_ref=f'{R.randint(180, 2900)}/{(ev.get("Statement of claim filed") or opened).year}',
        firm=firm, firm_ar=F['ar'] if F else '', firm_city=F['city'] if F else '', firm_addr_en=F['addr_en'] if F else '', firm_addr_ar=F['addr_ar'] if F else '',
        partner=F['people'][0] if F else None, associate=F['people'][1] if F else None, firm_email=F['email'] if F else '',
        counsel=u['full_name'], counsel_title=u['job_title'], counsel_ar=USER_AR[u['user_id']][0], counsel_title_ar=USER_AR[u['user_id']][1], counsel_id=u['user_id'],
        currency=cur, currency_ar=CURRENCY_AR[cur], claim=float(c['claim_amount_local']), awarded=float(c['awarded_amount_local']),
        settlement=float(c['settlement_amount_local']), recovered=float(c['recovered_amount_local']), claim_aed=float(c['claim_amount_aed']),
        opened=opened, closed=closed, end=end, next_hearing=d(c['next_hearing_date']), ev=ev,
        stage=c['stage'], status=c['status'], outcome=c['outcome'], priority=c['priority'], source=c['source_channel'],
        sensitivity=c['sensitivity'], access_group=c['access_group'], library=c['sharepoint_library'], next_action=c['next_action'],
        apps=D.apps.get(cid, []), law_en=LAW[country][0], law_ar=LAW[country][1], expert_en=EXPERTS[country][0], expert_ar=EXPERTS[country][1],
        vat=VAT[country], unit_price=lp(price_local * R.choice([0.42, 0.5, 0.55, 0.6, 0.65])), genuine_price=lp(price_local),
        tp_units=R.choice([3, 4, 5, 6, 8, 10, 12]), seized_units=R.choice([1200, 2400, 3600, 6000, 8400, 14500, 22000]),
        stock_seen=R.choice(['120–150', '200–250', '350–400', '600–700', 'about 1,000']), receipt_no=f'{R.randint(1000, 98999)}',
        bg_ref=f'BG-{R.randint(110, 980)}/{opened.year}', seal_no=f'BG-S{R.randint(10000, 99999)}', inv_code=f'BG-{R.randint(11, 48)}',
        lab_ref=f'LAB-{R.randint(110, 980)}/{opened.year}', marketplace=MARKETPLACE[country], listing_id=f'{R.randint(10000000, 99999999)}',
        order_no=f'{R.randint(100000000, 999999999)}', decl_no=f'{R.randint(101, 999)}-{R.randint(10000000, 99999999)}-{opened.year % 100}',
        container=f'{R.choice(["MSKU", "TGHU", "CMAU", "MSCU", "OOLU"])}{R.randint(1000000, 9999999)}', bl_no=f'{R.choice(["NGB", "SHA", "QIN", "XMN"])}{R.randint(1000000, 9999999)}',
        origin=R.choice([('Ningbo, China', 'نينغبو، الصين'), ('Mersin, Türkiye', 'مرسين، تركيا'), ('Nhava Sheva, India', 'نافا شيفا، الهند'), ('Port Klang, Malaysia', 'بورت كلانغ، ماليزيا')]),
        cd_days=R.choice([7, 10, 14, 14, 15]), instalments=R.choice([2, 2, 3]),
    )
    ctx['lp'] = lp
    # event-aligned dates shared by every document of the case
    def within(x):
        return clamp(x, opened - dt.timedelta(days=40), end)
    tp = ev.get('Test purchase completed') or ev.get('Evidence collected') or opened + dt.timedelta(days=R.randint(3, 10))
    ctx['tp_date'] = within(tp)
    ctx['cd_date'] = within(ev.get('Cease-and-desist sent') or opened + dt.timedelta(days=R.randint(10, 25)))
    ctx['inv_date'] = within(max(ctx['tp_date'], ev.get('Evidence collected') or ctx['tp_date']) + dt.timedelta(days=R.randint(3, 9)))
    ctx['soc_date'] = within(ev.get('Statement of claim filed') or ctx['cd_date'] + dt.timedelta(days=R.randint(30, 60)))
    ctx['expert_date'] = within(ev.get('Expert report filed') or ctx['soc_date'] + dt.timedelta(days=R.randint(60, 120)))
    ctx['expert_appointed'] = within(max(ctx['soc_date'] + dt.timedelta(days=21), ctx['expert_date'] - dt.timedelta(days=R.randint(35, 70))))
    ctx['hearing_dates'] = sorted(e for t, e in ((x['event_type'], d(x['event_date'])) for x in D.events[cid]) if t == 'Hearing held')
    ctx['judgment_date'] = within(ev.get('Judgment issued') or end)
    ctx['settle_date'] = within(ev.get('Settlement signed') or end)
    ctx['response_date'] = ev.get('Response received')
    ctx['poa_date'] = clamp(min(ctx['cd_date'], ctx['soc_date']) - dt.timedelta(days=R.randint(3, 12)), opened - dt.timedelta(days=60), end)
    ctx['customs_date'] = within(opened)
    ctx['tmo_date'] = within(end)
    ctx['licence_date'] = opened - dt.timedelta(days=R.randint(700, 1300))
    app = ctx['apps'][0] if ctx['apps'] else None
    ctx['takedown_date'] = within(d(app['takedown_requested_date']) if app and app['takedown_requested_date'] else ctx['tp_date'] + dt.timedelta(days=R.randint(1, 6)))
    ctx['takedown_confirmed'] = ev.get('Takedown confirmed') or (d(app['removed_date']) if app and app['removed_date'] else None)
    return ctx

# ----------------------------------------------------------------------------- selection
QUOTA = {'Cease-and-desist letter': 22, 'Evidence – test purchase': 18, 'Statement of claim': 17, 'Judgment': 15, 'Power of attorney': 14,
         'Investigation report': 13, 'Takedown notice': 12, 'Expert report': 10, 'Settlement agreement': 9, 'Customs seizure notice': 6,
         'Trademark office decision': 1, 'Licence agreement': 1}   # + 12 pack samples = 150
STATUS_TARGET = {('Skipped', 'Password-protected PDF'): 4, ('Skipped', 'OCR confidence below threshold'): 3, ('Indexed (flagged)', 'Low-confidence pages flagged for review'): 5, ('Pending', 'Queued for reindex'): 3}

def consistent(row, ctx):
    t = row['doc_type']
    if t in ('Statement of claim', 'Expert report'):
        return ctx['court_like'] and ctx['outcome'] != 'Takedown achieved'
    if t == 'Judgment':
        return ctx['court_like']
    return True

def select(D):
    samples = [r for r in D.docs if r['sample_file'] == 'True']
    golden_cases = {r['case_id'] for r in samples}
    cand = [r for r in D.docs if r['sample_file'] != 'True' and r['case_id'] not in golden_cases and consistent(r, D.ctx(r['case_id']))]
    by_case = defaultdict(list)
    for r in cand:
        by_case[r['case_id']].append(r)
    R = rng('select-v1')
    chosen, count = [], Counter()
    def take(r):
        if count[r['doc_type']] < QUOTA[r['doc_type']] and r not in chosen:
            chosen.append(r); count[r['doc_type']] += 1
    for t in ('Customs seizure notice', 'Trademark office decision', 'Licence agreement'):
        for r in cand:
            if r['doc_type'] == t:
                take(r)
    # whole case files first (richest cases, round-robin across countries) so the assistant can tell a full story
    cases = sorted(by_case, key=lambda k: (-len(by_case[k]), R.random()))
    rich = [k for k in cases if len(by_case[k]) >= 4]
    by_country = defaultdict(list)
    for k in rich:
        by_country[D.cases[k]['country']].append(k)
    order = []
    while any(by_country.values()):
        for ctry in sorted(by_country, key=lambda x: -len(by_country[x])):
            if by_country[ctry]:
                order.append(by_country[ctry].pop(0))
    for k in order[:24]:
        for r in by_case[k]:
            take(r)
    rest = cand[:]
    R.shuffle(rest)
    for r in rest:
        take(r)
    # status mix: make sure each index status the D4 page shows has real files behind it
    for (st, why), n in STATUS_TARGET.items():
        have = [r for r in chosen if r['index_status'] == st and r['skip_reason'] == why]
        pool = [r for r in rest if r not in chosen and r['index_status'] == st and r['skip_reason'] == why]
        for r in pool[:max(0, n - len(have))]:
            victims = [x for x in chosen if x['doc_type'] == r['doc_type'] and x['index_status'] == 'Indexed'
                       and x['doc_type'] not in ('Customs seizure notice', 'Trademark office decision', 'Licence agreement')]
            if victims:
                chosen.remove(victims[-1]); chosen.append(r)
    assert sum(QUOTA.values()) == len(chosen) == 138, (len(chosen), Counter(r['doc_type'] for r in chosen))
    return samples, chosen

# ----------------------------------------------------------------------------- names
STEM = {'Cease-and-desist letter': 'Cease_and_Desist', 'Evidence – test purchase': 'Evidence_Test_Purchase', 'Statement of claim': 'Statement_of_Claim',
        'Power of attorney': 'Power_of_Attorney', 'Investigation report': 'Investigation_Report', 'Judgment': 'Judgment', 'Takedown notice': 'Takedown_Notice',
        'Expert report': 'Expert_Report', 'Settlement agreement': 'Settlement_Agreement', 'Customs seizure notice': 'Customs_Seizure_Notice',
        'Trademark office decision': 'Trademark_Office_Decision', 'Licence agreement': 'Licence_Agreement'}
SLUG = {'Cease-and-desist letter': 'cease-and-desist', 'Evidence – test purchase': 'test-purchase-evidence', 'Statement of claim': 'statement-of-claim',
        'Power of attorney': 'power-of-attorney', 'Investigation report': 'investigation-report', 'Judgment': 'judgment', 'Takedown notice': 'takedown-notice',
        'Expert report': 'expert-report', 'Settlement agreement': 'settlement-agreement', 'Customs seizure notice': 'customs-seizure-notice',
        'Trademark office decision': 'tm-office-decision', 'Licence agreement': 'licence-agreement'}
AR_FILE = {'Cease-and-desist letter': 'إنذار قانوني', 'Evidence – test purchase': 'دليل شراء اختباري', 'Statement of claim': 'صحيفة دعوى', 'Power of attorney': 'وكالة',
           'Investigation report': 'تقرير تحقيق', 'Judgment': 'حكم', 'Takedown notice': 'إخطار إزالة', 'Expert report': 'تقرير الخبير',
           'Settlement agreement': 'اتفاقية تسوية', 'Customs seizure notice': 'إخطار حجز جمركي', 'Trademark office decision': 'قرار العلامات',
           'Licence agreement': 'اتفاقية ترخيص'}

def file_name(row, ctx, scanned, taken, dd):
    R = rng('name', row['doc_id'])
    t, cid, lang = row['doc_type'], row['case_id'], row['language']
    for attempt in range(50):
        x = R.random()
        if scanned and x < 0.45:
            name = R.choice([f'scan{R.randint(1000, 9999)}', f'Scan_{dd:%Y%m%d}_{R.randint(80000, 175959):06d}', f'IMG_{dd:%Y%m%d}_{R.randint(1000, 9999)}',
                             f'SCN_{R.randint(100000, 999999)}', f'{cid}_scan', f'Scanned document ({R.randint(2, 19)})'])
        elif lang == 'AR' and x < 0.22:
            name = R.choice([f'{AR_FILE[t]} {cid}', f'{AR_FILE[t]} - {ctx["inf_ar"].split()[0]} {cid}', f'{cid} {AR_FILE[t]}'])
        else:
            y = R.random()
            if y < 0.38: name = f'{cid}_{STEM[t]}_{lang}'
            elif y < 0.55: name = f'{cid}_{SLUG[t]}'
            elif y < 0.68: name = f'{SLUG[t]}_{cid}'
            elif y < 0.78: name = f'{SLUG[t]} {cid}'
            elif y < 0.90: name = f'{SLUG[t]} - {ctx["inf_short"]} (final)'
            else: name = f'{cid}_{SLUG[t]}' + R.choice([' (1)', '_v2', '_signed', ' - copy'])
        name = re.sub(r'[\\/:*?"<>|]', '', name).strip() + '.pdf'
        if name.lower() not in taken:
            taken.add(name.lower())
            return name
    raise RuntimeError('no unique name for ' + row['doc_id'])

def doc_date_for(t, ctx):
    return {'Cease-and-desist letter': ctx['cd_date'], 'Evidence – test purchase': ctx['tp_date'], 'Statement of claim': ctx['soc_date'],
            'Power of attorney': ctx['poa_date'], 'Investigation report': ctx['inv_date'], 'Judgment': ctx['judgment_date'],
            'Takedown notice': ctx['takedown_date'], 'Expert report': ctx['expert_date'], 'Settlement agreement': ctx['settle_date'],
            'Customs seizure notice': ctx['customs_date'], 'Trademark office decision': ctx['tmo_date'], 'Licence agreement': ctx['licence_date']}[t]
