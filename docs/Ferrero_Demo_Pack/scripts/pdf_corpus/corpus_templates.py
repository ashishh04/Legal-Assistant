"""Document templates: one function per fact_document doc_type, each writing English or Arabic.

Every fact comes from the case context (corpus_data.build_ctx), so a case's letter, evidence,
claim, expert report and judgment agree with each other and with fact_case / fact_case_event.
"""
import datetime as dt
from corpus_data import (CLAIMANT, CLAIMANT_ADDR, LEGAL_DEPT, INVESTIGATOR, LAB, FX_FROM_AED, rng, den, dar, dnum, dhijri, money)
import corpus_assets as A
from corpus_assets import wrap

MASC = [  # whole phrases first, then the bare term
    ('دفعت المدعى عليها بأنها اشترت البضاعة بحسن نية من تاجر جملة دون علمها بتقليدها', 'دفع المدعى عليه بأنه اشترى البضاعة بحسن نية من تاجر جملة دون علمه بتقليدها'),
    ('أنكرت المدعى عليها أي استعمال للعلامة، وطعنت في صحة الشراء الاختباري، وطلبت رفض الدعوى', 'أنكر المدعى عليه أي استعمال للعلامة، وطعن في صحة الشراء الاختباري، وطلب رفض الدعوى'),
    ('دفعت المدعى عليها بأن عبواتها مختلفة', 'دفع المدعى عليه بأن عبواته مختلفة'),
    ('المدعى عليها', 'المدعى عليه')]

SOURCE_EN = {'Infringement mailbox': 'a report to its infringement mailbox', 'Brand protection vendor': 'its brand protection vendor',
             'App store monitoring': 'its app store monitoring', 'Intake form': 'an internal intake form',
             'Distributor report': 'a report from an authorised distributor', 'Customs notification': 'a customs notification'}

REP_NAMES = {'UAE': ['Rashid Al Marzouqi', 'Imran Qureshi', 'Tarek Saleh'], 'KSA': ['Majed Al Shehri', 'Bandar Al Zahrani', 'Nasser Al Qahtani'],
             'Egypt': ['Karim Mansour', 'Hany Fathy'], 'Jordan': ['Bassam Odeh', 'Ziad Khalil'], 'Kuwait': ['Yousef Al Enezi', 'Fahad Al Ajmi'],
             'Qatar': ['Hamad Al Naimi', 'Jassim Al Kubaisi'], 'Oman': ['Said Al Hinai', 'Ahmed Al Rawahi'], 'Turkey': ['Mehmet Kaya', 'Burak Şahin'],
             'India': ['Rajesh Gupta', 'Anil Verma']}
REP_NAMES_AR = {'Rashid Al Marzouqi': 'راشد المرزوقي', 'Imran Qureshi': 'عمران قريشي', 'Tarek Saleh': 'طارق صالح', 'Majed Al Shehri': 'ماجد الشهري',
                'Bandar Al Zahrani': 'بندر الزهراني', 'Nasser Al Qahtani': 'ناصر القحطاني', 'Karim Mansour': 'كريم منصور', 'Hany Fathy': 'هاني فتحي',
                'Bassam Odeh': 'بسام عودة', 'Ziad Khalil': 'زياد خليل', 'Yousef Al Enezi': 'يوسف العنزي', 'Fahad Al Ajmi': 'فهد العجمي',
                'Hamad Al Naimi': 'حمد النعيمي', 'Jassim Al Kubaisi': 'جاسم الكبيسي', 'Said Al Hinai': 'سعيد الهنائي', 'Ahmed Al Rawahi': 'أحمد الرواحي',
                'Mehmet Kaya': 'محمد كايا', 'Burak Şahin': 'بوراك شاهين', 'Rajesh Gupta': 'راجيش غوبتا', 'Anil Verma': 'أنيل فيرما'}
STORE_ADDR = {'Google Play': ('Google LLC – Google Play legal removals (trademark complaints)', 'شركة Google LLC – قسم الإزالة القانونية في Google Play (شكاوى العلامات التجارية)'),
              'Apple App Store': ('Apple Inc. – App Store content disputes (intellectual property)', 'شركة Apple Inc. – قسم نزاعات المحتوى في App Store (الملكية الفكرية)'),
              'Huawei AppGallery': ('Huawei Services – AppGallery intellectual property complaints', 'خدمات Huawei – شكاوى الملكية الفكرية في AppGallery'),
              'Samsung Galaxy Store': ('Samsung Electronics – Galaxy Store IP complaints', 'Samsung Electronics – شكاوى الملكية الفكرية في Galaxy Store')}


class X:
    """Per-document generation context."""
    def __init__(self, row, c, assets_dir, doc_date):
        self.row, self.c, self.date = row, c, doc_date
        self.ar = row['language'] == 'AR'
        self.R = rng('doc', row['doc_id'])
        self.dir = assets_dir
        self.id = row['doc_id']

    def L(self, en, ar):
        if not self.ar:
            return en
        if not self.c['inf_entity']:            # an individual domain registrant takes masculine agreement
            for fem, masc in MASC:
                ar = ar.replace(fem, masc)
        return ar

    def D(self, day):
        return dar(day) if self.ar else den(day)

    def M(self, amount):
        return f'{money(amount)} {self.c["currency_ar"]}' if self.ar else f'{self.c["currency"]} {money(amount)}'

    def fee(self, aed):  # a fixed fee expressed in the local currency, rounded to two significant figures
        v = aed * FX_FROM_AED[self.c['currency']]
        mag = 10 ** max(0, len(str(int(v))) - 2)
        return max(mag, round(v / mag) * mag)

    def P(self, amount):  # unit prices: three decimals for KWD/OMR/JOD (fils, baisa), two for other small amounts
        if self.c['currency'] in ('KWD', 'OMR', 'JOD'):
            s = f'{amount:,.3f}'
        elif amount < 100 and amount != int(amount):
            s = f'{amount:,.2f}'
        else:
            s = money(amount)
        return f'{s} {self.c["currency_ar"]}' if self.ar else f'{self.c["currency"]} {s}'

    def H(self, day):  # Hijri date in the document's language
        return dhijri(day, 'AR' if self.ar else 'EN')

    @property
    def inf_label(self):  # registrant names already read 'velora-outlet.shop (registrant)'; don't add a second bracket
        if not self.c['inf_entity']:
            return self.inf
        return f'{self.inf} ({self.L(self.c["inf_type"].lower(), self.c["inf_type_ar"])})'

    @property
    def mark(self):
        return f'{self.c["mark_ar"]} ({self.c["mark"]})' if self.ar else self.c['mark']

    @property
    def claimant(self):
        return CLAIMANT['ar'] if self.ar else CLAIMANT['en']

    @property
    def inf(self):
        return self.c['inf_ar'] if self.ar else self.c['inf']

    @property
    def product(self):
        return self.c['product_ar'] if self.ar else self.c['product'].lower()

    def g(self, fem, masc):  # Arabic agreement with the defendant (companies are feminine)
        return fem if self.c['inf_entity'] else masc

    def path(self, name):
        return self.dir / f'{self.id}_{name}'

    # ---------------------------------------------------------- assets
    def sig(self, who, color='blue'):
        return A.signature(self.path(f'sig_{abs(hash(who)) % 10**6}.png'), self.id + who, color)

    def seal(self, key, lines, ring='', color='blue'):
        return A.seal(self.path(f'seal_{key}.png'), self.id + key, lines, ring_text=ring, color=color, rtl=self.ar)

    def stamp(self, key, lines, color='red'):
        return A.stamp(self.path(f'stamp_{key}.png'), self.id + key, lines, color=color, rtl=self.ar)

    # ---------------------------------------------------------- shared facts
    def rep(self):
        names = REP_NAMES[self.c['inf_country']] if self.c['inf_country'] in REP_NAMES else REP_NAMES['UAE']
        n = names[int(self.c['inf'].encode().hex(), 16) % len(names)]
        return REP_NAMES_AR.get(n, n) if self.ar else n

    def domain(self):
        if self.c['inf_type'] == 'Domain registrant':
            return self.c['inf'].split(' ')[0]
        return f'{self.c["mark"].lower()}-deals.shop'

    def app(self):
        c = self.c
        if c['apps']:
            a = c['apps'][0]
            return dict(name=a['app_name'], store=a['store'], developer=a['developer'], downloads=int(a['est_downloads'] or 10000), app_id=a['app_id'])
        R = rng('app', c['case_id'])
        return dict(name=f'{c["mark"]} {R.choice(["Stickers", "Recipes", "Coupons", "Kids Game", "Wallpapers", "Rewards"])}',
                    store=R.choice(['Google Play', 'Apple App Store', 'Huawei AppGallery']), developer=c['inf'], downloads=R.choice([10000, 50000, 100000]), app_id='')

    def developer_phrase(self):
        a = self.app(); c = self.c
        if a['developer'] == c['inf']:
            return self.L(f'published by {c["inf"]}', f'المنشور باسم {c["inf_ar"]}')
        if a['developer'] == 'Unknown developer':
            return self.L(f'published under an anonymous developer account later attributed to {c["inf"]}',
                          f'المنشور عبر حساب مطوّر مجهول تبيّن لاحقاً ارتباطه بـ{c["inf_ar"]}')
        return self.L(f'published under the developer account “{a["developer"]}”, operated on behalf of {c["inf"]}',
                      f'المنشور عبر حساب المطوّر «{a["developer"]}» الذي يُدار لصالح {c["inf_ar"]}')

    def infringement(self):
        c, t = self.c, self.c['case_type']
        if t.startswith('Trademark infringement'):
            return self.L(f'importing, stocking and selling counterfeit {self.product} bearing a sign identical to the {c["mark"]} mark',
                          f'استيراد وتخزين وبيع {self.product} مقلدة تحمل علامة مطابقة للعلامة {self.mark}')
        if t == 'Online marketplace listing':
            return self.L(f'offering counterfeit {self.product} under the {c["mark"]} mark through listing No. {c["listing_id"]} on the {c["marketplace"]} online marketplace',
                          f'عرض {self.product} مقلدة تحمل العلامة {self.mark} عبر الإعلان رقم {c["listing_id"]} على منصة {c["marketplace"]} للتجارة الإلكترونية')
        if t == 'Mobile app infringement':
            a = self.app()
            return self.L(f'distributing the mobile application “{a["name"]}” on {a["store"]}, {self.developer_phrase()}, which uses the {c["mark"]} name and logo without authorisation',
                          f'توزيع تطبيق الهاتف المحمول «{a["name"]}» عبر {a["store"]}، {self.developer_phrase()}، والذي يستخدم اسم وشعار العلامة {self.mark} دون ترخيص')
        if t == 'Unfair competition':
            return self.L(f'marketing {self.product} in a get-up that imitates the distinctive trade dress of {c["mark"]} products and misleads consumers as to their origin',
                          f'تسويق {self.product} بمظهر يحاكي الشكل المميز لمنتجات {self.mark} بما يضلل المستهلكين بشأن مصدرها')
        if t == 'Customs seizure':
            return self.L(f'importing a consignment of counterfeit {self.product} bearing the {c["mark"]} mark, which was intercepted by {c["court"]}',
                          f'استيراد شحنة من {self.product} المقلدة التي تحمل العلامة {self.mark}، والتي أوقفتها {c["court_ar"]}')
        if t.startswith('Domain'):
            return self.L(f'registering and using the domain name {self.domain()} to sell products under the {c["mark"]} mark',
                          f'تسجيل اسم النطاق {self.domain()} واستخدامه لبيع منتجات تحت العلامة {self.mark}')
        if t.startswith('Packaging'):
            return self.L(f'selling {self.product} in packaging that copies the colour scheme, layout and shape of the {c["mark"]} packaging',
                          f'بيع {self.product} في عبوات تنسخ الألوان والتصميم والشكل المميز لعبوة {self.mark}')
        if t.startswith('Trademark opposition'):
            return self.L(f'applying to register a sign confusingly similar to the {c["mark"]} mark in class {c["nice"]}',
                          f'التقدم بطلب تسجيل علامة مشابهة إلى حد اللبس للعلامة {self.mark} في الفئة {c["nice"]}')
        return self.L(f'importing and selling {c["mark"]} products intended for markets outside the {c["country_en"]} through unauthorised channels',
                      f'استيراد وبيع منتجات {self.mark} المخصصة لأسواق خارج {c["country_ar"]} عبر قنوات غير مرخصة')

    def online(self):
        return self.c['case_type'] in ('Online marketplace listing', 'Mobile app infringement', 'Domain name / cybersquatting')

    def rights_sentence(self):
        c = self.c
        return self.L(f'{CLAIMANT["en"]} is the registered proprietor of the trademark {c["mark"]} ({c["country_en"]} registration No. {c["mark_reg"]}, class {c["nice"]}), '
                      f'used continuously in the region since {c["mark_since"]} for {c["product"].lower()} and registered in {c["registered_in"]}.',
                      f'{CLAIMANT["ar"]} هي المالكة المسجلة للعلامة التجارية {self.mark} المسجلة في {c["country_ar"]} برقم {c["mark_reg"]} في الفئة {c["nice"]} '
                      f'عن منتجات {c["product_ar"]}، والمستعملة في المنطقة بصورة مستمرة منذ عام {c["mark_since"]}.')

    def test_purchase_sentence(self):
        c = self.c
        if c['case_type'] == 'Mobile app infringement':
            return self.L(f'On {den(c["tp_date"])} the application was downloaded and its store listing, icon and in-app screens were captured and notarised.',
                          f'وبتاريخ {dar(c["tp_date"])} جرى تنزيل التطبيق وتوثيق صفحته في المتجر وأيقونته وشاشاته الداخلية.')
        if c['case_type'] == 'Customs seizure':
            return self.L(f'Samples drawn from the consignment on {den(c["tp_date"])} were examined by the Rights Holder’s laboratory (certificate {c["lab_ref"]}) and found counterfeit.',
                          f'وقد فُحصت عينات مسحوبة من الشحنة بتاريخ {dar(c["tp_date"])} لدى مختبر صاحبة الحق (الشهادة رقم {c["lab_ref"]}) وثبت أنها مقلدة.')
        return self.L(f'On {den(c["tp_date"])} a test purchase of {c["tp_units"]} units was made at {self.P(c["unit_price"])} each (receipt No. {c["receipt_no"]}); '
                      f'the laboratory certificate {c["lab_ref"]} confirms that the goods are not genuine.',
                      f'وبتاريخ {dar(c["tp_date"])} أُجري شراء اختباري لعدد {c["tp_units"]} وحدات بسعر {self.P(c["unit_price"])} للوحدة (إيصال رقم {c["receipt_no"]})، '
                      f'وأكدت شهادة المختبر رقم {c["lab_ref"]} أن البضائع غير أصلية.')

    def counsel_block(self, label=None):
        c = self.c
        if c['firm']:
            name, name_ar, title, title_ar = c['partner']
            return dict(label=label, name=self.L(name, name_ar), title=self.L(title, title_ar), org=self.L(c['firm'], c['firm_ar']), sig=self.sig(name))
        return dict(label=label, name=self.L(c['counsel'], c['counsel_ar']), title=self.L(c['counsel_title'], c['counsel_title_ar']),
                    org=self.L(CLAIMANT['en'], CLAIMANT['ar']), sig=self.sig(c['counsel']))

    def letterhead(self, b):
        c = self.c
        if c['firm']:
            b.para(self.L(c['firm'].upper(), c['firm_ar']), align='start', bold=True, size=15, after=0, color='1F3864')
            b.para(self.L('Advocates & Legal Consultants · Intellectual Property', 'محامون ومستشارون قانونيون · الملكية الفكرية'), align='start', size=8.5, after=0, color='555555')
            b.para(self.L(c['firm_addr_en'], c['firm_addr_ar']) + f' · ip@{c["firm_email"]}.demo.local', align='start', size=8, after=0, color='555555')
        else:
            b.para(self.L('DOLCE GROUP INTERNATIONAL S.A.', 'شركة دولتشي جروب إنترناشيونال'), align='start', bold=True, size=15, after=0, color='5A2D0C')
            b.para(self.L(LEGAL_DEPT['en'], LEGAL_DEPT['ar']), align='start', size=8.5, after=0, color='555555')
        b.rule(color='1F3864' if c['firm'] else '5A2D0C', after=10, size=10)

    def court_header(self, b, sub_en, sub_ar, extra=()):
        c = self.c
        b.center(self.L(c['country_en'].upper(), c['country_ar']), bold=True, size=10.5)
        if c['country'] == 'KSA':
            b.center(self.L('Ministry of Justice', 'وزارة العدل'), size=10)
        elif c['country'] == 'Egypt':
            b.center(self.L('In the name of the People', 'باسم الشعب'), size=10, italic=True)
        b.center(self.L(c['court'].upper(), c['court_ar']), bold=True, size=13, before=2)
        b.center(self.L(sub_en, sub_ar), size=10)
        for e in extra:
            b.center(e, size=10)
        b.rule(after=8)

    def translation_note(self, b):
        c = self.c
        if not self.ar and c['country'] not in ('India',):
            who = c['firm'] or 'the Legal Department of ' + CLAIMANT['en']
            lang_src = 'Turkish' if c['country'] == 'Turkey' else 'Arabic'
            b.para(f'Unofficial English translation prepared by {who}. The {lang_src} original prevails.', align='center', italic=True, size=8.5, color='666666', after=6)
        if self.ar and c['country'] in ('Turkey', 'India'):
            b.para('ترجمة عربية غير رسمية لأغراض المتابعة الداخلية؛ النص الأصلي هو المعتمد.', align='center', italic=True, size=8.5, color='666666', after=6)


