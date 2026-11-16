// Builds the 12 sample case documents (EN/AR) from out/docs_spec.json using docx-js.
const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType, BorderStyle,
        Footer, PageNumber, LevelFormat, ShadingType } = require('docx');
const spec = JSON.parse(fs.readFileSync('out/docs_spec.json', 'utf8'));
const CL = spec.claimant;
fs.mkdirSync('out/documents', { recursive: true });

// ---------- helpers ----------
const P = (text, o = {}) => new Paragraph({
  alignment: o.align || AlignmentType.JUSTIFIED, spacing: { after: o.after ?? 120, before: o.before ?? 0 },
  numbering: o.num ? { reference: o.num === 'bul' ? 'bul' : o.num + (listIdx % 10), level: 0 } : undefined, keepNext: o.keepNext,
  children: (Array.isArray(text) ? text : [[text, {}]]).map(([t, r]) => new TextRun({ text: t, bold: r.bold || o.bold, italics: r.italics, size: o.size || 22, font: 'Arial' })),
});
const H = (text, lvl = 1) => (listIdx++, new Paragraph({ heading: lvl === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2, children: [new TextRun({ text, font: 'Arial' })] }));
const T = (text) => new Paragraph({ heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER, children: [new TextRun({ text, font: 'Arial' })] });
const C = (text, o = {}) => P(text, { align: AlignmentType.CENTER, ...o });
const AP = (text, o = {}) => new Paragraph({  // Arabic paragraph, right-to-left
  alignment: o.align || AlignmentType.RIGHT, bidirectional: true, spacing: { after: o.after ?? 120, before: o.before ?? 0 },
  numbering: o.num ? { reference: o.num + (listIdx % 10), level: 0 } : undefined,
  children: (Array.isArray(text) ? text : [[text, {}]]).map(([t, r]) => new TextRun({ text: t, rightToLeft: true, bold: r.bold || o.bold, size: o.size || 24, font: 'Arial' })),
});
const AH = (text) => (listIdx++, new Paragraph({ heading: HeadingLevel.HEADING_1, bidirectional: true, alignment: AlignmentType.RIGHT, children: [new TextRun({ text, rightToLeft: true, font: 'Arial' })] }));
const AT = (text) => new Paragraph({ heading: HeadingLevel.TITLE, bidirectional: true, alignment: AlignmentType.CENTER, children: [new TextRun({ text, rightToLeft: true, font: 'Arial' })] });
const AC = (text, o = {}) => AP(text, { align: AlignmentType.CENTER, ...o });
const rule = () => new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '999999' } }, spacing: { after: 160 }, children: [] });
function table(rows, widths, rtl = false, header = true) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths, visuallyRightToLeft: rtl,
    rows: rows.map((r, ri) => new TableRow({ children: r.map((cell, ci) => new TableCell({
      width: { size: widths[ci], type: WidthType.DXA },
      shading: header && ri === 0 ? { type: ShadingType.CLEAR, fill: 'E7E6E6', color: 'auto' } : undefined,
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      children: [new Paragraph({ bidirectional: rtl, alignment: rtl ? AlignmentType.RIGHT : AlignmentType.LEFT,
        children: [new TextRun({ text: String(cell), bold: header && ri === 0, rightToLeft: rtl, size: 20, font: 'Arial' })] })],
    })) })),
  });
}
const styles = {
  default: { document: { run: { font: 'Arial', size: 22 } } },
  paragraphStyles: [
    { id: 'Title', name: 'Title', basedOn: 'Normal', run: { font: 'Arial', size: 30, bold: true }, paragraph: { spacing: { before: 0, after: 200 }, alignment: AlignmentType.CENTER } },
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Arial', size: 24, bold: true }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 0 } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Arial', size: 22, bold: true }, paragraph: { spacing: { before: 180, after: 80 }, keepNext: true, outlineLevel: 1 } },
  ],
};
const numbering = { config: [] };
for (let k = 0; k < 10; k++) {
  numbering.config.push({ reference: 'num' + k, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] });
  numbering.config.push({ reference: 'anum' + k, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.RIGHT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] });
}
numbering.config.push({ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] });
// every H()/AH() heading starts a new list instance
let listIdx = 0;
function build(d, children, rtl = false) {
  listIdx = 0;
  const footerText = `${d.doc_type} · ${d.case_id} · ${d.sensitivity} · Demo document – all parties and facts are fictional`;
  const doc = new Document({ styles, numbering, creator: 'Intertec demo', title: `${d.case_id} ${d.doc_type}`,
    sections: [{ properties: { page: { margin: { top: 1300, bottom: 1200, left: 1300, right: 1300 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
        new TextRun({ text: footerText + '   Page ', size: 16, font: 'Arial', color: '666666' }), new TextRun({ children: [PageNumber.CURRENT], size: 16, font: 'Arial', color: '666666' })] })] }) },
      children }] });
  return Packer.toBuffer(doc).then(buf => { fs.writeFileSync(`out/documents/${d.file}`, buf); console.log('wrote', d.file); });
}
const D = key => spec.docs.find(x => x.key === key);

