"""Small DOCX builder on top of python-docx that handles English and Arabic (RTL) documents.

Arabic paragraphs are marked bidi; Arabic text goes in w:rtl runs while IDs, numbers and Latin
names go in their own LTR runs, so '476/2024' or 'TM-2024-403' never render reversed.
Arabic uses Segoe UI: Word's PDF export maps its lam-alef ligatures correctly, so the text
layer reads 'العلامة' (Arial/Tahoma/Times come out as 'العالمة').
All XML children are inserted in schema order so Word opens the files without repair.
"""
import re
import docx
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_TABLE_DIRECTION
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, Twips

LATIN, ARABIC = 'Arial', 'Segoe UI'
# Latin/number runs inside Arabic text. Brackets stay in the RTL runs so Word mirrors both of them
# consistently ('فيلورا (VELORA)'); putting one of them in the LTR run gives 'فيلورا ((VELORA'.
LTR_RE = re.compile(r"[A-Za-z0-9À-ɏ][A-Za-z0-9À-ɏ\-/.,:&'’ %+#@_=?–·]*[A-Za-z0-9À-ɏ%]|[A-Za-z0-9À-ɏ]")

PPR_SEQ = ['pStyle', 'keepNext', 'keepLines', 'pageBreakBefore', 'framePr', 'widowControl', 'numPr', 'suppressLineNumbers', 'pBdr', 'shd', 'tabs',
           'suppressAutoHyphens', 'kinsoku', 'wordWrap', 'overflowPunct', 'topLinePunct', 'autoSpaceDE', 'autoSpaceDN', 'bidi', 'adjustRightInd',
           'snapToGrid', 'spacing', 'ind', 'contextualSpacing', 'mirrorIndents', 'suppressOverlap', 'jc', 'textDirection', 'textAlignment',
           'textboxTightWrap', 'outlineLvl', 'divId', 'cnfStyle', 'rPr', 'sectPr', 'pPrChange']
RPR_SEQ = ['rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike', 'dstrike', 'outline', 'shadow', 'emboss', 'imprint', 'noProof',
           'snapToGrid', 'vanish', 'webHidden', 'color', 'spacing', 'w', 'kern', 'position', 'sz', 'szCs', 'highlight', 'u', 'effect', 'bdr', 'shd',
           'fitText', 'vertAlign', 'rtl', 'cs', 'em', 'lang', 'eastAsianLayout', 'specVanish', 'oMath']
TBLPR_SEQ = ['tblStyle', 'tblpPr', 'tblOverlap', 'bidiVisual', 'tblStyleRowBandSize', 'tblStyleColBandSize', 'tblW', 'jc', 'tblCellSpacing', 'tblInd',
             'tblBorders', 'shd', 'tblLayout', 'tblCellMar', 'tblLook', 'tblCaption', 'tblDescription', 'tblPrChange']
TCPR_SEQ = ['cnfStyle', 'tcW', 'gridSpan', 'hMerge', 'vMerge', 'tcBorders', 'shd', 'noWrap', 'tcMar', 'textDirection', 'tcFitText', 'vAlign', 'hideMark',
            'headers', 'cellIns', 'cellDel', 'cellMerge', 'tcPrChange']

def el(tag, **attrs):
    e = OxmlElement('w:' + tag)
    for k, v in attrs.items():
        e.set(qn('w:' + k), str(v))
    return e

def put(parent, child, seq):
    """Insert child into parent respecting schema order; replaces an existing element of the same tag."""
    tag = child.tag.split('}')[1]
    for old in parent.findall(qn('w:' + tag)):
        parent.remove(old)
    idx = seq.index(tag)
    for sib in list(parent):
        st = sib.tag.split('}')[1]
        if st in seq and seq.index(st) > idx:
            sib.addprevious(child)
            return child
    parent.append(child)
    return child

def clean_theme_fonts(rfonts, rtl_font=ARABIC):
    for a in ('asciiTheme', 'hAnsiTheme', 'eastAsiaTheme', 'cstheme'):
        rfonts.attrib.pop(qn('w:' + a), None)
    rfonts.set(qn('w:ascii'), LATIN); rfonts.set(qn('w:hAnsi'), LATIN); rfonts.set(qn('w:eastAsia'), LATIN); rfonts.set(qn('w:cs'), rtl_font)