# =============================================================================== 1. cease-and-desist letter
def cease_and_desist(b, x):
    c = x.c
    x.letterhead(b)
    ref = f'{(c["firm_email"] or "DG-LEGAL").upper()}/{c["case_id"]}/CD'
    b.para(x.L(f'Our ref: {ref}', f'مرجعنا: {ref}'), align='start', after=0, size=9.5)
    b.para(x.L(f'Date: {den(x.date)}', f'التاريخ: {dar(x.date)}'), align='start', after=8, size=9.5)
    b.para(x.L(f'{c["inf"]}', f'السادة / {c["inf_ar"]}'), align='start', bold=True, after=0)
    b.para(x.L(f'{c["inf_addr_en"]}, {c["country_en"]}', f'{c["inf_addr_ar"]}، {c["country_ar"]}'), align='start', after=0)
    b.para(x.L(f'Attention: {x.rep()}, Manager', f'عناية السيد / {x.rep()}، المدير المسؤول'), align='start', after=4)
    method = x.R.choice([('By courier and by email', 'يُسلَّم بالبريد السريع وبالبريد الإلكتروني'), ('By hand and by registered mail', 'يُسلَّم باليد وبالبريد المسجل بعلم الوصول')])
    if x.online():
        method = ('By email and through the platform’s rights-owner channel', 'يُرسل بالبريد الإلكتروني وعبر قناة أصحاب الحقوق في المنصة')
    b.para(x.L(method[0], method[1]), align='start', italic=True, size=9.5, after=8)
    b.para(x.L(f'Re: Infringement of the {c["mark"]} trademark – cease and desist', f'الموضوع: إنذار قانوني بالتوقف عن التعدي على العلامة التجارية {x.mark}'),
           align='start', bold=True, after=8)
    firm = bool(c['firm'])
    cl, cl_ar = ('our client', 'موكلتنا') if firm else ('the Company', 'الشركة')
    who = x.L(f'We act for {CLAIMANT["en"]} (“our client”).', f'نتشرف بإحاطتكم علماً بأننا نمثل {CLAIMANT["ar"]} («موكلتنا»).') if firm else \
        x.L(f'We write on behalf of {CLAIMANT["en"]} (the “Company”).', f'نكتب إليكم بالنيابة عن {CLAIMANT["ar"]} («الشركة»).')
    b.h1(x.L(f'1. {cl[0].upper() + cl[1:]}’s rights', f'1. حقوق {cl_ar}'))
    b.para(who + ' ' + x.rights_sentence())
    b.h1(x.L('2. The infringing activity', '2. المخالفة'))
    b.para(x.L(f'It has come to {cl}’s attention that you are {x.infringement()}. ', f'نما إلى علم {cl_ar} قيامكم بـ{x.infringement()}. ') + x.test_purchase_sentence())
    if c['repeat']:
        b.para(x.L(f'We note that this is not the first matter involving {c["inf"]}: {cl}’s records show {c["inf_cases"]} enforcement files opened against you.',
                   f'ونشير إلى أن هذه ليست المرة الأولى؛ إذ تُظهر سجلات {cl_ar} {c["inf_cases"]} ملفات إنفاذ مفتوحة ضدكم.'))
    b.h1(x.L('3. Legal position', '3. الأساس القانوني'))
    b.para(x.L(f'Your conduct infringes {cl}’s exclusive rights under {c["law_en"]} and constitutes unfair competition. It exposes you to civil liability and, '
               f'where counterfeiting is established, to criminal and administrative sanctions including the seizure and destruction of goods.',
               f'إن ما تقومون به يشكل تعدياً على الحقوق الاستئثارية لـ{cl_ar} وفقاً لأحكام {c["law_ar"]}، فضلاً عن كونه منافسة غير مشروعة، '
               f'ويعرضكم للمسؤولية المدنية والجزائية والإدارية بما في ذلك ضبط البضائع وإتلافها.'))
    b.h1(x.L(f'4. {cl[0].upper() + cl[1:]}’s demands', '4. المطالب'))
    days = c['cd_days']
    b.para(x.L(f'We therefore require you, within {days} days of the date of this letter, to:', f'لذلك نطالبكم، خلال {days} يوماً من تاريخ هذا الإنذار، بما يلي:'), after=3)
    items = [x.L(f'cease immediately all manufacture, import, offer, sale, advertising and distribution of products bearing the {c["mark"]} mark or any confusingly similar sign;',
                 f'التوقف فوراً عن تصنيع واستيراد وعرض وبيع والإعلان عن وتوزيع أي منتجات تحمل العلامة {x.mark} أو أي علامة مشابهة لها؛'),
             x.L(f'withdraw all infringing stock from your premises, warehouses and online channels and deliver it up for destruction under {cl}’s supervision;',
                 f'سحب جميع المنتجات المخالفة من محلاتكم ومستودعاتكم وقنواتكم الإلكترونية وتسليمها لإتلافها تحت إشراف ممثل {cl_ar}؛'),
             x.L('disclose in writing your suppliers, the quantities purchased and sold, and your selling prices;', 'الإفصاح كتابةً عن الموردين والكميات المشتراة والمباعة وأسعار البيع؛')]
    if c['case_type'] == 'Online marketplace listing':
        items.append(x.L(f'remove listing No. {c["listing_id"]} and any similar listing on {c["marketplace"]} or any other platform;', f'إزالة الإعلان رقم {c["listing_id"]} وأي إعلان مماثل على منصة {c["marketplace"]} أو غيرها؛'))
    if c['case_type'] == 'Mobile app infringement':
        items.append(x.L(f'withdraw the application “{x.app()["name"]}” from all app stores and stop using the {c["mark"]} name and logo;', f'سحب التطبيق «{x.app()["name"]}» من جميع متاجر التطبيقات والتوقف عن استخدام اسم وشعار العلامة؛'))
    if c['case_type'].startswith('Domain'):
        items.append(x.L(f'transfer the domain name {x.domain()} to {cl} and take the website offline;', f'نقل اسم النطاق {x.domain()} إلى {cl_ar} وإيقاف الموقع؛'))
    items.append(x.L('sign and return the enclosed written undertaking.', 'توقيع التعهد الكتابي المرفق وإعادته إلينا.'))
    b.numbered(items)
    b.h1(x.L('5. Consequences', '5. التبعات'))
    will = x.g('ستتخذ', 'ستتخذ')
    b.para(x.L(f'If we do not receive a satisfactory response within this period, {cl} will take action without further notice before {c["court"]} and the competent authorities, '
               f'seeking an injunction, compensation, destruction of the goods, publication of the judgment and its costs. All of {cl}’s rights are reserved.',
               f'وفي حال عدم الاستجابة خلال المهلة المحددة، {will} {cl_ar} دون إنذار آخر الإجراءات القانونية أمام {c["court_ar"]} والجهات المختصة، '
               f'للمطالبة بالمنع والتعويض والإتلاف ونشر الحكم، مع تحميلكم كافة الرسوم والمصاريف وأتعاب المحاماة، مع حفظ كافة حقوق {cl_ar} الأخرى.'))
    b.para(x.L('Yours faithfully,', 'وتفضلوا بقبول فائق الاحترام،'), align='start', before=4, after=2)
    blk = x.counsel_block()
    if c['firm']:
        blk['date'] = x.L(f'for and on behalf of {CLAIMANT["en"]}', f'بالنيابة عن {CLAIMANT["ar"]}')
    b.signatures([blk], widths_mm=[95])
    b.para(x.L('Enclosures: trademark registration certificate; test-purchase receipt and photographs; laboratory certificate; form of undertaking.',
               'المرفقات: شهادة تسجيل العلامة؛ إيصال الشراء الاختباري والصور؛ شهادة المختبر؛ نموذج التعهد.'), size=8.5, color='444444')
    if x.R.random() < 0.5:
        liq = max(c['claim'] * 0.05, x.fee(25000))
        b.page_break()
        b.title(x.L('UNDERTAKING', 'تعهد'), size=13, after=8)
        b.para(x.L(f'We, {c["inf"]}, {c["inf_cr_en"]}, irrevocably undertake to {CLAIMANT["en"]} that with effect from the date of signature we shall:',
                   f'نحن {c["inf_ar"]}، {c["inf_cr_ar"]}، نتعهد بصورة نهائية لا رجعة فيها لصالح {CLAIMANT["ar"]} بأن نلتزم اعتباراً من تاريخ التوقيع بما يلي:'))
        b.numbered([x.L(f'not use the {c["mark"]} mark or any confusingly similar sign;', f'عدم استخدام العلامة {x.mark} أو أي علامة مشابهة لها؛'),
                    x.L('deliver up all infringing stock within seven (7) days;', 'تسليم جميع المخزون المخالف خلال سبعة (7) أيام؛'),
                    x.L('pay the agreed costs of this letter;', 'سداد التكاليف المتفق عليها لهذا الإنذار؛'),
                    x.L(f'pay {x.M(liq)} as liquidated damages for each future breach.', f'دفع مبلغ {x.M(liq)} كتعويض اتفاقي عن كل مخالفة مستقبلية.')])
        b.signatures([dict(label=x.L('Signed for the undertaking party', 'التوقيع عن الطرف المتعهد'), name='', title=x.L('Name / title / company stamp', 'الاسم / الصفة / ختم الشركة'), date=x.L('Date:', 'التاريخ:'))], widths_mm=[95])