// ---------- 1. Judgment EN (won) ----------
(async () => {
let d = D('judgment_en_won');
await build(d, [
  C(d.court_en.toUpperCase(), { bold: true, size: 24 }), C('Commercial Circuit', { after: 40 }), C(`Commercial Case No. ${d.court_ref}`, { bold: true }), C(`Judgment pronounced in open court on ${d.doc_date}`), rule(),
  H('Parties'),
  P([['Claimant: ', { bold: true }], [`${CL.en}, a company incorporated in Luxembourg, owner of the registered trademark ${d.mark}, represented by ${d.firm}.`, {}]]),
  P([['Defendant: ', { bold: true }], [`${d.infringer}, a ${d.infringer_type.toLowerCase()} established in ${d.infringer_city}, United Arab Emirates, represented by its manager.`, {}]]),
  H('Facts'),
  P(`The Claimant is the registered proprietor of the trademark ${d.mark} (UAE registration No. ${d.mark_reg}, class ${d.mark_class}), used for ${d.mark_product.toLowerCase()} and sold in the United Arab Emirates through authorised distributors since 2016.`, { num: 'num' }),
  P(`On ${d.opened} the Claimant's brand-protection team documented products bearing a sign identical to the ${d.mark} mark offered for sale by the Defendant. Notarised test purchases were carried out and the samples were examined by the Claimant's authentication laboratory, which confirmed that the products were not manufactured by or under licence from the Claimant.`, { num: 'num' }),
  P(`A cease-and-desist notice was served on the Defendant, who did not respond. The Claimant filed the present action seeking compensation of AED ${d.claim_local}, an order to cease use of the mark, confiscation and destruction of the infringing goods, publication of the judgment and costs.`, { num: 'num' }),
  H("Defendant's submissions"),
  P('The Defendant submitted that it purchased the goods from a wholesaler in good faith, that the goods carried the sign when received, and that it had no knowledge of any infringement. It asked the Court to dismiss the claim or, alternatively, to reduce the compensation.'),
  H('Reasoning of the Court'),
  P('Whereas the registration certificate establishes the Claimant’s exclusive right to the mark in the State, and whereas the expert report confirms that the seized samples bear a sign identical to the registered mark on identical goods, the Court finds that the Defendant used the mark without the proprietor’s authorisation within the meaning of Federal Decree-Law No. 36 of 2021 Concerning Trademarks.'),
  P('Whereas good faith does not excuse a trader from verifying the provenance of branded goods, and the Defendant produced no invoice identifying a lawful source, the Court finds that the Defendant is liable for the harm caused to the Claimant.'),
  P(`Whereas the Claimant quantified its loss by reference to lost sales, the cost of enforcement and damage to the reputation of the mark, and the Court, exercising its discretion under the Civil Transactions Law, assesses the material and moral damage at AED ${d.awarded_local}.`),
  H('Operative part'),
  P('For these reasons, the Court rules:'),
  P(`To order the Defendant to pay the Claimant AED ${d.awarded_local} as compensation for material and moral damage.`, { num: 'num' }),
  P(`To order the Defendant to cease all use of the ${d.mark} mark or any confusingly similar sign on goods, packaging, advertising or online listings.`, { num: 'num' }),
  P('To order the confiscation and destruction of the infringing goods, packaging and printing materials at the Defendant’s expense.', { num: 'num' }),
  P('To order publication of a summary of this judgment in two daily newspapers, one in Arabic and one in English, at the Defendant’s expense.', { num: 'num' }),
  P('To order the Defendant to bear the court fees and expenses and AED 2,000 in advocate’s fees. All other claims are rejected.', { num: 'num' }),
  P(`Judgment issued and signed on ${d.doc_date}. Presiding Judge (signed). Court Clerk (signed).`, { before: 200 }),
]);

// ---------- 2. Judgment AR (KSA) ----------
d = D('judgment_ar_ksa');
await build(d, [
  AC('المملكة العربية السعودية', { bold: true }), AC('وزارة العدل', {}), AC(d.court_ar, { bold: true, size: 26 }), AC(`الدائرة التجارية الثالثة – القضية رقم ${d.court_ref}`, { bold: true }), AC(`تاريخ صدور الحكم: ${d.doc_date_ar}`), rule(),
  AH('أطراف الدعوى'),
  AP([['المدعية: ', { bold: true }], [`${CL.ar}، مالكة العلامة التجارية المسجلة ${d.mark_ar} (${d.mark})، ويمثلها ${d.firm}.`, {}]]),
  AP([['المدعى عليها: ', { bold: true }], [`${d.infringer_ar}، منشأة تجارية بمدينة ${d.infringer_city}، ويمثلها مديرها.`, {}]]),
  AH('الوقائع'),
  AP(`تتلخص وقائع الدعوى في أن المدعية تملك العلامة التجارية ${d.mark_ar} المسجلة في الفئة ${d.mark_class} لمنتجات ${d.mark_product_ar}، وأنها رصدت بتاريخ ${d.opened_ar} عرض المدعى عليها منتجات تحمل علامة مطابقة للعلامة المسجلة دون ترخيص.`, { num: 'anum' }),
  AP('قامت المدعية بشراء عينات موثقة وفحصها لدى مختبرها المعتمد، وثبت أن المنتجات مقلدة وليست من إنتاج المدعية أو من يرخص لها. وقد وُجه للمدعى عليها إنذار قانوني لم تستجب له.', { num: 'anum' }),
  AP(`طلبت المدعية الحكم بإلزام المدعى عليها بدفع تعويض قدره ${d.claim_local} ${d.currency_ar}، ومنعها من استخدام العلامة، وإتلاف المنتجات المقلدة، ونشر الحكم على نفقتها.`, { num: 'anum' }),
  AH('دفاع المدعى عليها'),
  AP('دفعت المدعى عليها بأنها اشترت البضاعة من مورد بحسن نية وأنها لا تعلم بالتقليد، وطلبت رد الدعوى أو تخفيض مبلغ التعويض.'),
  AH('الأسباب'),
  AP('وحيث إن شهادة التسجيل تثبت ملكية المدعية للعلامة وحقها في منع الغير من استعمالها على منتجات مطابقة أو مشابهة وفقاً لنظام العلامات التجارية لدول مجلس التعاون لدول الخليج العربية ولائحته التنفيذية، وحيث ثبت من تقرير الخبير أن العينات المحجوزة تحمل علامة مطابقة للعلامة المسجلة، فإن الدائرة تنتهي إلى ثبوت الاعتداء على العلامة.'),
  AP('وحيث إن حسن النية لا يعفي التاجر من التحقق من مصدر البضائع التي تحمل علامات تجارية، ولم تقدم المدعى عليها ما يثبت مصدراً مشروعاً، فإن المسؤولية تقع عليها.'),
  AP(`وحيث قدرت الدائرة الضرر المادي والمعنوي الذي لحق بالمدعية، فقد رأت تقدير التعويض بمبلغ ${d.awarded_local} ${d.currency_ar}.`),
  AH('منطوق الحكم'),
  AP('لذلك حكمت الدائرة بما يلي:'),
  AP(`إلزام المدعى عليها ${d.infringer_ar} بأن تدفع للمدعية مبلغاً قدره ${d.awarded_local} ${d.currency_ar} تعويضاً عن الأضرار المادية والمعنوية.`, { num: 'anum' }),
  AP(`منع المدعى عليها من استخدام العلامة ${d.mark_ar} أو أي علامة مشابهة لها على المنتجات أو العبوات أو الإعلانات أو المتاجر الإلكترونية.`, { num: 'anum' }),
  AP('مصادرة المنتجات المقلدة والعبوات وأدوات الطباعة وإتلافها على نفقة المدعى عليها.', { num: 'anum' }),
  AP('نشر ملخص الحكم في صحيفة يومية على نفقة المدعى عليها. ورفض ما عدا ذلك من طلبات.', { num: 'anum' }),
  AP(`حكماً قابلاً للاستئناف خلال ثلاثين يوماً من تاريخ استلام نسخة الحكم. صدر بتاريخ ${d.doc_date_ar}. قاضي الدائرة (توقيع). أمين السر (توقيع).`, { before: 200 }),
], true);

// ---------- 3. Judgment EN (lost) ----------
d = D('judgment_en_lost');
await build(d, [
  C(d.court_en.toUpperCase(), { bold: true, size: 24 }), C('Commercial Circuit', { after: 40 }), C(`Commercial Case No. ${d.court_ref}`, { bold: true }), C(`Judgment pronounced on ${d.doc_date}`), rule(),
  H('Parties'),
  P([['Claimant: ', { bold: true }], [`${CL.en}, owner of the registered trademark ${d.mark}${d.firm ? ', represented by ' + d.firm : ''}.`, {}]]),
  P([['Defendant: ', { bold: true }], [`${d.infringer} (${d.infringer_type.toLowerCase()}).`, {}]]),
  H('Facts'),
  P(`The Claimant alleged that, from ${d.opened}, the Defendant offered for sale goods bearing a sign identical to the ${d.mark} mark through online listings and sought compensation of AED ${d.claim_local}, an injunction and destruction of goods.`),
  P('The Defendant denied any sale in the State, submitted that the listings were directed at customers outside the United Arab Emirates, and argued that no infringing act had been proved within the jurisdiction.'),
  H('Reasoning of the Court'),
  P('Whereas the Claimant relied on screenshots of online listings and on correspondence with the platform, without a notarised test purchase or evidence of delivery of goods within the State;'),
  P('Whereas the appointed expert could not confirm that any sale to a consumer in the United Arab Emirates took place, nor that the listings were priced in dirhams or targeted consumers in the State;'),
  P('Whereas the infringing use of a trademark must be established within the territory in which protection is claimed, and the Claimant has not discharged its burden of proof in this respect;'),
  H('Operative part'),
  P('For these reasons, the Court rules:'),
  P('To dismiss the claim for insufficiency of evidence that the Defendant used the mark within the State.', { num: 'num' }),
  P('Each party shall bear its own fees and expenses.', { num: 'num' }),
  P('This judgment is subject to appeal within thirty days of notification.', { num: 'num' }),
  P(`Judgment issued on ${d.doc_date}. Presiding Judge (signed). Court Clerk (signed).`, { before: 200 }),
  P('Internal note (legal operations): the evidence gap identified by the Court (no notarised test purchase, no proof of delivery into the UAE) is now a mandatory step in the investigation checklist before filing.', { before: 300, size: 20 }),
]);

// ---------- 4. Settlement agreement EN ----------
d = D('settlement_en');
await build(d, [
  T('SETTLEMENT AGREEMENT'), C(`Dated ${d.doc_date}`), rule(),
  P([['Between: ', { bold: true }], [`${CL.en} (the “Rights Holder”), represented by ${d.firm}; and`, {}]]),
  P([['And: ', { bold: true }], [`${d.infringer}, ${d.infringer_city}, United Arab Emirates (the “Company”).`, {}]]),
  H('Recitals'),
  P(`A. The Rights Holder owns the trademark ${d.mark} (UAE registration No. ${d.mark_reg}, class ${d.mark_class}).`),
  P(`B. The Rights Holder commenced Commercial Case No. ${d.court_ref} before ${d.court_en} (case reference ${d.case_id}) alleging that the Company dealt in goods bearing the ${d.mark} mark without authorisation.`),
  P('C. The parties wish to settle the dispute on the terms set out below, without admission of liability by the Company.'),
  H('1. Definitions'),
  P('“Infringing Goods” means all products, packaging and promotional material bearing the Mark or any confusingly similar sign that were not supplied by the Rights Holder or its authorised distributors.'),
  H('2. Settlement payment'),
  P(`The Company shall pay the Rights Holder AED ${d.settlement_local} (the “Settlement Sum”) as follows: sixty per cent within fourteen (14) days of signature, and forty per cent within sixty (60) days of signature, by bank transfer to the account notified by the Rights Holder’s counsel.`),
  H('3. Destruction of stock'),
  P('Within thirty (30) days of signature the Company shall deliver up all Infringing Goods in its possession or control for destruction under the supervision of the Rights Holder’s representative, and shall provide a signed inventory and destruction certificate.'),
  H('4. Undertakings'),
  P(`The Company undertakes, for itself and its affiliates, not to manufacture, import, offer for sale, sell or advertise any goods bearing the ${d.mark} mark or any confusingly similar sign, and to disclose in writing the name and address of its supplier of the Infringing Goods within seven (7) days of signature.`),
  H('5. Withdrawal of proceedings'),
  P(`On receipt of the final instalment of the Settlement Sum, the Rights Holder shall file a notice of withdrawal of Commercial Case No. ${d.court_ref}, each party bearing its own costs.`),
  H('6. Confidentiality'),
  P('The terms of this Agreement are confidential, save that the Rights Holder may disclose the existence of the settlement and the undertakings given to courts, customs authorities and online platforms for enforcement purposes.'),
  H('7. Liquidated damages'),
  P('Any breach of clause 4 shall entitle the Rights Holder to liquidated damages of AED 250,000 per breach, without prejudice to any other remedy.'),
  H('8. Governing law and jurisdiction'),
  P('This Agreement is governed by the laws of the United Arab Emirates. The Dubai Courts have exclusive jurisdiction over any dispute arising from it.'),
  P(`Signed for the Rights Holder: ______________________ (${d.lead_counsel}, ${d.lead_title})`, { before: 300 }),
  P(`Signed for the Company: ______________________ (Authorised signatory, ${d.infringer})`),
]);

// ---------- 5. Cease-and-desist EN ----------
d = D('cease_desist_en');
await build(d, [
  P(`${CL.en} – Legal Department`, { bold: true, align: AlignmentType.LEFT, after: 0 }), P('Dubai, United Arab Emirates', { align: AlignmentType.LEFT, after: 0 }), P(`Date: ${d.doc_date}`, { align: AlignmentType.LEFT }),
  P(`To: ${d.infringer}`, { bold: true, align: AlignmentType.LEFT, after: 0 }), P(`${d.infringer_city}, United Arab Emirates`, { align: AlignmentType.LEFT, after: 0 }), P('By courier and e-mail – WITHOUT PREJUDICE SAVE AS TO COSTS', { align: AlignmentType.LEFT }),
  P(`Re: Unauthorised use of the ${d.mark} trademark – our reference ${d.case_id}`, { bold: true }), rule(),
  H('Our client’s rights'),
  P(`We act for ${CL.en}, the registered proprietor of the trademark ${d.mark} (UAE registration No. ${d.mark_reg}, class ${d.mark_class}) covering ${d.mark_product.toLowerCase()}. The mark has been used in the United Arab Emirates for many years and enjoys substantial goodwill.`),
  H('The infringement'),
  P(`It has come to our client’s attention that you are offering for sale and distributing products bearing a sign identical, or confusingly similar, to the ${d.mark} mark, without our client’s authorisation. Test purchases made on ${d.opened} confirmed that the products are not genuine. Copies of the receipts and photographs are enclosed.`),
  P('Your conduct constitutes trademark infringement and unfair competition under Federal Decree-Law No. 36 of 2021 Concerning Trademarks and exposes you to civil and criminal liability.'),
  H('Our demands'),
  P('Within fourteen (14) days of the date of this letter, you must:'),
  P(`cease immediately all import, offer for sale, sale, distribution and advertising of goods bearing the ${d.mark} mark or any similar sign;`, { num: 'num' }),
  P('deliver up to our client, or destroy under supervision, all such goods, packaging and promotional material in your possession or control;', { num: 'num' }),
  P('disclose in writing the identity of your supplier, the quantities purchased and sold, and the prices obtained; and', { num: 'num' }),
  P('sign and return the enclosed undertaking.', { num: 'num' }),
  H('Consequences'),
  P('If you fail to comply, our client will commence proceedings without further notice, seeking an injunction, compensation, destruction of the goods, publication of the judgment and costs, and will refer the matter to the competent authorities. Our client reserves all its rights.'),
  P('Yours faithfully,', { before: 200 }),
  P(`${d.lead_counsel}`, { bold: true, after: 0, align: AlignmentType.LEFT }), P(`${d.lead_title}, ${CL.en}`, { align: AlignmentType.LEFT }),
  P('Enclosures: registration certificate; test purchase receipts and photographs; form of undertaking.', { size: 20 }),
]);

// ---------- 6. Cease-and-desist AR (Egypt) ----------
d = D('cease_desist_ar');
await build(d, [
  AP(`${d.firm} – محامون ومستشارون قانونيون`, { bold: true, after: 0 }), AP('القاهرة – جمهورية مصر العربية', { after: 0 }), AP(`التاريخ: ${d.doc_date_ar}`),
  AP(`السادة / ${d.infringer_ar}`, { bold: true, after: 0 }), AP(`${d.infringer_city} – جمهورية مصر العربية`, { after: 0 }), AP('يُسلم باليد وبالبريد المسجل بعلم الوصول'),
  AP(`الموضوع: إنذار قانوني بالتوقف عن الاعتداء على العلامة التجارية ${d.mark_ar} (${d.mark}) – مرجعنا ${d.case_id}`, { bold: true }), rule(),
  AH('حقوق موكلتنا'),
  AP(`نتشرف بإحاطتكم علماً بأننا نمثل ${CL.ar}، مالكة العلامة التجارية ${d.mark_ar} المسجلة في الفئة ${d.mark_class} لمنتجات ${d.mark_product_ar}، والمسجلة والمستعملة في جمهورية مصر العربية ودول المنطقة منذ سنوات، والتي تتمتع بشهرة واسعة لدى جمهور المستهلكين.`),
  AH('المخالفة'),
  AP(`نما إلى علم موكلتنا قيامكم بتصنيع و/أو استيراد وعرض وبيع منتجات تحمل علامة مطابقة أو مشابهة بدرجة تؤدي إلى اللبس مع العلامة ${d.mark_ar} دون ترخيص من موكلتنا. وقد تم إجراء شراء اختباري بتاريخ ${d.opened_ar} وثبت أن المنتجات غير أصلية. مرفق صور المنتجات وإيصالات الشراء.`),
  AP('إن ما تقومون به يشكل اعتداءً على العلامة التجارية ومنافسة غير مشروعة وفقاً لأحكام قانون حماية حقوق الملكية الفكرية رقم 82 لسنة 2002 ولائحته التنفيذية، ويعرضكم للمساءلة المدنية والجنائية.'),
  AH('المطالب'),
  AP('لذلك نطالبكم، خلال خمسة عشر (15) يوماً من تاريخ هذا الإنذار، بما يلي:'),
  AP(`التوقف فوراً عن استيراد وتصنيع وعرض وبيع وتوزيع والإعلان عن أي منتجات تحمل العلامة ${d.mark_ar} أو أي علامة مشابهة لها.`, { num: 'anum' }),
  AP('تسليم موكلتنا جميع المنتجات والعبوات والمواد الدعائية المخالفة أو إتلافها تحت إشراف ممثلها.', { num: 'anum' }),
  AP('الإفصاح كتابةً عن مصدر المنتجات والكميات المستوردة والمباعة وأسعار البيع.', { num: 'anum' }),
  AP('توقيع التعهد الكتابي المرفق وإعادته إلينا.', { num: 'anum' }),
  AH('التبعات'),
  AP('وفي حال عدم الاستجابة خلال المهلة المحددة، ستضطر موكلتنا إلى اتخاذ كافة الإجراءات القانونية أمام المحكمة الاقتصادية المختصة والجهات الإدارية والجمركية، للمطالبة بالمنع والتعويض والإتلاف ونشر الحكم، مع تحميلكم كافة الرسوم والمصاريف، مع حفظ كافة حقوق موكلتنا.'),
  AP('وتفضلوا بقبول فائق الاحترام،', { before: 200 }),
  AP(`${d.firm}`, { bold: true, after: 0 }), AP(`بالنيابة عن ${CL.ar}`),
  AP('المرفقات: شهادة تسجيل العلامة؛ إيصالات الشراء الاختباري والصور؛ نموذج التعهد.', { size: 20 }),
], true);

// ---------- 7. Customs seizure notice AR ----------
d = D('customs_ar');
await build(d, [
  AC('حكومة دبي', { bold: true }), AC(d.court_ar, { bold: true, size: 26 }), AC('إخطار حجز جمركي – حقوق الملكية الفكرية', { bold: true }), rule(),
  table([['البيان', 'التفاصيل'], ['رقم الإخطار', `IPR/${d.court_ref}`], ['تاريخ الإخطار', d.doc_date_ar], ['مرجع صاحب الحق', d.case_id],
         ['المستورد', `${d.infringer_ar} (${d.infringer})`], ['العلامة التجارية', `${d.mark_ar} (${d.mark}) – تسجيل رقم ${d.mark_reg}`], ['صاحب الحق', CL.ar],
         ['وصف البضاعة', `${d.mark_product_ar} في عبوات تحمل العلامة`], ['الكمية المحجوزة', `${d.seized_units.toLocaleString('en-US')} وحدة`], ['القيمة التقديرية', `${d.claim_local} ${d.currency_ar}`],
         ['منفذ الدخول', 'ميناء جبل علي – البيان الجمركي رقم ' + Math.floor(100000 + Math.random() * 899999)], ['مكان الحجز', 'مستودع الجمارك – جبل علي']], [2800, 6300], true),
  AH('الإجراء'),
  AP(`تم إيقاف الإفراج عن الإرسالية المبينة أعلاه للاشتباه في كونها بضائع مقلدة تحمل علامة تجارية مسجلة، وذلك بتاريخ ${d.doc_date_ar} بناءً على طلب الحماية الجمركية المسجل لصالح صاحب الحق.`),
  AP('على صاحب الحق أو وكيله خلال عشرة (10) أيام عمل من تاريخ هذا الإخطار: معاينة العينات وتقديم تقرير فحص، وتقديم شكوى رسمية أو إقرار بعدم الاعتراض، وتقديم الضمان المالي المقرر إن لزم.'),
  AP('في حال ثبوت التقليد يتم تطبيق الإجراءات المقررة بشأن البضائع المخالفة، بما في ذلك المصادرة والإتلاف على نفقة المستورد، وإحالة الموضوع إلى الجهات المختصة.'),
  AP('ضابط حقوق الملكية الفكرية (توقيع وختم)', { before: 300 }),
], true);

// ---------- 8. Investigation report EN ----------
d = D('investigation_en');
await build(d, [
  T('TEST PURCHASE AND INVESTIGATION REPORT'), C('BrandGuard Investigations FZ-LLC – prepared for the Legal Department of ' + CL.en), C(`Report reference BG-${d.court_ref} · Case ${d.case_id} · ${d.doc_date}`), rule(),
  H('1. Objective'),
  P(`To verify whether products bearing the ${d.mark} mark offered by ${d.infringer} (${d.infringer_type.toLowerCase()}, ${d.infringer_city}) are genuine, and to secure evidence suitable for civil and administrative proceedings in the United Arab Emirates.`),
  H('2. Method'),
  P(`A covert test purchase was conducted on ${d.opened} by two investigators. ${d.test_units} units were purchased at AED ${d.unit_price} each (receipt No. ${Math.floor(1000 + Math.random() * 8999)}, copy attached). The purchase was witnessed and the samples were sealed, photographed and delivered to the Rights Holder’s authentication laboratory within 24 hours under chain-of-custody form CoC-${d.court_ref}.`),
  H('3. Findings'),
  table([['Check', 'Genuine reference', 'Sample result', 'Outcome'],
         ['Security hologram', 'Present, colour-shifting', 'Absent', 'Fail'],
         ['Batch code format', 'L + 7 digits, laser-etched', 'Inkjet, 6 digits', 'Fail'],
         ['Packaging print', 'Pantone-matched, sharp registration', 'Colour shift, blurred edges', 'Fail'],
         ['Net weight', 'As declared ± 2 g', '− 9 g to − 14 g', 'Fail'],
         ['Inner wrapper foil', 'Embossed logo', 'Plain foil', 'Fail'],
         ['Price point', `AED ${d.unit_price + 10}–${d.unit_price + 14} (authorised retail)`, `AED ${d.unit_price}`, 'Indicative']], [2300, 2600, 2600, 1600]),
  P(`All ${d.test_units} units failed the authentication checklist on at least four of five criteria. The laboratory certificate (LAB-${d.court_ref}) confirms that the samples were not manufactured by or under licence from the Rights Holder.`, { before: 160 }),
  H('4. Observations on the premises'),
  P(`Approximately 350–400 units of the same product were visible in stock. Staff stated that the goods are delivered weekly by a van from Sharjah and that “the price is lower because they come direct from the importer”. The investigator noted a second ${d.mark_product.toLowerCase()} line with similar characteristics.`),
  H('5. Evidence secured'),
  P('Sealed samples (' + d.test_units + ' units) under chain of custody; purchase receipt; 14 photographs of the shelf display, shop front and samples; investigator statements; laboratory certificate.', { num: 'bul' }),
  H('6. Recommendation'),
  P('Serve a cease-and-desist notice, request supplier disclosure, and in parallel lodge a complaint with the Department of Economic Development for an administrative inspection; the evidence secured meets the standard applied by the Dubai Courts for test purchases.'),
  P('Lead investigator (signed) · Reviewed by ' + d.lead_counsel + ', ' + d.lead_title, { before: 200, size: 20 }),
]);

// ---------- 9. Licence agreement EN ----------
d = D('licence_en');
await build(d, [
  T('TRADEMARK LICENCE AND DISTRIBUTION AGREEMENT'), C(`Dated ${d.doc_date}`), rule(),
  P([['Licensor: ', { bold: true }], [`${CL.en}, Luxembourg.`, {}]]),
  P([['Licensee: ', { bold: true }], [`${d.infringer}, ${d.infringer_city}, United Arab Emirates.`, {}]]),
  H('1. Grant'),
  P(`The Licensor grants the Licensee a non-exclusive, non-transferable licence to use the trademark ${d.mark} (UAE registration No. ${d.mark_reg}, class ${d.mark_class}) solely in connection with the import, distribution and sale of genuine ${d.mark} products supplied by the Licensor (the “Products”).`),
  H('2. Term'),
  P(`Three (3) years from the date of this Agreement, renewable by written agreement. Either party may terminate on ninety (90) days’ notice.`),
  H('3. Territory'),
  P('The licence is limited to the United Arab Emirates (the “Territory”). The Licensee shall not sell, export or supply the Products, directly or indirectly, to customers outside the Territory, and shall not import Products other than those supplied by the Licensor or its designated regional distributor. Any sale outside the Territory, or import of Products not destined for the Territory, is a material breach entitling the Licensor to terminate immediately.'),
  H('4. Quality control'),
  P('The Licensee shall store and handle the Products in accordance with the Licensor’s written guidelines, permit inspection of its premises on reasonable notice, and withdraw from sale any Product the Licensor identifies as non-conforming.'),
  H('5. Marking and advertising'),
  P('The Licensee shall use the mark only in the form approved by the Licensor and shall submit all advertising using the mark for prior written approval.'),
  H('6. Royalty'),
  P('The Licensee shall pay a royalty of four and a half per cent (4.5%) of net sales of the Products, payable quarterly within thirty (30) days of the end of each calendar quarter, together with a statement of sales by product and customer.'),
  H('7. Records and audit'),
  P('The Licensee shall keep complete records of purchases, sales and stock of the Products for five (5) years and shall allow the Licensor’s auditors to inspect them on ten (10) days’ notice.'),
  H('8. Termination'),
  P('On termination the Licensee shall cease all use of the mark, return or destroy promotional material, and sell remaining genuine stock in the Territory within sixty (60) days.'),
  H('9. Governing law'),
  P('This Agreement is governed by the laws of the United Arab Emirates; the Dubai Courts have exclusive jurisdiction.'),
  P('Signed for the Licensor: ______________________', { before: 300 }), P('Signed for the Licensee: ______________________'),
]);

// ---------- 10. Statement of claim EN ----------
d = D('claim_en');
await build(d, [
  C(`BEFORE ${d.court_en.toUpperCase()}`, { bold: true, size: 24 }), C(`Commercial Case No. ${d.court_ref}`, { bold: true }), C('STATEMENT OF CLAIM', { bold: true, size: 26 }), C(`Filed on ${d.doc_date}`), rule(),
  P([['Claimant: ', { bold: true }], [`${CL.en}, represented by ${d.firm}.`, {}]]),
  P([['Defendant: ', { bold: true }], [`${d.infringer}, ${d.infringer_city}, United Arab Emirates.`, {}]]),
  H('Subject of the claim'),
  P(`Trademark infringement and unfair competition in respect of the registered trademark ${d.mark} (UAE registration No. ${d.mark_reg}, class ${d.mark_class}).`),
  H('Facts'),
  P(`The Claimant is the registered proprietor of the ${d.mark} mark, used for ${d.mark_product.toLowerCase()}, and distributes genuine products in the State through authorised distributors.`, { num: 'num' }),
  P(`On ${d.opened} the Claimant identified products bearing a sign identical to the mark offered by the Defendant (${d.infringer_type.toLowerCase()}). Test purchases were carried out and the samples were certified as counterfeit by the Claimant’s laboratory.`, { num: 'num' }),
  P('A cease-and-desist notice was served on the Defendant, which failed to cease the infringing conduct or to disclose its supplier.', { num: 'num' }),
  P('The Defendant’s conduct has caused the Claimant loss of sales, enforcement costs and damage to the reputation of the mark, and has misled consumers as to the origin of the goods.', { num: 'num' }),
  H('Legal basis'),
  P('Federal Decree-Law No. 36 of 2021 Concerning Trademarks; the provisions of the Civil Transactions Law on liability for harmful acts; Federal Decree-Law No. 50 of 2022 (Commercial Transactions Law) on unfair competition.'),
  H('Evidence'),
  P('Registration certificate; test purchase receipts and photographs; laboratory certificate; investigation report; cease-and-desist notice and proof of service; expert valuation of loss.', { num: 'bul' }),
  H('Relief sought'),
  P(`Order the Defendant to pay the Claimant AED ${d.claim_local} as compensation for material and moral damage.`, { num: 'num' }),
  P(`Order the Defendant to cease all use of the ${d.mark} mark and any confusingly similar sign.`, { num: 'num' }),
  P('Order the confiscation and destruction of the infringing goods, packaging and printing materials.', { num: 'num' }),
  P('Order publication of the judgment in two daily newspapers at the Defendant’s expense.', { num: 'num' }),
  P('Order the Defendant to bear fees, expenses and advocate’s fees.', { num: 'num' }),
  P(d.next_hearing ? `The matter is listed for hearing on ${d.next_hearing}.` : 'The Claimant requests the earliest available hearing date.', { before: 160 }),
  P(`For the Claimant: ${d.firm} (signed)`, { before: 200 }),
]);

// ---------- 11. Takedown notice EN ----------
d = D('takedown_en');
await build(d, [
  P(`${CL.en} – Legal Department`, { bold: true, align: AlignmentType.LEFT, after: 0 }), P(`Date: ${d.doc_date}`, { align: AlignmentType.LEFT }),
  P('To: Google LLC – Google Play Legal Support (Trademark complaints)', { bold: true, align: AlignmentType.LEFT }),
  P(`Re: Trademark infringement notice – application “${d.mark} Kids Game” by ${d.infringer} – our reference ${d.case_id}`, { bold: true }), rule(),
  H('Rights holder'),
  P(`${CL.en} is the registered proprietor of the trademark ${d.mark} (UAE registration No. ${d.mark_reg}, class ${d.mark_class}; corresponding registrations in Kuwait, Saudi Arabia and Egypt).`),
  H('Infringing application'),
  P(`The application “${d.mark} Kids Game”, published by ${d.infringer} and available on Google Play in Kuwait, the United Arab Emirates and Saudi Arabia, uses the ${d.mark} name and logo in its title, icon and store listing without authorisation. The listing suggests an official connection with the rights holder, misleads consumers, and collects user data under the rights holder’s brand.`),
  H('Request'),
  P('We request that the application and its store listing be removed, and that the developer be notified of this complaint.', { num: 'num' }),
  P('We request disclosure of the developer’s registered contact details for the purpose of enforcement.', { num: 'num' }),
  H('Declarations'),
  P('I have a good-faith belief that the use of the mark described above is not authorised by the trademark owner, its agent or the law. The information in this notice is accurate and, under penalty of perjury, I am authorised to act on behalf of the owner of the trademark.'),
  P(`${d.lead_counsel}, ${d.lead_title}, for ${CL.en}`, { before: 200, bold: true }),
]);

// ---------- 12. Trademark office decision AR (SAIP) ----------
d = D('tm_office_ar');
await build(d, [
  AC('المملكة العربية السعودية', { bold: true }), AC('الهيئة السعودية للملكية الفكرية', { bold: true, size: 26 }), AC('لجنة النظر في اعتراضات العلامات التجارية', { bold: true }), AC(`قرار رقم ${d.court_ref} – بتاريخ ${d.doc_date_ar}`), rule(),
  AH('أطراف الاعتراض'),
  AP([['المعترضة: ', { bold: true }], [`${CL.ar}، مالكة العلامة التجارية المسجلة ${d.mark_ar} (${d.mark}).`, {}]]),
  AP([['المعترض ضدها: ', { bold: true }], [`${d.infringer_ar} (${d.infringer})، مقدمة طلب تسجيل العلامة المتعارضة في الفئة ${d.mark_class}.`, {}]]),
  AH('الوقائع'),
  AP(`تقدمت المعترض ضدها بطلب تسجيل علامة تجارية في الفئة ${d.mark_class} لمنتجات ${d.mark_product_ar}، ونُشر الطلب في النشرة الرسمية. وتقدمت المعترضة باعتراضها خلال المدة النظامية بتاريخ ${d.opened_ar} استناداً إلى تشابه العلامة المطلوب تسجيلها مع علامتها المسجلة والمشهورة ${d.mark_ar}.`),
  AH('الأسباب'),
  AP('وحيث إن المقارنة بين العلامتين من حيث الشكل والنطق والانطباع العام تُظهر تشابهاً من شأنه أن يؤدي إلى لبس لدى جمهور المستهلكين، لا سيما وأن المنتجات متطابقة وتُعرض عبر قنوات التوزيع ذاتها؛'),
  AP('وحيث إن المعترضة أثبتت أسبقية تسجيلها واستعمالها للعلامة في المملكة وشهرتها لدى الجمهور، وأن المعترض ضدها لم تقدم ما يثبت حسن نيتها أو تميز علامتها؛'),
  AP('وعملاً بأحكام نظام العلامات التجارية لدول مجلس التعاون لدول الخليج العربية ولائحته التنفيذية؛'),
  AH('القرار'),
  AP('قبول الاعتراض شكلاً وموضوعاً.', { num: 'anum' }),
  AP(`رفض طلب تسجيل العلامة التجارية المقدم من ${d.infringer_ar} في الفئة ${d.mark_class} لتشابهها مع العلامة المسجلة ${d.mark_ar}.`, { num: 'anum' }),
  AP('إلزام المعترض ضدها بالرسوم المقررة. ويجوز التظلم من هذا القرار خلال ستين يوماً من تاريخ الإبلاغ به.', { num: 'anum' }),
  AP('رئيس اللجنة (توقيع)     أعضاء اللجنة (توقيع)', { before: 300 }),
], true);
console.log('done');
})();