class DocBuilder:
    def __init__(self, lang, footer_left, meta):
        self.lang = lang
        self.rtl = lang == 'AR'
        self.base = 11.5 if self.rtl else 10.5
        self.d = docx.Document()
        sec = self.d.sections[0]
        sec.page_width, sec.page_height = Mm(210), Mm(297)
        sec.top_margin, sec.bottom_margin = Twips(1250), Twips(1150)
        sec.left_margin = sec.right_margin = Twips(1300)
        sec.header_distance, sec.footer_distance = Twips(560), Twips(500)
        if self.rtl:
            put(sec._sectPr, el('bidi'), ['footnotePr', 'endnotePr', 'type', 'pgSz', 'pgMar', 'paperSrc', 'pgBorders', 'lnNumType', 'pgNumType', 'cols',
                                          'formProt', 'vAlign', 'noEndnote', 'titlePg', 'textDirection', 'bidi', 'rtlGutter', 'docGrid', 'printerSettings', 'sectPrChange'])
        self._styles()
        self._footer(footer_left)
        cp = self.d.core_properties
        cp.title, cp.subject, cp.author = meta['title'], meta['subject'], meta['author']
        cp.keywords, cp.category, cp.comments = meta['keywords'], meta['subject'], meta['comments']
        cp.last_modified_by = meta['author']
        cp.created = cp.modified = meta['when']
        cp.language = 'ar-AE' if self.rtl else 'en-GB'
        self.body_width_mm = 210 - 2 * 1300 / 56.7

    # ------------------------------------------------------------------ setup
    def _styles(self):
        styles = self.d.styles.element
        rpr_default = styles.find(qn('w:docDefaults')).find(qn('w:rPrDefault')).find(qn('w:rPr'))
        rf = rpr_default.find(qn('w:rFonts'))
        if rf is None:
            rf = put(rpr_default, el('rFonts'), RPR_SEQ)
        clean_theme_fonts(rf)
        put(rpr_default, el('sz', val=int(self.base * 2)), RPR_SEQ)
        put(rpr_default, el('szCs', val=int(self.base * 2)), RPR_SEQ)
        put(rpr_default, el('lang', val='en-GB', eastAsia='en-US', bidi='ar-AE'), RPR_SEQ)
        ppr_default = styles.find(qn('w:docDefaults')).find(qn('w:pPrDefault'))
        if ppr_default is not None and ppr_default.find(qn('w:pPr')) is not None:
            put(ppr_default.find(qn('w:pPr')), el('spacing', after=0, line=264, lineRule='auto'), PPR_SEQ)
        for s in self.d.styles:
            rpr = s.element.find(qn('w:rPr'))
            if rpr is None:
                continue
            f = rpr.find(qn('w:rFonts'))
            if f is not None:
                clean_theme_fonts(f)
            c = rpr.find(qn('w:color'))
            if c is not None:
                for a in ('themeColor', 'themeShade', 'themeTint'):
                    c.attrib.pop(qn('w:' + a), None)
                c.set(qn('w:val'), '000000')

    def _footer(self, text):
        p = self.d.sections[0].footer.paragraphs[0]
        self._ppr(p, 'center', 0, 0)
        pg, of = ('صفحة', 'من') if self.rtl else ('Page', 'of')
        self._runs(p, f'{text}   {pg} ', size=7.5, color='6B6B6B')
        self._field(p, 'PAGE', '1', 7.5, '6B6B6B')
        self._runs(p, f' {of} ', size=7.5, color='6B6B6B')
        self._field(p, 'NUMPAGES', '1', 7.5, '6B6B6B')

    def _field(self, p, instr, placeholder, size, color):
        fld = el('fldSimple', instr=instr)
        r = OxmlElement('w:r')
        r.append(self._rpr(False, False, False, size, color))
        t = OxmlElement('w:t'); t.text = placeholder; r.append(t)
        fld.append(r)
        p._p.append(fld)

    # ------------------------------------------------------------------ low level
    def _rpr(self, rtl, bold, italic, size, color, font=None):
        rpr = OxmlElement('w:rPr')
        f = el('rFonts', ascii=font or LATIN, hAnsi=font or LATIN, eastAsia=font or LATIN, cs=ARABIC if not font else font)
        put(rpr, f, RPR_SEQ)
        if bold:
            put(rpr, el('b'), RPR_SEQ); put(rpr, el('bCs'), RPR_SEQ)
        if italic:
            put(rpr, el('i'), RPR_SEQ); put(rpr, el('iCs'), RPR_SEQ)
        if color:
            put(rpr, el('color', val=color), RPR_SEQ)
        sz = int(round((size or self.base) * 2))
        put(rpr, el('sz', val=sz), RPR_SEQ); put(rpr, el('szCs', val=sz), RPR_SEQ)
        if rtl:
            put(rpr, el('rtl'), RPR_SEQ)
            put(rpr, el('lang', bidi='ar-AE'), RPR_SEQ)
        return rpr

    def _run(self, p, text, rtl, bold=False, italic=False, size=None, color=None, font=None):
        r = p.add_run()
        r._r.insert(0, self._rpr(rtl, bold, italic, size, color, font))
        r.text = text
        return r

    def _runs(self, p, text, bold=False, italic=False, size=None, color=None, rtl=None, font=None):
        rtl = self.rtl if rtl is None else rtl
        if not rtl:
            self._run(p, text, False, bold, italic, size, color, font)
            return
        pos = 0
        for m in LTR_RE.finditer(text):
            if m.start() > pos:
                self._run(p, text[pos:m.start()], True, bold, italic, size, color, font)
            self._run(p, m.group(), False, bold, italic, size, color, font)
            pos = m.end()
        if pos < len(text):
            self._run(p, text[pos:], True, bold, italic, size, color, font)

    def _ppr(self, p, align, before, after, keep_next=False, ind_start=None, hanging=None, rtl=None, line=None, border_bottom=None, shade=None, outline=None):
        rtl = self.rtl if rtl is None else rtl
        ppr = p._p.get_or_add_pPr()
        if keep_next:
            put(ppr, el('keepNext'), PPR_SEQ)
        if border_bottom:
            b = el('pBdr'); b.append(el('bottom', val='single', sz=border_bottom[0], space=4, color=border_bottom[1])); put(ppr, b, PPR_SEQ)
        if shade:
            put(ppr, el('shd', val='clear', color='auto', fill=shade), PPR_SEQ)
        if rtl:
            put(ppr, el('bidi'), PPR_SEQ)
        sp = el('spacing', before=int(before * 20), after=int(after * 20))
        if line:
            sp.set(qn('w:line'), str(int(line * 240))); sp.set(qn('w:lineRule'), 'auto')
        put(ppr, sp, PPR_SEQ)
        if ind_start is not None or hanging is not None:
            ind = el('ind')
            if ind_start is not None:
                ind.set(qn('w:start'), str(int(ind_start)))
            if hanging is not None:
                ind.set(qn('w:hanging'), str(int(hanging)))
            put(ppr, ind, PPR_SEQ)
        jc = {'left': 'right' if rtl else 'left', 'start': 'right' if rtl else 'left', 'right': 'left' if rtl else 'right', 'end': 'left' if rtl else 'right',
              'center': 'center', 'both': 'both'}[align]
        put(ppr, el('jc', val=jc), PPR_SEQ)
        if outline is not None:
            put(ppr, el('outlineLvl', val=outline), PPR_SEQ)

    # ------------------------------------------------------------------ blocks
    def para(self, text, align='both', bold=False, italic=False, size=None, before=0, after=6, color=None, keep_next=False, style=None, line=None, shade=None):
        p = self.d.add_paragraph(style=style)
        self._ppr(p, align, before, after, keep_next=keep_next, line=line, shade=shade)
        parts = text if isinstance(text, list) else [(text, {})]
        for t, o in parts:
            self._runs(p, t, bold=o.get('bold', bold), italic=o.get('italic', italic), size=o.get('size', size), color=o.get('color', color))
        return p

    def title(self, text, size=15, after=4, before=0, color='111111'):
        return self.para(text, align='center', bold=True, size=size, before=before, after=after, color=color, style='Title', keep_next=True)

    def center(self, text, bold=False, size=None, after=1, before=0, color=None, italic=False):
        return self.para(text, align='center', bold=bold, size=size, after=after, before=before, color=color, italic=italic, keep_next=True)

    def h1(self, text, before=10, after=4):
        p = self.d.add_paragraph(style='Heading 1')
        self._ppr(p, 'start', before, after, keep_next=True, outline=0)
        self._runs(p, text, bold=True, size=self.base + 1.5, color='1F1F1F')
        return p

    def h2(self, text, before=6, after=3):
        p = self.d.add_paragraph(style='Heading 2')
        self._ppr(p, 'start', before, after, keep_next=True, outline=1)
        self._runs(p, text, bold=True, size=self.base + 0.5, color='333333')
        return p

    def numbered(self, items, start=1, after=4, size=None, fmt='{n}.', indent=420):
        for k, item in enumerate(items):
            p = self.d.add_paragraph()
            self._ppr(p, 'both', 0, after, ind_start=indent, hanging=indent)
            letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و', 'ز', 'ح', 'ط', 'ي'] if self.rtl else list('abcdefghijklmnopqrstuvwxyz')
            label = fmt.format(n=start + k, a=letters[(start + k - 1) % len(letters)])
            self._runs(p, label + '\t', size=size)
            parts = item if isinstance(item, list) else [(item, {})]
            for t, o in parts:
                self._runs(p, t, bold=o.get('bold', False), size=o.get('size', size), italic=o.get('italic', False))

    def bullets(self, items, after=3, size=None):
        self.numbered(items, after=after, size=size, fmt='•', indent=360)

    def rule(self, color='9A9A9A', after=8, size=6):
        p = self.d.add_paragraph()
        self._ppr(p, 'center', 0, after, border_bottom=(size, color))
        return p

    def spacer(self, pt=6):
        p = self.d.add_paragraph()
        self._ppr(p, 'start', 0, 0)
        self._run(p, '', False, size=pt / 2)
        return p

    def page_break(self):
        p = self.d.add_paragraph()
        self._ppr(p, 'start', 0, 0)
        p.add_run().add_break(WD_BREAK.PAGE)

    def image(self, path, width_mm, align='center', after=4, caption=None, before=0):
        p = self.d.add_paragraph()
        self._ppr(p, align, before, after if not caption else 1, keep_next=bool(caption))
        p.add_run().add_picture(str(path), width=Mm(width_mm))
        if caption:
            self.para(caption, align=align, italic=True, size=self.base - 1.5, after=after, color='444444')

    # ------------------------------------------------------------------ tables
    def _table(self, nrows, widths_mm, borders=True):
        t = self.d.add_table(rows=nrows, cols=len(widths_mm))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        if self.rtl:
            t.table_direction = WD_TABLE_DIRECTION.RTL
        tblPr = t._tbl.tblPr
        b = el('tblBorders')
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            b.append(el(side, val='single' if borders else 'nil', sz=4, space=0, color='A6A6A6'))
        put(tblPr, b, TBLPR_SEQ)
        mar = el('tblCellMar')
        for side, v in (('top', 50), ('left', 90), ('bottom', 50), ('right', 90)):
            mar.append(el(side, w=v, type='dxa'))
        put(tblPr, mar, TBLPR_SEQ)
        put(tblPr, el('tblW', w=int(sum(widths_mm) * 56.7), type='dxa'), TBLPR_SEQ)
        put(tblPr, el('tblLayout', type='fixed'), TBLPR_SEQ)
        grid = t._tbl.tblGrid
        for gc, w in zip(grid.findall(qn('w:gridCol')), widths_mm):
            gc.set(qn('w:w'), str(int(w * 56.7)))
        for row in t.rows:
            for cell, w in zip(row.cells, widths_mm):
                cell.width = Mm(w)
            row._tr.get_or_add_trPr().append(el('cantSplit'))     # a signature or table row never breaks across pages
        return t

    def _cell(self, cell, text, bold=False, size=None, shade=None, align='start', color=None, italic=False):
        p = cell.paragraphs[0]
        self._ppr(p, align, 0, 0)
        parts = text if isinstance(text, list) else [(str(text), {})]
        for t, o in parts:
            self._runs(p, t, bold=o.get('bold', bold), size=o.get('size', size), color=o.get('color', color), italic=o.get('italic', italic))
        if shade:
            put(cell._tc.get_or_add_tcPr(), el('shd', val='clear', color='auto', fill=shade), TCPR_SEQ)
        put(cell._tc.get_or_add_tcPr(), el('vAlign', val='center'), TCPR_SEQ)

    def table(self, header, rows, widths_mm, size=None, after=8, shade_first_col=False, align=None):
        size = size or self.base - 1
        t = self._table(len(rows) + (1 if header else 0), widths_mm)
        r0 = 0
        if header:
            for j, h in enumerate(header):
                self._cell(t.rows[0].cells[j], h, bold=True, size=size, shade='E7E6E6')
            r0 = 1
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                self._cell(t.rows[r0 + i].cells[j], v, size=size, bold=shade_first_col and j == 0, shade='F2F2F2' if shade_first_col and j == 0 else None,
                           align=(align[j] if align else 'start'))
        self.spacer(after)
        return t

    def kv(self, rows, widths_mm=(52, 112), size=None, after=8):
        return self.table(None, rows, widths_mm, size=size, after=after, shade_first_col=True)

    def images_row(self, items, after=6):
        """Side-by-side images with captions: items = [(path, width_mm, caption)]."""
        n = len(items)
        w = round(self.body_width_mm / n, 1)
        t = self._table(1, [w] * n, borders=False)
        for cell, (path, width, cap) in zip(t.rows[0].cells, items):
            p = cell.paragraphs[0]
            self._ppr(p, 'center', 0, 1)
            p.add_run().add_picture(str(path), width=Mm(min(width, w - 4)))
            q = cell.add_paragraph(); self._ppr(q, 'center', 0, 0)
            self._runs(q, cap, italic=True, size=self.base - 1.5, color='444444')
        self.spacer(after)
        return t

    def signatures(self, blocks, widths_mm=None, after=6):
        """blocks: list of dicts {label, name, title, org, sig (path|None), seal (path|None), date}.
        The table always spans the text width; a lone block sits at the start side."""
        n = len(blocks)
        widths_mm = list(widths_mm or [round(self.body_width_mm / n, 1)] * n)
        spare = round(self.body_width_mm - sum(widths_mm), 1)
        if spare > 5:
            widths_mm.append(spare); blocks = list(blocks) + [None]
        t = self._table(1, widths_mm, borders=False)
        for cell, b in zip(t.rows[0].cells, blocks):
            p = cell.paragraphs[0]
            self._ppr(p, 'start', 0, 1)
            if b is None:
                continue
            if b.get('label'):
                self._runs(p, b['label'], bold=True, size=self.base - 0.5)
            if b.get('sig') or b.get('seal'):
                p2 = cell.add_paragraph(); self._ppr(p2, 'start', 2, 0)
                if b.get('sig'):
                    p2.add_run().add_picture(str(b['sig']), width=Mm(b.get('sig_w', 34)))
                if b.get('seal'):
                    p2.add_run('  ')
                    p2.add_run().add_picture(str(b['seal']), width=Mm(b.get('seal_w', 26)))
            else:
                p2 = cell.add_paragraph(); self._ppr(p2, 'start', 14, 0)
            p3 = cell.add_paragraph(); self._ppr(p3, 'start', 0, 0)
            self._runs(p3, '______________________________', size=self.base - 1, color='555555')
            for key, bold in (('name', True), ('title', False), ('org', False), ('date', False)):
                if b.get(key):
                    q = cell.add_paragraph(); self._ppr(q, 'start', 0, 0)
                    self._runs(q, b[key], bold=bold, size=self.base - 1)
        self.spacer(after)
        return t

    def save(self, path):
        self.d.save(str(path))