# =============================================================================== 2. evidence – test purchase
def evidence_test_purchase(b, x):
    c = x.c
    b.para(x.L(INVESTIGATOR['en'].upper(), INVESTIGATOR['ar']), align='start', bold=True, size=13, color='0B4F6C', after=0)
    b.para(x.L('Field operations · Gulf & Levant', 'العمليات الميدانية · الخليج والمشرق'), align='start', size=8.5, color='555555', after=0)
    b.rule(color='0B4F6C', size=10)
    b.title(x.L('TEST PURCHASE EVIDENCE RECORD', 'محضر توثيق شراء اختباري'), size=14)
    b.center(x.L(f'Record {c["bg_ref"]}-TP · Case {c["case_id"]} · {den(x.date)}', f'المحضر رقم {c["bg_ref"]}-TP · القضية {c["case_id"]} · {dar(x.date)}'), size=9.5, after=8)
    app = c['case_type'] == 'Mobile app infringement'
    if app:
        channel = 'app'
    elif c['case_type'].startswith('Domain'):
        channel = 'domain'
    elif c['case_type'] == 'Online marketplace listing' or c['inf_type'] == 'Online seller':
        channel = 'marketplace'
    else:
        channel = 'store'
    if channel == 'marketplace':
        method = x.L(f'Online order on {c["marketplace"]} (order No. {c["order_no"]}), delivered to a controlled address', f'طلب إلكتروني عبر منصة {c["marketplace"]} (طلب رقم {c["order_no"]}) مع التسليم إلى عنوان خاضع للرقابة')
        place = x.L(f'{c["marketplace"]} store of {c["inf"]} (listing No. {c["listing_id"]})', f'متجر {c["inf_ar"]} على منصة {c["marketplace"]} (إعلان رقم {c["listing_id"]})')
    elif app:
        a = x.app()
        method = x.L(f'Download and in-app purchase from {a["store"]} on a forensic handset, screen-recorded', f'تنزيل التطبيق وإجراء شراء داخلي من {a["store"]} على جهاز مخصص للأدلة مع تسجيل الشاشة')
        place = x.L(f'“{a["name"]}” on {a["store"]}', f'«{a["name"]}» على {a["store"]}')
    elif channel == 'domain':
        method = x.L(f'Order placed on {x.domain()} with cash on delivery', f'طلب عبر الموقع {x.domain()} مع الدفع عند الاستلام')
        place = x.domain()
    else:
        method = x.L('Covert in-store purchase by two investigators, video-recorded', 'شراء سري من المحل بواسطة محققَين اثنين مع تسجيل فيديو')
        place = x.L(f'{c["inf"]}, {c["inf_addr_en"]}', f'{c["inf_ar"]}، {c["inf_addr_ar"]}')
    b.kv([[x.L('Rights holder', 'صاحب الحق'), x.claimant], [x.L('Mark', 'العلامة'), f'{x.mark} · {x.L("reg.", "تسجيل رقم")} {c["mark_reg"]} · {x.L("class", "الفئة")} {c["nice"]}'],
          [x.L('Target', 'الجهة المستهدفة'), x.inf_label], [x.L('Location / channel', 'الموقع / القناة'), place],
          [x.L('Date of purchase', 'تاريخ الشراء'), f'{x.D(c["tp_date"])} · {x.R.randint(10, 20)}:{x.R.randint(10, 59)}'],
          [x.L('Method', 'الطريقة'), method], [x.L('Investigator', 'المحقق'), x.L(f'Field investigator {c["inv_code"]} (identity on file)', f'المحقق الميداني {c["inv_code"]} (الهوية محفوظة بالملف)')],
          [x.L('Instructing counsel', 'المستشار المكلِّف'), x.L(f'{c["counsel"]}, {c["counsel_title"]}', f'{c["counsel_ar"]}، {c["counsel_title_ar"]}')]])
    b.h1(x.L('1. Items purchased', '1. المواد المشتراة'))
    units = c['tp_units'] if not app else 1
    price = c['unit_price']
    b.table([x.L('Item', 'الصنف'), x.L('Qty', 'الكمية'), x.L('Unit price', 'سعر الوحدة'), x.L('Total', 'الإجمالي'), x.L('Batch code seen', 'رمز التشغيلة')],
            [[f'{c["mark"]} {x.L(c["unit_en"], c["unit_ar"])}', str(units), x.P(price), x.P(price * units), f'L{x.R.randint(100000, 999999)}']], [62, 18, 30, 30, 30])
    b.para(x.L(f'Authorised retail price of the genuine product: {x.P(c["genuine_price"])}. Payment by {"card ending " + str(x.R.randint(1000, 9999)) if x.R.random() < 0.5 else "cash"}; receipt No. {c["receipt_no"]}.',
               f'سعر التجزئة المعتمد للمنتج الأصلي: {x.P(c["genuine_price"])}. الدفع {"ببطاقة تنتهي بالأرقام " + str(x.R.randint(1000, 9999)) if x.R.random() < 0.5 else "نقداً"}؛ الإيصال رقم {c["receipt_no"]}.'))
    b.h1(x.L('2. Exhibits', '2. المستندات المرفقة'))
    photo = A.product_photo(x.path('photo.jpg'), x.id, c['mark'], c['product'], [f'EXHIBIT {c["bg_ref"]}-1', c['case_id'], f'Seal {c["seal_no"]}', dnum(c['tp_date'])])
    b.image(photo, 120, caption=x.L(f'Exhibit 1 – sample purchased on {den(c["tp_date"])}, sealed under {c["seal_no"]}.', f'المستند 1 – العينة المشتراة بتاريخ {dar(c["tp_date"])} والمختومة بالختم {c["seal_no"]}.'))
    if channel == 'store':
        rc = A.receipt(x.path('receipt.jpg'), x.id, c['inf'], f'{c["inf_city"]}, {c["inf_country"]}', [(f'{c["mark"]} {c["unit_en"]}', units, float(price))],
                       c['currency'], c['vat'], c['tp_date'], c['receipt_no'], 'CASH' if x.R.random() < 0.5 else f'CARD ****{x.R.randint(1000, 9999)}')
        b.image(rc, 62, caption=x.L(f'Exhibit 2 – purchase receipt No. {c["receipt_no"]}.', f'المستند 2 – إيصال الشراء رقم {c["receipt_no"]}.'))
    else:
        kind = channel
        a = x.app() if app else {}
        cap = A.listing_capture(x.path('capture.png'), x.id, kind, dict(mark=c['mark'], product=c['product'], title=a.get('name') or f'{c["mark"]} {c["product"]} – {c["unit_en"]} – original imported – best price',
                                price=int(price) if price >= 2 else 2, old_price=int(c['genuine_price']), seller=c['inf'], store=(a.get('store', '') + ' – store listing') if app else c['marketplace'],
                                developer=a.get('developer', ''), downloads=f'{a.get("downloads", 10000) // 1000}K+', domain=x.domain(), when=c['tp_date'], currency=c['currency'],
                                listing_id=c['listing_id'], city=c['inf_city'], where=x.domain() if kind == 'domain' else (a.get('store', '') or c['marketplace'])))
        b.image(cap, 150, caption=x.L('Exhibit 2 – capture of the listing at the time of purchase.', 'المستند 2 – صورة الإعلان وقت الشراء.'))
    b.h1(x.L('3. Chain of custody', '3. سلسلة الحيازة'))
    t0 = c['tp_date']
    b.table([x.L('Date', 'التاريخ'), x.L('From', 'من'), x.L('To', 'إلى'), x.L('Seal', 'الختم'), x.L('Condition', 'الحالة')],
            [[dnum(t0), x.L(f'Seller – {x.inf}', f'البائع – {x.inf}'), c['inv_code'], c['seal_no'], x.L('Sealed, photographed', 'مختوم ومصوّر')],
             [dnum(t0), c['inv_code'], x.L('BrandGuard evidence room', 'غرفة الأدلة لدى براند جارد'), c['seal_no'], x.L('Seal intact', 'الختم سليم')],
             [dnum(t0 + dt.timedelta(days=1)), x.L('BrandGuard evidence room', 'غرفة الأدلة لدى براند جارد'), x.L('Authentication laboratory', 'مختبر التحقق'), c['seal_no'], x.L('Seal intact', 'الختم سليم')]],
            [24, 40, 46, 26, 30], size=8.5)
    b.h1(x.L('4. Initial observations', '4. الملاحظات الأولية'))
    b.bullets([x.L('No security hologram on the outer pack; batch code inkjet-printed rather than laser-etched.', 'غياب الملصق الأمني المجسم على العبوة الخارجية؛ رمز التشغيلة مطبوع بالحبر وليس محفوراً بالليزر.'),
               x.L(f'Selling price {round(100 * (1 - price / c["genuine_price"]))}% below the authorised retail price.', f'سعر البيع أقل بنسبة {round(100 * (1 - price / c["genuine_price"]))}% من سعر التجزئة المعتمد.'),
               x.L('Print registration and colours differ visibly from genuine reference samples.', 'اختلاف واضح في دقة الطباعة والألوان مقارنةً بالعينات المرجعية الأصلية.')])
    b.para(x.L('I confirm that this record is accurate and that the samples were kept sealed from purchase until delivery to the laboratory.',
               'أقر بأن هذا المحضر صحيح وأن العينات ظلت مختومة منذ الشراء حتى تسليمها إلى المختبر.'), italic=True, before=4)
    b.signatures([dict(label=x.L('Investigator', 'المحقق'), name=c['inv_code'], title=INVESTIGATOR['ar' if x.ar else 'en'], sig=x.sig(c['inv_code'], 'black')),
                  dict(label=x.L('Reviewed', 'المراجعة'), name=x.L('Youssef Nasser', 'يوسف ناصر'), title=x.L('Brand Protection Manager', 'مدير حماية العلامات التجارية'), org=x.claimant, sig=x.sig('Youssef Nasser'))])


# =============================================================================== 3. statement of claim
def statement_of_claim(b, x):
    c = x.c
    b.center(x.L(f'BEFORE {c["court"].upper()}', f'أمام {c["court_ar"]}'), bold=True, size=12.5)
    b.center(x.L(f'Commercial Case No. {c["court_ref"]}', f'الدعوى التجارية رقم {c["court_ref"]}'), bold=True)
    b.title(x.L('STATEMENT OF CLAIM', 'صحيفة دعوى'), size=15, before=6)
    b.center(x.L(f'Filed on {den(x.date)}', f'مقدمة بتاريخ {dar(x.date)}') + (f' ({x.H(x.date)})' if c['country'] == 'KSA' else ''), size=10)
    b.rule()
    x.translation_note(b)
    b.h1(x.L('Parties', 'أطراف الدعوى'))
    rep = x.L(f'represented by {c["firm"]}, {c["firm_addr_en"]}', f'ويمثلها {c["firm_ar"]}، {c["firm_addr_ar"]}') if c['firm'] else \
        x.L(f'represented by its in-house counsel {c["counsel"]} under power of attorney', f'ويمثلها مستشارها القانوني {c["counsel_ar"]} بموجب وكالة')
    b.para([(x.L('Claimant: ', 'المدعية: '), {'bold': True}), (x.L(f'{CLAIMANT["en"]}, a société anonyme incorporated in Luxembourg, {CLAIMANT_ADDR["en"]}; ', f'{CLAIMANT["ar"]}، شركة مساهمة مسجلة في لوكسمبورغ، {CLAIMANT_ADDR["ar"]}؛ ') + rep + '.', {})])
    b.para([(x.L('Defendant: ', x.g('المدعى عليها: ', 'المدعى عليه: ')), {'bold': True}),
            (x.L(f'{c["inf"]}, {c["inf_type"].lower()}, {c["inf_cr_en"]}, {c["inf_addr_en"]}, {c["country_en"]}.', f'{c["inf_ar"]}، {c["inf_type_ar"]}، {c["inf_cr_ar"]}، {c["inf_addr_ar"]}، {c["country_ar"]}.'), {})])
    b.h1(x.L('Facts', 'الوقائع'))
    facts = [x.rights_sentence(),
             x.L(f'Through {SOURCE_EN.get(c["source"], c["source"].lower())}, the Claimant learned that the Defendant was {x.infringement()}. ', f'علمت المدعية عن طريق {source_ar(c["source"])} أن {x.g("المدعى عليها تقوم", "المدعى عليه يقوم")} بـ{x.infringement()}. ') + x.test_purchase_sentence(),
             x.L(f'A cease-and-desist letter was served on {den(c["cd_date"])}. ', f'وُجّه إنذار قانوني بتاريخ {dar(c["cd_date"])}. ') +
             (x.L(f'The Defendant replied on {den(c["response_date"])} denying infringement and refusing to sign the undertaking.', f'وردّت {x.g("المدعى عليها", "المدعى عليه")} بتاريخ {dar(c["response_date"])} بإنكار التعدي ورفض توقيع التعهد.')
              if c['response_date'] and c['response_date'] <= x.date else x.L('The Defendant did not respond.', f'ولم {x.g("تستجب المدعى عليها", "يستجب المدعى عليه")} للإنذار.')),
             x.L(f'The Claimant estimates its loss, including lost sales, enforcement costs and harm to the reputation of the mark, at {x.M(c["claim"])}.',
                 f'وتقدّر المدعية الأضرار التي لحقت بها، بما فيها المبيعات الفائتة وتكاليف الإنفاذ والإضرار بسمعة العلامة، بمبلغ {x.M(c["claim"])}.') if c['claim'] else
             x.L('At this stage the Claimant seeks injunctive relief only and reserves its right to claim compensation once the Defendant’s sales have been disclosed.',
                 'وتقتصر طلبات المدعية في هذه المرحلة على المنع والإزالة، مع حفظ حقها في المطالبة بالتعويض بعد الإفصاح عن حجم المبيعات.')]
    b.numbered(facts)
    b.h1(x.L('Legal grounds', 'الأسانيد القانونية'))
    b.para(x.L(f'Under {c["law_en"]}, the registration confers on the Claimant the exclusive right to use the mark and to prevent third parties from using an identical or similar sign '
               'for identical or similar goods where such use is likely to cause confusion. The Defendant’s acts also constitute unfair competition and give rise to liability in tort.',
               f'تخوّل أحكام {c["law_ar"]} المدعيةَ بموجب التسجيل الحق الاستئثاري في استعمال العلامة ومنع الغير من استعمال علامة مطابقة أو مشابهة على سلع مطابقة أو مشابهة متى كان من شأن ذلك إحداث اللبس، '
               'كما تشكل أفعال المدعى عليها منافسة غير مشروعة وخطأً موجباً للتعويض وفق قواعد المسؤولية التقصيرية.'))
    b.h1(x.L('Evidence', 'المستندات المؤيدة'))
    ev = [x.L('Exhibit C-1: trademark registration certificate and renewal.', 'حافظة المستندات م-1: شهادة تسجيل العلامة وتجديدها.'),
          x.L(f'Exhibit C-2: test-purchase evidence record {c["bg_ref"]}-TP with receipt and photographs.', f'م-2: محضر الشراء الاختباري {c["bg_ref"]}-TP مع الإيصال والصور.'),
          x.L(f'Exhibit C-3: laboratory certificate {c["lab_ref"]}.', f'م-3: شهادة المختبر رقم {c["lab_ref"]}.'),
          x.L(f'Exhibit C-4: cease-and-desist letter dated {den(c["cd_date"])} and proof of delivery.', f'م-4: الإنذار القانوني المؤرخ {dar(c["cd_date"])} وما يفيد التسليم.'),
          x.L('Exhibit C-5: power of attorney.', 'م-5: سند الوكالة.')]
    b.numbered(ev, fmt='{n}.')
    b.h1(x.L('Relief sought', 'الطلبات'))
    b.para(x.L('The Claimant respectfully asks the Court to:', 'تلتمس المدعية من عدالة المحكمة الحكم بما يلي:'), after=3)
    relief = [x.L(f'order the Defendant to pay {x.M(c["claim"])} as compensation for material and moral damage, with legal interest from the date of judgment;',
                  f'إلزام {x.g("المدعى عليها", "المدعى عليه")} بأن {x.g("تؤدي", "يؤدي")} للمدعية مبلغ {x.M(c["claim"])} تعويضاً عن الأضرار المادية والأدبية مع الفائدة القانونية من تاريخ الحكم؛')] if c['claim'] else []
    relief += [x.L(f'order the Defendant to cease all use of the {c["mark"]} mark or any confusingly similar sign;', f'منع {x.g("المدعى عليها", "المدعى عليه")} من استعمال العلامة {x.mark} أو أي علامة مشابهة لها؛'),
              x.L('order the seizure and destruction of the infringing goods, packaging and printing materials at the Defendant’s expense;', 'مصادرة البضائع والعبوات وأدوات الطباعة المخالفة وإتلافها على نفقة المدعى عليها؛'),
              x.L('order publication of a summary of the judgment in two daily newspapers at the Defendant’s expense;', 'نشر ملخص الحكم في صحيفتين يوميتين على نفقة المدعى عليها؛'),
              x.L('order the Defendant to bear the court fees, expenses and advocate’s fees.', 'إلزام المدعى عليها بالرسوم والمصاريف ومقابل أتعاب المحاماة.')]
    if c['case_type'].startswith('Domain'):
        relief.insert(2, x.L(f'order the transfer of the domain name {x.domain()} to the Claimant;', f'الأمر بنقل اسم النطاق {x.domain()} إلى المدعية؛'))
    if c['case_type'] == 'Mobile app infringement':
        relief.insert(2, x.L(f'order the Defendant to withdraw the application “{x.app()["name"]}” from all app stores;', f'إلزام المدعى عليها بسحب التطبيق «{x.app()["name"]}» من جميع المتاجر؛'))
    b.numbered(relief)
    blk = x.counsel_block(x.L('For the Claimant', 'عن المدعية'))
    b.signatures([blk, dict(label=x.L('Registry', 'قلم الكتاب'), name='', title=x.L(f'Filed {den(x.date)}', f'قُيّدت بتاريخ {dar(x.date)}'),
                            seal=x.stamp('filed', [x.L('FILED', 'تم القيد'), x.L(c['court'], c['court_ar']), x.L(f'{den(x.date)} · No. {c["court_ref"]}', f'{dar(x.date)} · رقم {c["court_ref"]}')]), seal_w=48)],
                 widths_mm=[80, 84])


def source_ar(s):
    return {'Infringement mailbox': 'صندوق بريد البلاغات', 'Brand protection vendor': 'مزود خدمات حماية العلامات', 'App store monitoring': 'رصد متاجر التطبيقات',
            'Intake form': 'نموذج الإبلاغ الداخلي', 'Distributor report': 'بلاغ من أحد الموزعين', 'Customs notification': 'إخطار جمركي'}.get(s, s)


# =============================================================================== 4. power of attorney
def power_of_attorney(b, x):
    c = x.c
    signer = x.R.choice([('Daniel Weber', 'دانيال فيبر', 'Regional General Counsel', 'المستشار العام الإقليمي'), ('Mariam Al Suwaidi', 'مريم السويدي', 'Head of Legal', 'رئيس الإدارة القانونية')])
    b.title(x.L('SPECIAL POWER OF ATTORNEY', 'وكالة خاصة'), size=15, after=2)
    b.center(x.L(f'No. POA-{c["case_id"][3:]}-{x.date.year} · {den(x.date)}', f'رقم POA-{c["case_id"][3:]}-{x.date.year} · {dar(x.date)}'), size=9.5, after=8)
    b.rule()
    b.para(x.L(f'{CLAIMANT["en"]}, a société anonyme incorporated under the laws of the Grand Duchy of Luxembourg, with registered office at {CLAIMANT_ADDR["en"]} (the “Principal”), '
               f'represented by {signer[0]}, {signer[2]}, duly authorised by resolution of the board of directors,',
               f'إن {CLAIMANT["ar"]}، شركة مساهمة مؤسسة وفقاً لقوانين دوقية لوكسمبورغ الكبرى، ومقرها {CLAIMANT_ADDR["ar"]} («الموكِّلة»)، '
               f'ويمثلها {signer[1]} بصفة {signer[3]} بموجب قرار مجلس الإدارة،'))
    if c['firm']:
        p1, p2 = c['partner'], c['associate']
        att_en = f'{p1[0]} and {p2[0]} of {c["firm"]}, {c["firm_addr_en"]}, jointly or severally'
        att_ar = f'{p1[1]} و{p2[1]} من {c["firm_ar"]}، {c["firm_addr_ar"]}، مجتمعين أو منفردين'
    else:
        att_en = f'{c["counsel"]} ({c["counsel_title"]}) and Ahmed Darwish (Paralegal) of the Principal’s Legal Department, jointly or severally'
        att_ar = f'{c["counsel_ar"]} ({c["counsel_title_ar"]}) وأحمد درويش (مساعد قانوني) من الإدارة القانونية للموكِّلة، مجتمعين أو منفردين'
    b.para(x.L(f'hereby appoints {att_en} (the “Attorneys”) to act in its name and on its behalf in {c["country_en"]} in all matters concerning the protection and enforcement of its '
               f'trademarks, including the {c["mark"]} mark (registration No. {c["mark_reg"]}), and in particular in matter {c["case_id"]} against {c["inf"]}, with the following powers:',
               f'توكِّل بموجب هذا {att_ar} («الوكلاء») في التصرف باسمها ونيابةً عنها في {c["country_ar"]} في جميع المسائل المتعلقة بحماية علاماتها التجارية وإنفاذ الحقوق المترتبة عليها، '
               f'بما فيها العلامة {x.mark} (تسجيل رقم {c["mark_reg"]})، وعلى وجه الخصوص في الملف {c["case_id"]} ضد {c["inf_ar"]}، ولهم في سبيل ذلك الصلاحيات الآتية:'))
    powers = [x.L('to represent the Principal before all courts of every degree, the public prosecution, police, customs, economic and municipal authorities and the trademark office;',
                  'تمثيل الموكِّلة أمام جميع المحاكم على اختلاف درجاتها والنيابة العامة والشرطة والجمارك والدوائر الاقتصادية والبلديات وإدارة العلامات التجارية؛'),
              x.L('to file, sign and withdraw complaints, statements of claim, appeals, oppositions and applications for precautionary seizure;', 'تقديم وتوقيع وسحب الشكاوى وصحف الدعاوى والطعون والاعتراضات وطلبات الحجز التحفظي؛'),
              x.L('to appoint and challenge experts, attend inspections and the destruction of goods, and receive notices;', 'تعيين الخبراء وردّهم وحضور المعاينات وعمليات الإتلاف واستلام الإعلانات؛'),
              x.L('to negotiate and sign settlements and undertakings, and to receive amounts awarded or agreed and give receipts;', 'التفاوض على التسويات والتعهدات وتوقيعها، وقبض المبالغ المحكوم بها أو المتفق عليها وإعطاء المخالصات؛'),
              x.L('to delegate all or part of these powers to another lawyer.', 'توكيل الغير في كل ما ذُكر أو بعضه.')]
    b.numbered(powers, fmt='{a})')
    valid = x.date.replace(year=x.date.year + 3) if not (x.date.month == 2 and x.date.day == 29) else x.date.replace(year=x.date.year + 3, day=28)
    b.para(x.L(f'This power of attorney is valid until {den(valid)} unless revoked earlier in writing. It is governed by the laws of {c["country_en"]}.',
               f'تسري هذه الوكالة حتى {dar(valid)} ما لم تُلغَ كتابةً قبل ذلك، وتخضع لقوانين {c["country_ar"]}.'))
    b.signatures([dict(label=x.L('For the Principal', 'عن الموكِّلة'), name=x.L(signer[0], signer[1]), title=x.L(signer[2], signer[3]), org=x.claimant, sig=x.sig(signer[0]),
                       seal=x.seal('corp', ['DOLCE GROUP', 'INTERNATIONAL S.A.', 'LUXEMBOURG'], ring='DOLCE GROUP INTERNATIONAL', color='blue'), seal_w=24)], widths_mm=[110])
    b.h2(x.L('Notarial certification', 'التصديق'))
    b.para(x.L(f'Signed before me, Maître Anne Schmit, Notary in Luxembourg, on {den(x.date)}, register No. {x.R.randint(1200, 9800)}/{x.date.year}. '
               f'Apostille / legalisation No. {x.R.randint(10000, 99999)} for use in {c["country_en"]}.',
               f'وُقّعت أمامي، آن شميت، الكاتب العدل في لوكسمبورغ، بتاريخ {dar(x.date)}، سجل رقم {x.R.randint(1200, 9800)}/{x.date.year}. '
               f'تصديق / أبوستيل رقم {x.R.randint(10000, 99999)} للاستعمال في {c["country_ar"]}.'), size=9)
    b.signatures([dict(label=x.L('Notary', 'الكاتب العدل'), name='Me Anne Schmit', title=x.L('Notary, Luxembourg', 'كاتب عدل، لوكسمبورغ'), sig=x.sig('Anne Schmit', 'black'),
                       seal=x.seal('notary', ['NOTARY', 'PUBLIC'], ring='GRAND DUCHY OF LUXEMBOURG', color='purple'), seal_w=24)], widths_mm=[110])


# =============================================================================== 5. investigation report
def investigation_report(b, x):
    c = x.c
    b.title(x.L('INVESTIGATION REPORT', 'تقرير تحقيق'), size=15)
    b.center(x.L(f'{INVESTIGATOR["en"]} – prepared for the Legal Department of {CLAIMANT["en"]}', f'{INVESTIGATOR["ar"]} – مُعد للإدارة القانونية في {CLAIMANT["ar"]}'), size=9.5)
    b.center(x.L(f'Report {c["bg_ref"]} · Case {c["case_id"]} · {den(x.date)}', f'التقرير {c["bg_ref"]} · القضية {c["case_id"]} · {dar(x.date)}'), size=9.5, after=6)
    b.rule()
    b.kv([[x.L('Subject', 'الجهة محل التحقيق'), f'{x.inf} · {x.L(c["inf_type"].lower(), c["inf_type_ar"])} · {x.L(c["inf_city"], c["inf_city_ar"])}'],
          [x.L('Mark / products', 'العلامة / المنتجات'), f'{x.mark} · {x.product}'], [x.L('Trigger', 'مصدر البلاغ'), x.L(c['source'], source_ar(c['source']))],
          [x.L('Priority', 'الأولوية'), x.L(c['priority'], {'High': 'عالية', 'Medium': 'متوسطة', 'Low': 'منخفضة'}.get(c['priority'], c['priority']))]])
    b.h1(x.L('1. Objective', '1. الهدف'))
    b.para(x.L(f'To establish whether {c["inf"]} deals in products infringing the {c["mark"]} mark, to identify its sources of supply, and to secure evidence admissible in civil and administrative proceedings in {c["country_en"]}.',
               f'التحقق مما إذا كانت {c["inf_ar"]} تتعامل في منتجات تتعدى على العلامة {x.mark}، وتحديد مصادر التوريد، وجمع أدلة مقبولة أمام الجهات القضائية والإدارية في {c["country_ar"]}.'))
    b.h1(x.L('2. Method', '2. المنهجية'))
    b.para(x.L(f'Desk research of public registers and online channels, two site visits and a test purchase on {den(c["tp_date"])} (record {c["bg_ref"]}-TP). '
               f'Samples were sealed under {c["seal_no"]} and delivered to the {LAB["en"]} within 24 hours.',
               f'بحث مكتبي في السجلات العامة والقنوات الإلكترونية، وزيارتان ميدانيتان، وشراء اختباري بتاريخ {dar(c["tp_date"])} (المحضر {c["bg_ref"]}-TP). '
               f'خُتمت العينات بالختم {c["seal_no"]} وسُلّمت إلى {LAB["ar"]} خلال 24 ساعة.'))
    b.h1(x.L('3. Findings', '3. النتائج'))
    b.table([x.L('Check', 'معيار الفحص'), x.L('Genuine reference', 'المرجع الأصلي'), x.L('Sample', 'العينة'), x.L('Result', 'النتيجة')],
            [[x.L('Security hologram', 'الملصق الأمني'), x.L('Present, colour-shifting', 'موجود ومتغير اللون'), x.L('Absent', 'غير موجود'), x.L('Fail', 'غير مطابق')],
             [x.L('Batch code', 'رمز التشغيلة'), x.L('L + 7 digits, laser', 'L + 7 أرقام، ليزر'), x.L('Inkjet, 6 digits', 'حبر، 6 أرقام'), x.L('Fail', 'غير مطابق')],
             [x.L('Packaging print', 'طباعة العبوة'), x.L('Pantone-matched', 'ألوان معتمدة'), x.L('Colour shift, blurred', 'انحراف لوني وتشوش'), x.L('Fail', 'غير مطابق')],
             [x.L('Net weight', 'الوزن الصافي'), x.L('As declared ± 2 g', 'كما هو مُعلن ± 2 غ'), f'− {x.R.randint(6, 15)} g', x.L('Fail', 'غير مطابق')],
             [x.L('Price point', 'سعر البيع'), x.P(c['genuine_price']), x.P(c['unit_price']), x.L('Indicative', 'مؤشر')]], [40, 44, 44, 32], size=8.5)
    b.para(x.L(f'The laboratory certificate {c["lab_ref"]} confirms that the samples were not manufactured by or under licence from the Rights Holder.',
               f'تؤكد شهادة المختبر رقم {c["lab_ref"]} أن العينات لم تُصنّع من قبل صاحبة الحق أو بترخيص منها.'))
    b.h1(x.L('4. Observations and supply chain', '4. الملاحظات وسلسلة التوريد'))
    stock = c['stock_seen']
    b.para(x.L(f'Approximately {stock} units of the same product were visible in stock. Staff indicated that goods arrive every {x.R.choice(["week", "two weeks", "month"])} '
               f'from {x.R.choice(["a wholesaler in Sharjah", "an importer in Jebel Ali", "a trader in Al Batha, Riyadh", "a supplier in Mersin", "an online wholesale group"])}. '
               + (f'{c["inf"]} is a repeat offender with {c["inf_cases"]} matters on file.' if c['repeat'] else 'No previous matters are recorded against the subject.'),
               f'شوهد في المخزون نحو {stock.replace("about", "حوالي")} وحدة من المنتج نفسه. وأفاد العاملون بأن البضائع تصل {x.R.choice(["أسبوعياً", "كل أسبوعين", "شهرياً"])} '
               f'من {x.R.choice(["تاجر جملة في الشارقة", "مستورد في جبل علي", "تاجر في البطحاء بالرياض", "مورّد في مرسين", "مجموعة بيع بالجملة عبر الإنترنت"])}. '
               + (f'وتُعد {c["inf_ar"]} من المخالفين المتكررين ولديها {c["inf_cases"]} ملفات مسجلة.' if c['repeat'] else 'ولا توجد ملفات سابقة مسجلة ضد الجهة.')))
    if x.R.random() < 0.6:
        photo = A.product_photo(x.path('photo.jpg'), x.id, c['mark'], c['product'], [f'{c["bg_ref"]}', c['case_id'], f'Seal {c["seal_no"]}'])
        b.image(photo, 105, caption=x.L('Figure 1 – sample secured during the test purchase.', 'الشكل 1 – العينة المضبوطة أثناء الشراء الاختباري.'))
    b.h1(x.L('5. Recommendation', '5. التوصية'))
    rec = x.L(f'Serve a cease-and-desist letter, request supplier disclosure and, failing compliance, file proceedings before {c["court"]}. The evidence meets the standard applied to test purchases in {c["country_en"]}.',
              f'توجيه إنذار قانوني، وطلب الإفصاح عن الموردين، وفي حال عدم الامتثال رفع الدعوى أمام {c["court_ar"]}. وتستوفي الأدلة المعايير المعتمدة للشراء الاختباري في {c["country_ar"]}.')
    b.para(rec)
    b.signatures([dict(label=x.L('Lead investigator', 'المحقق الرئيسي'), name=c['inv_code'], title=INVESTIGATOR['ar' if x.ar else 'en'], sig=x.sig(c['inv_code'], 'black')),
                  dict(label=x.L('Reviewed by', 'روجع من قبل'), name=x.L(c['counsel'], c['counsel_ar']), title=x.L(c['counsel_title'], c['counsel_title_ar']), sig=x.sig(c['counsel']))])


# =============================================================================== 6. judgment
LOSS_REASON = {
    'online': ('The Claimant did not establish that the listing targeted consumers in the State or that any sale was concluded there; the screenshots relied on were not notarised.',
               'لم تُثبت المدعية أن الإعلان موجه إلى المستهلكين في الدولة أو أن أي عملية بيع تمت فيها، كما أن صور الشاشة المقدمة غير موثقة.'),
    'unfair': ('Comparing the get-up as a whole, the Court finds the differences in name, colour and layout sufficient to exclude a likelihood of confusion; the shared elements are common to the trade.',
               'بمقارنة المظهر العام في مجمله، ترى المحكمة أن الفروق في الاسم والألوان والتصميم كافية لنفي احتمال اللبس، وأن العناصر المشتركة شائعة في هذا المجال التجاري.'),
    'goods': ('The test purchase was not carried out under judicial supervision, the chain of custody of the samples was broken, and the Defendant produced invoices showing purchase from an authorised distributor.',
              'لم يتم الشراء الاختباري تحت إشراف قضائي، وانقطعت سلسلة حيازة العينات، وقُدّمت فواتير تثبت الشراء من موزع معتمد.')}

def judgment(b, x):
    c = x.c
    hij = f' ({x.H(x.date)})' if c['country'] == 'KSA' else ''
    x.court_header(b, f'Commercial Circuit – Case No. {c["court_ref"]}', f'الدائرة التجارية – القضية رقم {c["court_ref"]}',
                   [x.L(f'Judgment pronounced in open court on {den(x.date)}{hij}', f'صدر الحكم في جلسة علنية بتاريخ {dar(x.date)}{hij}')])
    x.translation_note(b)
    outcome = c['outcome']
    b.h1(x.L('Parties', 'أطراف الدعوى'))
    rep = x.L(f'represented by {c["firm"]}', f'ويمثلها {c["firm_ar"]}') if c['firm'] else x.L(f'represented by {c["counsel"]}', f'ويمثلها {c["counsel_ar"]}')
    b.para([(x.L('Claimant: ', 'المدعية: '), {'bold': True}), (x.L(f'{CLAIMANT["en"]}, Luxembourg, owner of the registered trademark {c["mark"]}, {rep}.', f'{CLAIMANT["ar"]}، لوكسمبورغ، مالكة العلامة التجارية المسجلة {x.mark}، {rep}.'), {})])
    b.para([(x.L('Defendant: ', x.g('المدعى عليها: ', 'المدعى عليه: ')), {'bold': True}),
            (x.L(f'{c["inf"]}, {c["inf_type"].lower()} established in {c["inf_city"]}, {c["inf_cr_en"]}, represented by its manager {x.rep()}.',
                 f'{c["inf_ar"]}، {c["inf_type_ar"]} {x.g("مقرها", "مقره")} {c["inf_city_ar"]}، {c["inf_cr_ar"]}، {x.g("ويمثلها", "ويمثله")} {x.rep()}.'), {})])
    b.h1(x.L('Facts and procedure', 'الوقائع والإجراءات'))
    hearings = [h for h in c['hearing_dates'] if h <= x.date]
    sought_en = f'compensation of {x.M(c["claim"])}, an injunction' if c['claim'] else 'an injunction'
    sought_ar = f'تعويضاً قدره {x.M(c["claim"])} مع المنع' if c['claim'] else 'المنع'
    facts = [x.L(f'The Claimant filed this action on {den(c["soc_date"])} seeking {sought_en}, destruction of the infringing goods, publication of the judgment and costs, '
                 f'on the ground that the Defendant was {x.infringement()}.',
                 f'أقامت المدعية هذه الدعوى بتاريخ {dar(c["soc_date"])} طالبةً {sought_ar} والإتلاف ونشر الحكم والمصاريف، '
                 f'تأسيساً على قيام {x.g("المدعى عليها", "المدعى عليه")} بـ{x.infringement()}.'),
             x.test_purchase_sentence(),
             x.L(('The case was heard at one session' if len(hearings) == 1 else f'The case was heard at {len(hearings) or 2} sessions') + (f', the last on {den(hearings[-1])}' if len(hearings) > 1 else (f', on {den(hearings[0])}' if hearings else '')) + '. '
                 + (f'The Court appointed {c["expert_en"]}, whose report was filed on {den(c["expert_date"])}.' if c['ev'].get('Expert report filed') else 'The Court did not consider it necessary to appoint an expert.'),
                 {0: 'نُظرت الدعوى في جلستين', 1: 'نُظرت الدعوى في جلسة واحدة', 2: 'نُظرت الدعوى في جلستين'}.get(len(hearings), f'نُظرت الدعوى في {len(hearings)} جلسات')
                 + (f'، آخرها بتاريخ {dar(hearings[-1])}' if len(hearings) > 1 else (f' بتاريخ {dar(hearings[0])}' if hearings else '')) + '. '
                 + (f'وندبت المحكمة {c["expert_ar"]}، وأودع تقريره بتاريخ {dar(c["expert_date"])}.' if c['ev'].get('Expert report filed') else 'ولم ترَ المحكمة حاجة لندب خبير.'))]
    b.numbered(facts)
    b.h1(x.L('Defendant’s submissions', x.g('دفاع المدعى عليها', 'دفاع المدعى عليه')))
    b.para(x.R.choice([x.L('The Defendant argued that it bought the goods in good faith from a wholesaler, that it did not know they were counterfeit, and that the amount claimed was unsupported.',
                            'دفعت المدعى عليها بأنها اشترت البضاعة بحسن نية من تاجر جملة دون علمها بتقليدها، وبأن مبلغ التعويض المطالب به غير مؤيد بدليل.'),
                       x.L('The Defendant denied any use of the mark, contested the authenticity of the test purchase and asked the Court to dismiss the claim.',
                           'أنكرت المدعى عليها أي استعمال للعلامة، وطعنت في صحة الشراء الاختباري، وطلبت رفض الدعوى.'),
                       x.L('The Defendant submitted that its packaging is sufficiently different, that the colours used are common in the confectionery trade, and that no consumer had been misled.',
                           'دفعت المدعى عليها بأن عبواتها مختلفة بما يكفي، وبأن الألوان المستخدمة شائعة في تجارة الحلويات، وبأنه لم يثبت تضليل أي مستهلك.')]))
    b.h1(x.L('Reasoning', 'الأسباب'))
    if outcome in ('Won', 'Partially won'):
        b.para(x.L(f'Whereas the registration certificate establishes the Claimant’s exclusive right to the {c["mark"]} mark in the State, and the evidence shows use by the Defendant of an identical or confusingly similar sign on identical goods, '
                   f'the Court finds infringement within the meaning of {c["law_en"]}.',
                   f'وحيث إن شهادة التسجيل تثبت الحق الاستئثاري للمدعية في العلامة {x.mark} في الدولة، وقد ثبت من الأوراق استعمال {x.g("المدعى عليها", "المدعى عليه")} علامة مطابقة أو مشابهة إلى حد اللبس على سلع مطابقة، '
                   f'فإن المحكمة تنتهي إلى ثبوت التعدي وفقاً لأحكام {c["law_ar"]}.'))
        b.para(x.L('Whereas good faith does not excuse a trader from verifying the provenance of branded goods, and the Defendant produced no invoice identifying a lawful source, the defence is rejected.',
                   'وحيث إن حسن النية لا يعفي التاجر من التحقق من مصدر السلع التي تحمل علامات تجارية، ولم تُقدَّم أي فاتورة تثبت مصدراً مشروعاً، فإن هذا الدفع يكون في غير محله.'))
        if not c['awarded']:
            dmg = x.L('No compensation having been claimed at this stage, the Court confines itself to the injunctive relief requested.',
                      'وحيث إن المدعية لم تطالب بتعويض في هذه المرحلة، فإن المحكمة تقتصر على الحكم بطلبات المنع والإزالة.')
        elif outcome == 'Won' and abs(c['awarded'] - c['claim']) < 1:
            dmg = x.L(f'The Claimant’s quantification is supported by the evidence; the Court awards the full amount of {x.M(c["awarded"])}.', f'وحيث إن تقدير المدعية للتعويض تؤيده الأوراق، فإن المحكمة تقضي لها بكامل المبلغ وقدره {x.M(c["awarded"])}.')
        elif outcome == 'Won':
            dmg = x.L(f'Exercising its discretion, the Court assesses the material and moral damage at {x.M(c["awarded"])}.', f'وحيث إن المحكمة، بما لها من سلطة تقديرية، تقدر التعويض الجابر للضررين المادي والأدبي بمبلغ {x.M(c["awarded"])}.')
        else:
            dmg = x.L(f'However, the Claimant did not prove the volume of lost sales claimed. Taking into account the quantities seized and the enforcement costs actually incurred, the Court limits compensation to {x.M(c["awarded"])} '
                      f'out of the {x.M(c["claim"])} claimed, and rejects the request for publication.',
                      f'غير أن المدعية لم تُثبت حجم المبيعات الفائتة المطالب بها، ومراعاةً للكميات المضبوطة وتكاليف الإنفاذ الفعلية، تقصر المحكمة التعويض على مبلغ {x.M(c["awarded"])} '
                      f'من أصل {x.M(c["claim"])} المطالب به، وترفض طلب النشر.')
        b.para(dmg)
    else:
        key = 'online' if x.online() else ('unfair' if c['case_type'] in ('Unfair competition', 'Packaging imitation / passing off') else 'goods')
        b.para(x.L('Whereas the burden of proving infringement lies on the Claimant,', 'وحيث إن عبء إثبات التعدي يقع على عاتق المدعية،') + ' ' + x.L(*LOSS_REASON[key]))
        b.para(x.L('The Court therefore finds that infringement has not been established and the claim must be dismissed.', 'ومن ثم فإن التعدي يكون غير ثابت، وتغدو الدعوى قائمة على غير سند متعينة الرفض.'))
    b.h1(x.L('Operative part', 'منطوق الحكم'))
    b.para(x.L('For these reasons, the Court rules:', 'فلهذه الأسباب حكمت المحكمة:'), after=3)
    if outcome in ('Won', 'Partially won'):
        ops = [x.L(f'The Defendant shall pay the Claimant {x.M(c["awarded"])} as compensation, with legal interest at 5% from the date this judgment becomes final.',
                   f'إلزام {x.g("المدعى عليها", "المدعى عليه")} بأن {x.g("تؤدي", "يؤدي")} للمدعية مبلغ {x.M(c["awarded"])} تعويضاً، والفائدة القانونية بواقع 5% من تاريخ صيرورة الحكم نهائياً.')] if c['awarded'] else []
        ops += [x.L(f'The Defendant shall cease all use of the {c["mark"]} mark or any confusingly similar sign on goods, packaging, advertising or online listings.',
                    f'منع {x.g("المدعى عليها", "المدعى عليه")} من استعمال العلامة {x.mark} أو أي علامة مشابهة لها على السلع أو العبوات أو الإعلانات أو المنصات الإلكترونية.')]
        if c['case_type'].startswith('Domain'):
            ops.append(x.L(f'The domain name {x.domain()} shall be transferred to the Claimant.', f'نقل اسم النطاق {x.domain()} إلى المدعية.'))
        elif c['case_type'] == 'Mobile app infringement':
            ops.append(x.L(f'The Defendant shall withdraw the application “{x.app()["name"]}” from all app stores within fifteen days.', f'إلزام المدعى عليها بسحب التطبيق «{x.app()["name"]}» من جميع المتاجر خلال خمسة عشر يوماً.'))
        else:
            ops.append(x.L('The infringing goods, packaging and printing materials shall be confiscated and destroyed at the Defendant’s expense.', 'مصادرة البضائع والعبوات وأدوات الطباعة المخالفة وإتلافها على نفقة المدعى عليها.'))
        if outcome == 'Won':
            ops.append(x.L('A summary of this judgment shall be published in two daily newspapers, one in Arabic and one in English, at the Defendant’s expense.', 'نشر ملخص هذا الحكم في صحيفتين يوميتين إحداهما باللغة العربية والأخرى بالإنجليزية على نفقة المدعى عليها.'))
        adv = max(x.fee(2000), round(c['awarded'] * 0.002 / x.fee(1000)) * x.fee(1000))
        ops.append(x.L(f'The Defendant shall bear the court fees and expenses and {x.M(adv)} in advocate’s fees; all other requests are rejected.',
                       f'إلزام المدعى عليها بالرسوم والمصاريف ومبلغ {x.M(adv)} مقابل أتعاب المحاماة، ورفض ما عدا ذلك من طلبات.'))
    else:
        ops = [x.L('The claim is dismissed in its entirety.', 'رفض الدعوى برمتها.'),
               x.L(f'The Claimant shall bear the court fees and expenses and {x.M(x.fee(2000))} in advocate’s fees.', f'إلزام المدعية بالرسوم والمصاريف ومبلغ {x.M(x.fee(2000))} مقابل أتعاب المحاماة.')]
    b.numbered(ops)
    b.para(x.L('This judgment may be appealed within thirty (30) days of its notification.', 'ويجوز استئناف هذا الحكم خلال ثلاثين (30) يوماً من تاريخ إعلانه.'), italic=True, before=4)
    seal = x.seal('court', [x.L('COURT SEAL', 'ختم المحكمة'), x.L('COMMERCIAL', 'الدائرة التجارية')], ring=c['court'], color=x.R.choice(['blue', 'purple']))
    b.signatures([dict(label=x.L('Court Clerk', 'أمين السر'), name='', title=x.L('(signed)', '(توقيع)'), sig=x.sig('clerk' + c['case_id'], 'black')),
                  dict(label=x.L('Presiding Judge', 'رئيس الدائرة'), name='', title=x.L('(signed)', '(توقيع)'), sig=x.sig('judge' + c['case_id'], 'black'), seal=seal, seal_w=27)])


# =============================================================================== 7. takedown notice
def takedown_notice(b, x):
    c = x.c
    sender = ('Youssef Nasser', 'يوسف ناصر', 'Brand Protection Manager', 'مدير حماية العلامات التجارية') if x.R.random() < 0.6 else (c['counsel'], c['counsel_ar'], c['counsel_title'], c['counsel_title_ar'])
    b.para(x.L('DOLCE GROUP INTERNATIONAL S.A. – BRAND PROTECTION', 'شركة دولتشي جروب إنترناشيونال – حماية العلامات التجارية'), align='start', bold=True, size=13, color='5A2D0C', after=0)
    b.para(x.L(LEGAL_DEPT['en'], LEGAL_DEPT['ar']) + ' · brandprotection@dolcegroup.demo.local', align='start', size=8, color='555555', after=0)
    b.rule(color='5A2D0C', size=10)
    kind = 'app' if c['case_type'] == 'Mobile app infringement' else ('domain' if c['case_type'].startswith('Domain') else 'marketplace')
    if kind == 'app':
        a = x.app(); to = STORE_ADDR.get(a['store'], (a['store'], a['store']))
        subj = x.L(f'Trademark infringement notice – application “{a["name"]}”', f'إخطار تعدٍّ على علامة تجارية – التطبيق «{a["name"]}»')
    elif kind == 'domain':
        to = (f'Registrar of record and hosting provider of {x.domain()} (abuse desk)', f'مسجِّل النطاق ومزوّد الاستضافة للموقع {x.domain()} (قسم البلاغات)')
        subj = x.L(f'Notice of trademark infringement and abusive registration – {x.domain()}', f'إخطار تعدٍّ على علامة تجارية وتسجيل تعسفي – {x.domain()}')
    else:
        to = (f'{c["marketplace"]} – Brand protection / IP infringement team', f'منصة {c["marketplace"]} – فريق حماية العلامات والملكية الفكرية')
        subj = x.L(f'Notice of infringing listing No. {c["listing_id"]}', f'إخطار بإعلان مخالف رقم {c["listing_id"]}')
    b.para(x.L(f'Date: {den(x.date)} · Our reference: {c["case_id"]}', f'التاريخ: {dar(x.date)} · مرجعنا: {c["case_id"]}'), align='start', after=2)
    b.para(x.L(f'To: {to[0]}', f'إلى: {to[1]}'), align='start', bold=True, after=6)
    b.para(x.L('Re: ', 'الموضوع: ') + subj, align='start', bold=True, after=8)
    b.h1(x.L('Rights holder', 'صاحب الحق'))
    b.para(x.rights_sentence())
    b.h1(x.L('Infringing content', 'المحتوى المخالف'))
    if kind == 'app':
        a = x.app()
        rows = [[x.L('Store', 'المتجر'), a['store']], [x.L('Application', 'التطبيق'), a['name']], [x.L('Developer account', 'حساب المطوّر'), a['developer']],
                [x.L('Estimated installs', 'عدد التنزيلات التقديري'), f'{a["downloads"]:,}+'], [x.L('Countries', 'الدول'), x.L(c['country_en'], c['country_ar'])]]
    elif kind == 'domain':
        rows = [[x.L('Domain name', 'اسم النطاق'), x.domain()], [x.L('Registrant', 'المسجِّل'), x.L('withheld by privacy service', 'محجوب بخدمة خصوصية')],
                [x.L('Content', 'المحتوى'), x.L(f'online shop selling {c["product"].lower()} under the {c["mark"]} mark', f'متجر إلكتروني يبيع {c["product_ar"]} تحت العلامة {x.mark}')]]
    else:
        rows = [[x.L('Platform', 'المنصة'), c['marketplace']], [x.L('Listing ID', 'رقم الإعلان'), c['listing_id']], [x.L('Seller', 'البائع'), x.inf],
                [x.L('Price', 'السعر'), x.P(c['unit_price'])], [x.L('Genuine retail price', 'سعر التجزئة الأصلي'), x.P(c['genuine_price'])]]
    b.kv(rows)
    b.para(x.L(f'The content uses the {c["mark"]} name and logo without authorisation. ', f'يستخدم المحتوى اسم وشعار العلامة {x.mark} دون ترخيص. ') + x.test_purchase_sentence())
    a = x.app() if kind == 'app' else {}
    cap = A.listing_capture(x.path('capture.png'), x.id, kind, dict(mark=c['mark'], product=c['product'], title=a.get('name') or f'{c["mark"]} {c["product"]} {c["unit_en"]} – original imported – best price',
                            price=max(2, int(c['unit_price'])), old_price=int(c['genuine_price']), seller=c['inf'], store=(a.get('store', '') + ' – store listing') if a else c['marketplace'],
                            developer=a.get('developer', ''), downloads=f'{a.get("downloads", 10000) // 1000}K+', domain=x.domain(), when=x.date, currency=c['currency'],
                            listing_id=c['listing_id'], city=c['inf_city'], where=a.get('store') or (x.domain() if kind == 'domain' else c['marketplace'])))
    b.image(cap, 150, caption=x.L(f'Annex 1 – capture taken on {den(x.date)}.', f'الملحق 1 – صورة ملتقطة بتاريخ {dar(x.date)}.'))
    b.h1(x.L('Request', 'الطلب'))
    req = [x.L('Remove or disable access to the content identified above without delay.', 'إزالة المحتوى المحدد أعلاه أو تعطيل الوصول إليه دون تأخير.'),
           x.L('Disclose the registered contact details of the account holder for the purpose of enforcement.', 'الإفصاح عن بيانات الاتصال المسجلة لصاحب الحساب لأغراض الإنفاذ.'),
           x.L('Prevent the same account from re-listing products under the mark.', 'منع الحساب نفسه من إعادة عرض منتجات تحت العلامة.')]
    b.numbered(req)
    b.h1(x.L('Declarations', 'الإقرارات'))
    b.para(x.L('I have a good-faith belief that the use described above is not authorised by the trademark owner, its agent or the law. The information in this notice is accurate, and I am authorised to act on behalf of the owner.',
               'أقر بحسن نية بأن الاستعمال الموصوف أعلاه غير مرخص من مالك العلامة أو وكيله أو بموجب القانون، وأن المعلومات الواردة في هذا الإخطار صحيحة، وأنني مخوّل بالتصرف نيابةً عن المالك.'))
    blk = dict(name=x.L(sender[0], sender[1]), title=x.L(sender[2], sender[3]), org=x.claimant, sig=x.sig(sender[0]))
    if c['takedown_confirmed'] and c['takedown_confirmed'] >= x.date:
        b.signatures([blk, dict(label=x.L('Platform action', 'إجراء المنصة'), name='', title=x.L(f'Content removed on {den(c["takedown_confirmed"])}', f'أُزيل المحتوى بتاريخ {dar(c["takedown_confirmed"])}'),
                                seal=x.stamp('removed', [x.L('ACTIONED', 'تم التنفيذ'), x.L('Content removed', 'تمت إزالة المحتوى'), dnum(c['takedown_confirmed'])], color='green'), seal_w=44)])
    else:
        b.signatures([blk], widths_mm=[95])


# =============================================================================== 8. expert report
def expert_report(b, x):
    c = x.c
    won = c['outcome'] in ('Won', 'Partially won', 'Settled', 'Pending')
    b.center(x.L(f'{c["court"]} – Commercial Case No. {c["court_ref"]}', f'{c["court_ar"]} – الدعوى التجارية رقم {c["court_ref"]}'), bold=True)
    b.title(x.L('EXPERT REPORT', 'تقرير الخبير'), size=15, before=4)
    b.center(x.L(f'{CLAIMANT["en"]} v. {c["inf"]}', f'{CLAIMANT["ar"]} ضد {c["inf_ar"]}'), size=10)
    b.center(x.L(f'Filed on {den(x.date)}', f'أودع بتاريخ {dar(x.date)}'), size=10, after=4)
    b.rule()
    x.translation_note(b)
    b.h1(x.L('1. Appointment and mission', '1. الندب والمأمورية'))
    quantum = bool(c['claim'])
    b.para(x.L(f'By order dated {den(c["expert_appointed"])}, the Court appointed {c["expert_en"]}, with the following mission: (a) to compare the Claimant’s registered mark and trade dress with the signs used by the Defendant; '
               + ('(b) state whether the Defendant’s products are likely to cause confusion among average consumers; and (c) assess the quantities sold and the resulting loss.' if quantum else
                  'and (b) state whether the Defendant’s products are likely to cause confusion among average consumers.'),
               f'بموجب قرار المحكمة المؤرخ {dar(c["expert_appointed"])} نُدب {c["expert_ar"]} لأداء المأمورية الآتية: (أ) مقارنة العلامة المسجلة للمدعية ومظهر منتجاتها بالعلامات المستخدمة من المدعى عليها؛ '
               + ('(ب) بيان ما إذا كان من شأن منتجات المدعى عليها إحداث اللبس لدى المستهلك العادي؛ (ج) تقدير الكميات المباعة والضرر المترتب.' if quantum else
                  '(ب) بيان ما إذا كان من شأن منتجات المدعى عليها إحداث اللبس لدى المستهلك العادي.')))
    b.h1(x.L('2. Documents and inspections', '2. المستندات والمعاينات'))
    b.bullets([x.L('Registration certificate and genuine reference samples supplied by the Claimant.', 'شهادة التسجيل والعينات المرجعية الأصلية المقدمة من المدعية.'),
               x.L(f'Sealed samples {c["seal_no"]} from the test purchase of {den(c["tp_date"])} and laboratory certificate {c["lab_ref"]}.', f'العينات المختومة {c["seal_no"]} من الشراء الاختباري المؤرخ {dar(c["tp_date"])} وشهادة المختبر رقم {c["lab_ref"]}.'),
               x.L(f'Inspection of the Defendant’s premises at {c["inf_addr_en"]} in the presence of both parties.', f'معاينة مقر المدعى عليها في {c["inf_addr_ar"]} بحضور الطرفين.'),
               x.L('The Defendant’s purchase invoices and stock records for the last twelve months.', 'فواتير الشراء وسجلات المخزون لدى المدعى عليها عن الاثني عشر شهراً الأخيرة.')])
    b.h1(x.L('3. Comparison', '3. المقارنة'))
    g1 = A.product_photo(x.path('genuine.jpg'), x.id + 'g', c['mark'], c['product'], ['REFERENCE', 'genuine product'])
    g2 = A.product_photo(x.path('sample.jpg'), x.id + 's', c['mark'], c['product'], [f'SAMPLE {c["seal_no"]}', c['case_id']])
    b.images_row([(g1, 76, x.L('Figure 1 – genuine reference product', 'الشكل 1 – المنتج الأصلي المرجعي')),
                  (g2, 76, x.L('Figure 2 – Defendant’s product (sealed sample)', 'الشكل 2 – منتج المدعى عليها (عينة مختومة)'))])
    lvl = (lambda hi, lo: hi if won else lo)
    b.table([x.L('Criterion', 'المعيار'), x.L('Assessment', 'التقييم'), x.L('Degree', 'الدرجة')],
            [[x.L('Visual similarity', 'التشابه البصري'), x.L('Same dominant word element, same colour scheme and layout' if won else 'Different word element; colours partly shared', 'نفس العنصر اللفظي المهيمن ونفس الألوان والتصميم' if won else 'عنصر لفظي مختلف وألوان مشتركة جزئياً'), x.L(lvl('High', 'Low'), lvl('عالية', 'منخفضة'))],
             [x.L('Phonetic similarity', 'التشابه الصوتي'), x.L('Identical pronunciation' if won else 'Distinct pronunciation', 'نطق مطابق' if won else 'نطق مختلف'), x.L(lvl('High', 'Low'), lvl('عالية', 'منخفضة'))],
             [x.L('Conceptual similarity', 'التشابه المعنوي'), x.L('Same invented word' if won else 'No shared concept', 'الكلمة المبتكرة ذاتها' if won else 'لا يوجد مفهوم مشترك'), x.L(lvl('High', 'Low'), lvl('عالية', 'منخفضة'))],
             [x.L('Goods', 'السلع'), x.L(f'Identical – {c["product"].lower()}', f'مطابقة – {c["product_ar"]}'), x.L('Identical', 'مطابقة')],
             [x.L('Channels of trade', 'قنوات التوزيع'), x.L('Same retail and online channels', 'نفس منافذ البيع بالتجزئة والقنوات الإلكترونية'), x.L(lvl('High', 'Medium'), lvl('عالية', 'متوسطة'))]],
            [40, 92, 30], size=8.5)
    b.h1(x.L('4. Quantities and loss', '4. الكميات والضرر'))
    if quantum:
        units = int(c['claim'] / max(c['genuine_price'], 1) * x.R.uniform(0.12, 0.3))
        loss = c['awarded'] if c['awarded'] else c['claim'] * x.R.uniform(0.25, 0.45)
        b.para(x.L(f'The Defendant’s records show purchases of approximately {units:,} units over the period examined. Applying the Claimant’s average unit margin and adding documented enforcement costs, '
                   f'the expert estimates the loss at {x.M(loss)}' + (', against the ' + x.M(c['claim']) + ' claimed.' if abs(loss - c['claim']) > 1 else '.'),
                   f'تُظهر سجلات المدعى عليها شراء نحو {units:,} وحدة خلال الفترة محل الفحص. وبتطبيق متوسط هامش الربح للوحدة لدى المدعية وإضافة تكاليف الإنفاذ الموثقة، '
                   f'يقدّر الخبير الضرر بمبلغ {x.M(loss)}' + (f' مقابل {x.M(c["claim"])} المطالب به.' if abs(loss - c['claim']) > 1 else '.')))
    else:
        b.para(x.L('The Claimant seeks injunctive relief only, so the assessment of loss was not part of the mission. The expert notes that the infringing content remained available for at least '
                   f'{x.R.randint(3, 9)} weeks before it was reported.',
                   'تقتصر طلبات المدعية على المنع والإزالة، ومن ثم لم يكن تقدير الضرر من ضمن المأمورية. ويلاحظ الخبير أن المحتوى المخالف ظل متاحاً لمدة لا تقل عن '
                   f'{x.R.randint(3, 9)} أسابيع قبل الإبلاغ عنه.'))
    b.h1(x.L('5. Conclusion', '5. النتيجة'))
    if won:
        b.para(x.L(f'The signs used by the Defendant are identical or highly similar to the {c["mark"]} mark and are used on identical goods; an average consumer exercising ordinary attention is likely to be confused as to origin.',
                   f'العلامات المستخدمة من المدعى عليها مطابقة أو شديدة التشابه مع العلامة {x.mark} وتُستخدم على سلع مطابقة، ومن شأنها إحداث اللبس لدى المستهلك العادي متوسط الانتباه بشأن مصدر المنتجات.'))
    else:
        b.para(x.L('Taking the products as a whole, the differences in name and presentation are sufficient for an average consumer to distinguish them; the expert does not find a likelihood of confusion.',
                   'بالنظر إلى المنتجات في مجملها، فإن الفروق في الاسم وطريقة العرض كافية لتمكين المستهلك العادي من التمييز بينها، ولا يرى الخبير احتمالاً للبس.'))
    b.signatures([dict(label=x.L('Court-appointed expert', 'الخبير المنتدب'), name=x.L(c['expert_en'].split(',')[0], c['expert_ar'].split('،')[0]), title=x.L('Expert', 'خبير'), sig=x.sig(c['expert_en']),
                       seal=x.seal('expert', [x.L('REGISTERED', 'خبير'), x.L('EXPERT', 'مقيد')], ring='COURT EXPERTS ROLL', color='green'), seal_w=24)], widths_mm=[110])


# =============================================================================== 9. settlement agreement
def settlement_agreement(b, x):
    c = x.c
    b.title(x.L('SETTLEMENT AGREEMENT', 'اتفاقية تسوية'), size=15)
    b.center(x.L(f'Dated {den(x.date)} · Matter {c["case_id"]}', f'بتاريخ {dar(x.date)} · الملف {c["case_id"]}'), size=10, after=4)
    b.rule()
    b.para(x.L('BETWEEN', 'بين كل من'), bold=True, align='start', after=2)
    b.numbered([x.L(f'{CLAIMANT["en"]}, {CLAIMANT_ADDR["en"]} (the “Rights Holder”); and', f'{CLAIMANT["ar"]}، {CLAIMANT_ADDR["ar"]} («صاحبة الحق»)؛'),
                x.L(f'{c["inf"]}, {c["inf_cr_en"]}, {c["inf_addr_en"]}, {c["country_en"]}, represented by {x.rep()} (the “Counterparty”).',
                    f'{c["inf_ar"]}، {c["inf_cr_ar"]}، {c["inf_addr_ar"]}، {c["country_ar"]}، ويمثلها {x.rep()} («الطرف الثاني»).')])
    b.h1(x.L('Recitals', 'تمهيد'))
    b.para(x.L(f'The Rights Holder owns the {c["mark"]} mark (registration No. {c["mark_reg"]}). It alleges that the Counterparty was {x.infringement()}. '
               + (f'Proceedings are pending before {c["court"]} under No. {c["court_ref"]}. ' if c['court_like'] else f'The matter was referred to {c["court"]}. ')
               + 'The parties wish to settle the dispute without admission of liability on the following terms.',
               f'تملك صاحبة الحق العلامة {x.mark} (تسجيل رقم {c["mark_reg"]})، وتنسب إلى الطرف الثاني {x.infringement()}. '
               + (f'والنزاع منظور أمام {c["court_ar"]} برقم {c["court_ref"]}. ' if c['court_like'] else f'وقد أُحيل الأمر إلى {c["court_ar"]}. ')
               + 'ويرغب الطرفان في تسوية النزاع ودياً دون إقرار بالمسؤولية وفقاً للشروط الآتية:'))
    n = c['instalments']
    total = c['settlement']
    parts = [round(total / n, -2) for _ in range(n - 1)]
    parts.append(total - sum(parts))
    dates = [x.date.fromordinal(x.date.toordinal() + 14 + 30 * k) for k in range(n)]
    b.h1(x.L('1. Payment', '1. المبلغ'))
    if total:
        on_ar = 'على قسطين' if n == 2 else f'على {n} أقساط'
        b.para(x.L(f'The Counterparty shall pay the Rights Holder {x.M(total)} in {n} instalments, by bank transfer to the account notified in writing:',
                   f'يدفع الطرف الثاني لصاحبة الحق مبلغاً إجمالياً قدره {x.M(total)} {on_ar} بالتحويل المصرفي إلى الحساب المُخطَر به كتابةً، وذلك على النحو الآتي:'), after=3)
        b.table([x.L('Instalment', 'القسط'), x.L('Amount', 'المبلغ'), x.L('Due date', 'تاريخ الاستحقاق')], [[str(k + 1), x.M(p), x.D(dd)] for k, (p, dd) in enumerate(zip(parts, dates))], [40, 60, 60])
    else:
        b.para(x.L('No monetary compensation is payable. In consideration of the undertakings below, each party bears its own costs.',
                   'لا يستحق أي تعويض مالي، ويتحمل كل طرف مصاريفه مقابل التعهدات الواردة أدناه.'))
    b.h1(x.L('2. Stock and materials', '2. المخزون والمواد'))
    destroy = c['seized_units'] if c['case_type'] == 'Customs seizure' else int(str(c['stock_seen']).split('–')[0].replace('about ', '').replace(',', '') or 200)
    b.para(x.L(f'Within fourteen (14) days the Counterparty shall deliver up all remaining infringing stock (declared at {destroy:,} units), packaging and promotional materials, which shall be destroyed under the Rights Holder’s supervision at the Counterparty’s cost.',
               f'يسلّم الطرف الثاني خلال أربعة عشر (14) يوماً جميع المخزون المخالف المتبقي (المُعلن بعدد {destroy:,} وحدة) والعبوات والمواد الدعائية، لتُتلف تحت إشراف صاحبة الحق وعلى نفقة الطرف الثاني.'))
    b.h1(x.L('3. Undertakings', '3. التعهدات'))
    b.para(x.L(f'The Counterparty undertakes not to use the {c["mark"]} mark or any confusingly similar sign, packaging or domain name, and to disclose in writing the identity of its suppliers within seven (7) days.',
               f'يتعهد الطرف الثاني بعدم استعمال العلامة {x.mark} أو أي علامة أو عبوة أو اسم نطاق مشابه لها، وبالإفصاح كتابةً عن هوية موردّيه خلال سبعة (7) أيام.'))
    b.h1(x.L('4. Withdrawal of proceedings', '4. ترك الخصومة'))
    b.para(x.L('On receipt of the final instalment the Rights Holder shall withdraw the pending proceedings and complaints; each party bears its own costs.', 'تلتزم صاحبة الحق، فور استلام القسط الأخير، بترك الخصومة في الدعوى والشكاوى المنظورة، ويتحمل كل طرف مصاريفه.'))
    b.h1(x.L('5. Breach', '5. الإخلال'))
    liq = total * 2 if total else x.fee(50000)
    b.para(x.L(f'Any breach of clauses 1 to 3 entitles the Rights Holder to liquidated damages of {x.M(liq)}, without prejudice to its other remedies, and revives all claims.',
               f'يترتب على أي إخلال بالبنود من 1 إلى 3 استحقاق صاحبة الحق تعويضاً اتفاقياً قدره {x.M(liq)} دون الإخلال بحقوقها الأخرى، مع عودة جميع المطالبات.'))
    b.h1(x.L('6. Confidentiality and governing law', '6. السرية والقانون الواجب التطبيق'))
    b.para(x.L(f'The terms of this Agreement are confidential. It is governed by the laws of {c["country_en"]}; the courts of {c["court_city"]} have exclusive jurisdiction.',
               f'تُعد شروط هذه الاتفاقية سرية، وتخضع لقوانين {c["country_ar"]}، وتختص محاكم {c["court_city_ar"]} حصرياً بأي نزاع ينشأ عنها.'))
    signer = x.counsel_block(x.L('For the Rights Holder', 'عن صاحبة الحق'))
    b.signatures([signer, dict(label=x.L('For the Counterparty', 'عن الطرف الثاني'), name=x.rep(), title=x.L('Manager', 'المدير'), org=x.inf, sig=x.sig(x.rep() + c['case_id'], 'black'),
                               seal=x.seal('company', wrap(x.inf, 16)[:3], ring=c['inf'], color='blue'), seal_w=22)])


# =============================================================================== 10. customs seizure notice
def customs_seizure_notice(b, x):
    c = x.c
    b.center(x.L('GOVERNMENT OF DUBAI', 'حكومة دبي'), bold=True, size=11)
    b.center(x.L(c['court'].upper(), c['court_ar']), bold=True, size=13)
    b.center(x.L('Notice of suspension of release – intellectual property rights', 'إخطار بوقف الإفراج – حقوق الملكية الفكرية'), bold=True, size=11, before=2)
    b.rule()
    nno = f'IPR/{x.date.year}/{x.R.randint(1000, 9999)}'
    b.para(x.L(f'Notice No. {nno} · Date: {den(x.date)}', f'رقم الإخطار {nno} · التاريخ: {dar(x.date)}'), align='start', after=2)
    b.para(x.L(f'To: {CLAIMANT["en"]} – registered right holder, through its agent {c["firm"] or "the Legal Department"}', f'إلى: {CLAIMANT["ar"]} – صاحبة الحق المسجلة، عن طريق وكيلها {c["firm_ar"] or "الإدارة القانونية"}'),
           align='start', bold=True, after=8)
    b.para(x.L(f'Further to the recordation of the {c["mark"]} mark with this Department, we inform you that the consignment described below has been suspended from release on suspicion of infringing your registered rights:',
               f'بالإشارة إلى قيد العلامة {x.mark} لدى الإدارة، نحيطكم علماً بأنه تم وقف الإفراج عن الشحنة المبينة أدناه للاشتباه في تعديها على حقوقكم المسجلة:'))
    b.kv([[x.L('Customs declaration', 'البيان الجمركي'), c['decl_no']], [x.L('Container / bill of lading', 'الحاوية / بوليصة الشحن'), f'{c["container"]} / {c["bl_no"]}'],
          [x.L('Port of entry', 'منفذ الدخول'), x.L('Jebel Ali Port', 'ميناء جبل علي')], [x.L('Port of loading', 'ميناء الشحن'), x.L(c['origin'][0], c['origin'][1])],
          [x.L('Importer', 'المستورد'), f'{x.inf} ({x.L(c["inf_cr_en"], c["inf_cr_ar"])})'], [x.L('Goods', 'البضائع'), f'{x.product} – {x.L(c["unit_en"], c["unit_ar"])}'],
          [x.L('Quantity suspended', 'الكمية الموقوفة'), x.L(f'{c["seized_units"]:,} units bearing the {c["mark"]} mark', f'{c["seized_units"]:,} وحدة تحمل العلامة {x.mark}')],
          [x.L('Declared / estimated value', 'القيمة المصرح بها / التقديرية'), f'{x.M(c["claim"] * 0.18)} / {x.M(c["claim"])}']])
    b.h1(x.L('Required action', 'الإجراء المطلوب'))
    b.numbered([x.L('Inspect the samples drawn and confirm in writing whether the goods are counterfeit, within ten (10) working days of this notice.', 'معاينة العينات المسحوبة وتأكيد ما إذا كانت البضائع مقلدة كتابياً خلال عشرة (10) أيام عمل من تاريخ هذا الإخطار.'),
                x.L('Where infringement is confirmed, lodge a guarantee and file a complaint or action before the competent authority within twenty (20) working days.', 'في حال تأكيد التعدي، تقديم الضمان اللازم ورفع شكوى أو دعوى أمام الجهة المختصة خلال عشرين (20) يوم عمل.'),
                x.L('Failing either step, the consignment will be released to the importer in accordance with the applicable customs legislation.', 'وفي حال عدم اتخاذ أي من الإجراءين، يُفرج عن الشحنة للمستورد وفقاً للتشريعات الجمركية المعمول بها.')])
    if x.R.random() < 0.7:
        photo = A.product_photo(x.path('photo.jpg'), x.id, c['mark'], c['product'], [f'IPR {nno}', c['container'], dnum(x.date)])
        b.image(photo, 100, caption=x.L('Sample drawn from the consignment.', 'عينة مسحوبة من الشحنة.'))
    b.signatures([dict(label=x.L('IPR Department', 'إدارة حقوق الملكية الفكرية'), name='', title=x.L('Inspector – IPR Section', 'مفتش – قسم الملكية الفكرية'), sig=x.sig('customs' + c['case_id'], 'black'),
                       seal=x.seal('customs', [x.L('IPR', 'الملكية'), x.L('DEPARTMENT', 'الفكرية')], ring='DUBAI CUSTOMS', color='green'), seal_w=26)], widths_mm=[110])


# =============================================================================== 11. trademark office decision
def trademark_office_decision(b, x):
    c = x.c
    appl = f'{x.R.randint(300000, 599999)}'
    india = c['country'] == 'India'
    office_en = 'Trade Marks Registry – Office of the Controller General of Patents, Designs and Trade Marks' if india else c['court']
    office_ar = 'سجل العلامات التجارية – مكتب المراقب العام لبراءات الاختراع والتصاميم والعلامات التجارية' if india else c['court_ar']
    b.center(x.L(c['country_en'].upper(), c['country_ar']), bold=True)
    b.center(x.L(office_en, office_ar), bold=True, size=12)
    b.center(x.L(f'Decision in opposition No. OPP-{appl[:4]}-{x.date.year} · {den(x.date)}', f'قرار في الاعتراض رقم OPP-{appl[:4]}-{x.date.year} · {dar(x.date)}'), size=10)
    b.rule()
    b.kv([[x.L('Opponent', 'المعترضة'), f'{x.claimant} · {x.L("owner of", "مالكة العلامة")} {x.mark} ({c["mark_reg"]})'],
          [x.L('Applicant', 'طالب التسجيل'), x.inf], [x.L('Application', 'الطلب'), x.L(f'No. {appl}, class {c["nice"]}, filed {den(c["opened"])}', f'رقم {appl}، الفئة {c["nice"]}، مقدم بتاريخ {dar(c["opened"])}')]])
    b.h1(x.L('Background', 'الوقائع'))
    b.para(x.L(f'The opponent filed an opposition against the application on the ground that the applied-for sign is confusingly similar to its earlier registered mark {c["mark"]} for identical goods in class {c["nice"]}. '
               + (f'Parallel rectification proceedings were brought before {c["court"]}.' if india else ''),
               f'تقدمت المعترضة باعتراض على الطلب تأسيساً على أن العلامة المطلوب تسجيلها مشابهة إلى حد اللبس لعلامتها المسجلة سابقاً {x.mark} عن سلع مطابقة في الفئة {c["nice"]}. '
               + (f'كما أُقيمت دعوى شطب موازية أمام {c["court_ar"]}.' if india else '')))
    if c['outcome'] == 'Withdrawn':
        b.h1(x.L('Decision', 'القرار'))
        b.para(x.L(f'On {den(x.date)} the applicant filed a request to withdraw application No. {appl}. The application is therefore treated as abandoned and the opposition proceedings are closed as having become infructuous. No order as to costs.',
                   f'بتاريخ {dar(x.date)} تقدم طالب التسجيل بطلب سحب الطلب رقم {appl}، وعليه يُعتبر الطلب متنازلاً عنه وتُغلق إجراءات الاعتراض لانتفاء موضوعها، دون إلزام بالمصاريف.'))
    else:
        b.h1(x.L('Decision', 'القرار'))
        b.para(x.L(f'The opposition is upheld. The application is refused for similarity with the earlier mark {c["mark"]}.', f'قبول الاعتراض ورفض تسجيل العلامة المتعارضة لتشابهها مع العلامة السابقة {x.mark}.'))
    b.signatures([dict(label=x.L('For the Registrar', 'عن المسجِّل'), name='', title=x.L('Examiner of Trade Marks', 'فاحص العلامات التجارية'), sig=x.sig('registrar' + c['case_id'], 'black'),
                       seal=x.seal('office', [x.L('TRADE MARKS', 'العلامات'), x.L('REGISTRY', 'التجارية')], ring='TRADE MARKS REGISTRY', color='blue'), seal_w=26)], widths_mm=[110])


# =============================================================================== 12. licence agreement
def licence_agreement(b, x):
    c = x.c
    b.title(x.L('TRADEMARK LICENCE AND DISTRIBUTION AGREEMENT', 'اتفاقية ترخيص علامة تجارية وتوزيع'), size=14)
    b.center(x.L(f'Dated {den(x.date)}', f'بتاريخ {dar(x.date)}'), size=10, after=4)
    b.rule()
    b.para([(x.L('Licensor: ', 'المرخِّص: '), {'bold': True}), (x.L(f'{CLAIMANT["en"]}, {CLAIMANT_ADDR["en"]}.', f'{CLAIMANT["ar"]}، {CLAIMANT_ADDR["ar"]}.'), {})])
    b.para([(x.L('Licensee: ', 'المرخَّص له: '), {'bold': True}), (x.L(f'{c["inf"]}, {c["inf_cr_en"]}, {c["inf_addr_en"]}, {c["country_en"]}.', f'{c["inf_ar"]}، {c["inf_cr_ar"]}، {c["inf_addr_ar"]}، {c["country_ar"]}.'), {})])
    clauses = [
        (x.L('1. Grant', '1. الترخيص'), x.L(f'The Licensor grants the Licensee a non-exclusive, non-transferable licence to use the trademark {c["mark"]} (registration No. {c["mark_reg"]}, class {c["nice"]}) solely for the import, distribution and sale of genuine {c["mark"]} products supplied by the Licensor or its designated affiliates.',
                                            f'يمنح المرخِّص المرخَّص له ترخيصاً غير حصري وغير قابل للتنازل باستعمال العلامة التجارية {x.mark} (تسجيل رقم {c["mark_reg"]}، الفئة {c["nice"]}) حصراً لاستيراد وتوزيع وبيع منتجات {x.mark} الأصلية المورّدة من المرخِّص أو الشركات التابعة المعيّنة.')),
        (x.L('2. Term', '2. المدة'), x.L('Three (3) years from the date of this Agreement, renewable by written agreement; either party may terminate on ninety (90) days’ notice.', 'ثلاث (3) سنوات من تاريخ هذه الاتفاقية، قابلة للتجديد باتفاق كتابي، ويجوز لأي طرف إنهاؤها بإخطار مدته تسعون (90) يوماً.')),
        (x.L('3. Territory', '3. الإقليم'), x.L(f'The licence is limited to the {c["country_en"]} (the “Territory”). The Licensee shall not import products other than those supplied by the Licensor, and shall not sell or supply products outside the Territory; any breach of this clause is a material breach.',
                                                f'يقتصر الترخيص على {c["country_ar"]} («الإقليم»). ولا يجوز للمرخَّص له استيراد منتجات غير تلك المورّدة من المرخِّص، أو بيع المنتجات أو توريدها خارج الإقليم، ويُعد أي إخلال بهذا البند إخلالاً جوهرياً.')),
        (x.L('4. Quality control', '4. مراقبة الجودة'), x.L('The Licensee shall store and handle the products in accordance with the Licensor’s written guidelines, permit inspection on reasonable notice, and withdraw any product the Licensor identifies as non-conforming.',
                                                         'يلتزم المرخَّص له بتخزين المنتجات ومناولتها وفق تعليمات المرخِّص المكتوبة، والسماح بالتفتيش بإخطار معقول، وسحب أي منتج يحدده المرخِّص بوصفه غير مطابق.')),
        (x.L('5. Royalty', '5. الإتاوة'), x.L(f'The Licensee shall pay a royalty of {x.R.choice(["four per cent (4%)", "five per cent (5%)", "three and a half per cent (3.5%)"])} of net sales, payable quarterly within thirty (30) days of the end of each quarter, with a sales statement by product and customer.',
                                              f'يدفع المرخَّص له إتاوة بنسبة {x.R.choice(["أربعة بالمائة (4%)", "خمسة بالمائة (5%)", "ثلاثة ونصف بالمائة (3.5%)"])} من صافي المبيعات، تُسدد ربع سنوياً خلال ثلاثين (30) يوماً من نهاية كل ربع، مع كشف بالمبيعات حسب المنتج والعميل.')),
        (x.L('6. Records and audit', '6. السجلات والتدقيق'), x.L('The Licensee shall keep complete purchase, sales and stock records for five (5) years and allow the Licensor’s auditors to inspect them on ten (10) days’ notice.',
                                                                 'يحتفظ المرخَّص له بسجلات كاملة للمشتريات والمبيعات والمخزون لمدة خمس (5) سنوات، ويسمح لمدققي المرخِّص بفحصها بإخطار مدته عشرة (10) أيام.')),
        (x.L('7. Termination', '7. الإنهاء'), x.L('On termination the Licensee shall cease all use of the mark, return promotional material and sell remaining genuine stock within sixty (60) days.', 'عند الإنهاء يتوقف المرخَّص له عن أي استعمال للعلامة، ويعيد المواد الدعائية، ويبيع المخزون الأصلي المتبقي خلال ستين (60) يوماً.')),
        (x.L('8. Governing law', '8. القانون الواجب التطبيق'), x.L(f'This Agreement is governed by the laws of the {c["country_en"]}; the courts of {c["court_city"]} have exclusive jurisdiction.', f'تخضع هذه الاتفاقية لقوانين {c["country_ar"]}، وتختص محاكم {c["court_city_ar"]} حصرياً بنظر أي نزاع ينشأ عنها.'))]
    for h, t in clauses:
        b.h1(h); b.para(t)
    b.signatures([dict(label=x.L('For the Licensor', 'عن المرخِّص'), name=x.L('Daniel Weber', 'دانيال فيبر'), title=x.L('Regional General Counsel', 'المستشار العام الإقليمي'), org=x.claimant, sig=x.sig('Daniel Weber')),
                  dict(label=x.L('For the Licensee', 'عن المرخَّص له'), name=x.rep(), title=x.L('Managing Director', 'المدير العام'), org=x.inf, sig=x.sig(x.rep() + 'lic', 'black'))])


TEMPLATES = {'Cease-and-desist letter': cease_and_desist, 'Evidence – test purchase': evidence_test_purchase, 'Statement of claim': statement_of_claim,
             'Power of attorney': power_of_attorney, 'Investigation report': investigation_report, 'Judgment': judgment, 'Takedown notice': takedown_notice,
             'Expert report': expert_report, 'Settlement agreement': settlement_agreement, 'Customs seizure notice': customs_seizure_notice,
             'Trademark office decision': trademark_office_decision, 'Licence agreement': licence_agreement}

def author_for(t, c):
    return {'Judgment': c['court'], 'Customs seizure notice': c['court'], 'Trademark office decision': c['court'], 'Expert report': c['expert_en'].split(',')[0],
            'Evidence – test purchase': INVESTIGATOR['en'], 'Investigation report': INVESTIGATOR['en']}.get(t, c['firm'] or CLAIMANT['en'])
