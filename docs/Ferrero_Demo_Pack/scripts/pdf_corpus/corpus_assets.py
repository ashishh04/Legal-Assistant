"""Images and PDF post-processing for the demo corpus.

Seals and stamps are drawn with PyMuPDF (it shapes Arabic correctly; Pillow here has no raqm),
signatures, evidence photos, receipts and listing captures with Pillow. `scanify` turns a
Word-made PDF into an image-only scan; `finalize_text_pdf` stamps metadata and optional encryption.
"""
import io, math, textwrap
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance, ImageOps
from corpus_data import rng

FONTS = 'C:/Windows/Fonts/'
def font(name, size):
    return ImageFont.truetype(FONTS + name, size)

INK = {'blue': (28, 52, 140), 'purple': (88, 40, 130), 'red': (170, 30, 40), 'green': (20, 100, 60), 'black': (25, 25, 30)}

# ----------------------------------------------------------------------------- signature
def signature(path, seed, color='blue'):
    R = rng('sig', seed)
    W, H = 720, 230
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    pts, x, base = [], 40.0, H * 0.58
    for _ in range(R.randint(7, 11)):
        x += R.uniform(28, 62)
        pts.append((x, base + R.uniform(-70, 48)))
    pts = [(20, base + 10)] + pts + [(x + 60, base - R.uniform(10, 40))]
    def cr(p0, p1, p2, p3, n=24):
        for k in range(n):
            t = k / n; t2, t3 = t * t, t * t * t
            yield tuple(0.5 * ((2 * p1[i]) + (-p0[i] + p2[i]) * t + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * t2 + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * t3) for i in (0, 1))
    curve = []
    ext = [pts[0]] + pts + [pts[-1]]
    for k in range(len(ext) - 3):
        curve += list(cr(*ext[k:k + 4]))
    col = INK[color] + (235,)
    for k in range(len(curve) - 1):
        w = int(2 + 3 * abs(math.sin(k / 9.0)) + R.random())
        dr.line([curve[k], curve[k + 1]], fill=col, width=w)
    sx = R.uniform(60, 160)  # flourish underline
    dr.arc([sx, base + 18, sx + R.uniform(380, 520), base + 70 + R.uniform(0, 30)], start=190, end=350, fill=col, width=3)
    img = img.filter(ImageFilter.GaussianBlur(0.7))
    img.save(path)
    return path

# ----------------------------------------------------------------------------- seals & stamps (PyMuPDF)
def _pdf_rgb(color):
    return tuple(c / 255 for c in INK[color])

def ring_words(s, limit=31):
    """Upper-case ring text cut at a word boundary so it fits round the seal."""
    out = ''
    for w in s.split(' – ')[0].upper().split():
        if len(out) + len(w) + 1 > limit:
            break
        out = (out + ' ' + w).strip()
    return out or s.upper()[:limit]

def wrap(s, width):
    return textwrap.wrap(s, width) or [s]

def _ink_texture(img, R, strength=0.35):
    a = np.array(img).astype(np.float32)
    noise = np.random.default_rng(R.randint(0, 2**31)).uniform(1 - strength, 1.0, a.shape[:2])
    a[..., 3] *= noise
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA')

def seal(path, seed, center_lines, ring_text='', color='blue', rtl=False, star=True):
    R = rng('seal', seed)
    doc = pymupdf.open(); pg = doc.new_page(width=220, height=220)
    c = pymupdf.Point(110, 110); col = _pdf_rgb(color)
    sh = pg.new_shape()
    sh.draw_circle(c, 100); sh.finish(color=col, width=3.2)
    sh.draw_circle(c, 92); sh.finish(color=col, width=1.1)
    sh.draw_circle(c, 62); sh.finish(color=col, width=1.0)
    sh.commit()
    if ring_text:
        txt = ring_words(ring_text)
        n = len(txt); span = min(300, 9.6 * n); start = 90 + span / 2
        for k, ch in enumerate(txt):
            ang = math.radians(start - k * span / max(n - 1, 1))
            r = 70.5
            p = pymupdf.Point(c.x + r * math.cos(ang), c.y - r * math.sin(ang))
            rot = math.degrees(ang) - 90
            pg.insert_text(p, ch, fontsize=10.5, fontname='arialbd', fontfile=FONTS + 'arialbd.ttf', color=col, morph=(p, pymupdf.Matrix(rot)))
    if star and ring_text:
        for ang in (270 - 6, 270 + 6):
            a = math.radians(ang); p = pymupdf.Point(c.x + 74 * math.cos(a), c.y - 74 * math.sin(a))
            pg.insert_text(p + (-3.5, 4), '*', fontsize=12, fontname='arialbd', fontfile=FONTS + 'arialbd.ttf', color=col)
    hexcol = '#%02x%02x%02x' % INK[color]
    fs = 10 if len(center_lines) < 4 else 8.5
    if rtl:
        fs += 1.5
    html = ''.join(f'<p style="margin:0;line-height:1.2">{ln}</p>' for ln in center_lines)
    css = f'* {{font-family: sans-serif; color: {hexcol}; text-align: center; font-weight: bold;}} p {{font-size: {fs}pt;}}'
    text_h = len(center_lines) * fs * 1.35
    box = pymupdf.Rect(50, 110 - text_h / 2 - 2, 170, 110 + text_h / 2 + 14)
    if rtl:
        html = f'<div dir="rtl">{html}</div>'
    pg.insert_htmlbox(box, html, css=css)
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=True)
    img = Image.frombytes('RGBA', (pix.width, pix.height), pix.samples)
    img = _ink_texture(img, R).rotate(R.uniform(-18, 18), resample=Image.BICUBIC, expand=True)
    img.save(path)
    return path

def stamp(path, seed, lines, color='red', rtl=False):
    """Rectangular office stamp (RECEIVED / FILED / وارد)."""
    R = rng('stamp', seed)
    first, rest = lines[0], lines[1:]
    H = 34 + 12.5 * len(rest) + 16
    doc = pymupdf.open(); pg = doc.new_page(width=240, height=H)
    col = _pdf_rgb(color)
    sh = pg.new_shape()
    sh.draw_rect(pymupdf.Rect(6, 6, 234, H - 6), radius=0.08); sh.finish(color=col, width=2.6)
    sh.draw_rect(pymupdf.Rect(11, 11, 229, H - 11), radius=0.06); sh.finish(color=col, width=0.8)
    sh.commit()
    hexcol = '#%02x%02x%02x' % INK[color]
    spacing = '' if rtl else 'letter-spacing:1px;'   # letter-spacing breaks Arabic joining
    html = f'<p style="font-size:17pt;margin:0;{spacing}">{first}</p>' + ''.join(f'<p style="font-size:8.5pt;margin:0">{x}</p>' for x in rest)
    if rtl:
        html = f'<div dir="rtl">{html}</div>'
    pg.insert_htmlbox(pymupdf.Rect(14, 13, 226, H - 8), html, css=f'* {{font-family: sans-serif; font-weight: bold; color: {hexcol}; text-align: center;}}')
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=True)
    img = Image.frombytes('RGBA', (pix.width, pix.height), pix.samples)
    img = _ink_texture(img, R, 0.45).rotate(R.uniform(-9, 9), resample=Image.BICUBIC, expand=True)
    img.save(path)
    return path

# ----------------------------------------------------------------------------- product photo / receipt / captures (Pillow)
PALETTE = {'VELORA': ((96, 52, 28), (250, 246, 238)), 'CRISPINO': ((196, 36, 44), (252, 240, 222)), 'DOLCETTA': ((150, 110, 40), (60, 30, 20)),
           'MINTIQ': ((40, 160, 130), (235, 250, 245)), 'PICCOLINI': ((240, 120, 20), (255, 255, 255)), 'AURELIA': ((200, 160, 60), (90, 50, 20))}

def _product(dr, img, mark, product, box, R, counterfeit=True):
    x0, y0, x1, y1 = box
    main, second = PALETTE.get(mark, ((120, 80, 40), (240, 240, 240)))
    if counterfeit:  # slightly off brand colour
        main = tuple(clamp_c(v + R.randint(-25, 25)) for v in main)
    w, h = x1 - x0, y1 - y0
    shadow = Image.new('L', img.size, 0); sd = ImageDraw.Draw(shadow)
    sd.ellipse([x0 + w * 0.05, y1 - h * 0.06, x1 - w * 0.05, y1 + h * 0.08], fill=120)
    img.paste((40, 40, 40), mask=shadow.filter(ImageFilter.GaussianBlur(18)))
    size = max(12, int(h * 0.16))
    while size > 10 and font('arialbd.ttf', size).getlength(mark) > w * 0.72:
        size -= 2
    f = font('arialbd.ttf', size)
    if product == 'Hazelnut spread':
        dr.rounded_rectangle([x0 + w * .15, y0 + h * .05, x1 - w * .15, y0 + h * .2], 12, fill=main)
        dr.rounded_rectangle([x0 + w * .1, y0 + h * .18, x1 - w * .1, y1], 28, fill=(110, 62, 30))
        dr.rectangle([x0 + w * .1, y0 + h * .38, x1 - w * .1, y0 + h * .78], fill=second)
        dr.text(((x0 + x1) / 2, y0 + h * .58), mark, fill=main, font=f, anchor='mm')
    elif product == 'Wafer bars':
        for k in range(3):
            dy = k * h * .22
            dr.rounded_rectangle([x0, y0 + h * .2 + dy, x1, y0 + h * .38 + dy], 8, fill=main if k % 2 == 0 else second, outline=(90, 20, 20))
        dr.text(((x0 + x1) / 2, y0 + h * .29), mark, fill=second, font=f, anchor='mm')
    elif product == 'Boxed pralines':
        dr.rectangle([x0, y0 + h * .15, x1, y1 - h * .05], fill=second, outline=main, width=6)
        for i in range(4):
            for j in range(2):
                cx, cy = x0 + w * (.2 + i * .2), y0 + h * (.45 + j * .22)
                dr.ellipse([cx - w * .07, cy - w * .07, cx + w * .07, cy + w * .07], fill=main)
        dr.text(((x0 + x1) / 2, y0 + h * .27), mark, fill=main, font=f, anchor='mm')
    elif product == 'Mints and chewing gum':
        dr.rounded_rectangle([x0 + w * .15, y0 + h * .25, x1 - w * .15, y1 - h * .1], 24, fill=main, outline=(20, 90, 70), width=5)
        dr.text(((x0 + x1) / 2, (y0 + y1) / 2 + h * .07), mark, fill=second, font=f, anchor='mm')
    elif product.startswith('Children'):
        for k in range(3):
            cx = x0 + w * (.2 + k * .3); cy = y0 + h * .6
            dr.ellipse([cx - w * .13, cy - h * .25, cx + w * .13, cy + h * .25], fill=second if k % 2 else main, outline=(150, 70, 10), width=4)
        dr.text(((x0 + x1) / 2, y0 + h * .2), mark, fill=main, font=f, anchor='mm')
    else:
        dr.rectangle([x0, y0 + h * .25, x1, y1 - h * .02], fill=(235, 235, 230), outline=(160, 160, 160), width=3)
        for i in range(4):
            for j in range(2):
                cx, cy = x0 + w * (.18 + i * .21), y0 + h * (.5 + j * .24)
                dr.ellipse([cx - w * .08, cy - w * .08, cx + w * .08, cy + w * .08], fill=main, outline=(150, 115, 30), width=3)
        dr.text(((x0 + x1) / 2, y0 + h * .15), mark, fill=main, font=f, anchor='mm')

def clamp_c(v):
    return max(0, min(255, v))

def product_photo(path, seed, mark, product, tag_lines):
    R = rng('photo', seed)
    W, H = 960, 640
    top, bot = (R.randint(150, 200),) * 3, (R.randint(95, 140),) * 3
    grad = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(top) * (1 - grad) + np.array(bot) * grad) * np.ones((H, W, 3))
    arr += np.random.default_rng(R.randint(0, 2**31)).normal(0, 4, arr.shape)
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGB')
    dr = ImageDraw.Draw(img)
    _product(dr, img, mark, product, (W * .22, H * .14, W * .68, H * .82), R)
    tx, ty = W * .70, H * .55
    dr.rectangle([tx, ty, tx + 250, ty + 22 + 24 * len(tag_lines)], fill=(252, 252, 248), outline=(30, 30, 30), width=2)
    for k, ln in enumerate(tag_lines):
        dr.text((tx + 10, ty + 10 + 24 * k), ln, fill=(20, 20, 20), font=font('arialbd.ttf' if k == 0 else 'arial.ttf', 19 if k == 0 else 16))
    for k in range(21):  # scale bar
        x = W * .08 + k * 26
        dr.line([x, H * .92, x, H * .92 - (16 if k % 5 == 0 else 8)], fill=(250, 250, 250), width=2)
    dr.line([W * .08, H * .92, W * .08 + 520, H * .92], fill=(250, 250, 250), width=2)
    dr.text((W * .08, H * .935), '0          5 cm', fill=(250, 250, 250), font=font('arial.ttf', 15))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img = ImageEnhance.Color(img).enhance(R.uniform(0.85, 1.1))
    img.save(path, 'JPEG', quality=80)
    return path

def receipt(path, seed, shop, city, lines, currency, vat, when, receipt_no, pay):
    R = rng('receipt', seed)
    mono, monob = font('consola.ttf', 22), font('consolab.ttf', 24)
    rows = [(shop.upper()[:30], monob), (city, mono)]
    if vat:
        rows.append((f'TRN {R.randint(100000000000000, 100999999999999)}', mono))
    rows += [('-' * 32, mono), (f'Date {when:%d/%m/%Y}  {R.randint(10, 21)}:{R.randint(10, 59)}', mono), (f'Receipt #{receipt_no}  Till 0{R.randint(1, 4)}', mono), ('-' * 32, mono)]
    sub = 0
    for desc, qty, price in lines:
        rows.append((desc[:32], mono)); rows.append((f'  {qty} x {price:,.2f}'.ljust(20) + f'{qty * price:>12,.2f}', mono)); sub += qty * price
    rows.append(('-' * 32, mono))
    if vat:
        rows.append((f'Subtotal'.ljust(20) + f'{sub / (1 + vat / 100):>12,.2f}', mono))
        rows.append((f'VAT {vat}%'.ljust(20) + f'{sub - sub / (1 + vat / 100):>12,.2f}', mono))
    rows.append((f'TOTAL {currency}'.ljust(20) + f'{sub:>12,.2f}', monob))
    rows += [(pay, mono), ('-' * 32, mono), ('THANK YOU - NO REFUNDS', mono), ('GOODS SOLD ARE NOT RETURNABLE', mono)]
    pw, ph = 470, 60 + 30 * len(rows)
    paper = Image.new('RGB', (pw, ph), (250, 249, 244))
    dp = ImageDraw.Draw(paper)
    for k, (t, f) in enumerate(rows):
        dp.text((pw / 2, 34 + 30 * k), t, fill=(35, 35, 40), font=f, anchor='mm')
    paper = paper.rotate(R.uniform(-3, 3), expand=True, fillcolor=(70, 70, 75))
    canvas = Image.new('RGB', (paper.width + 120, paper.height + 120), (70, 70, 75))
    canvas.paste(paper, (60, 60))
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.5))
    canvas.save(path, 'JPEG', quality=78)
    return path

def _stars(dr, x, y, rating, f):
    dr.text((x, y), '★' * int(rating) + '☆' * (5 - int(rating)) + f'  {rating:.1f}', fill=(230, 160, 20), font=f)

def listing_capture(path, seed, kind, d):
    """kind: marketplace | app | domain. d: dict with mark, product, title, price, old_price, seller, store, developer, downloads, domain, when, currency."""
    R = rng('cap', seed)
    W, H = 1100, 680
    img = Image.new('RGB', (W, H), (255, 255, 255)); dr = ImageDraw.Draw(img)
    fb, fr, fs = font('segoeuib.ttf', 26), font('segoeui.ttf', 20), font('segoeui.ttf', 16)
    sym = font('seguisym.ttf', 22)
    dr.rectangle([0, 0, W, 54], fill=(32, 33, 36))
    dr.text((18, 14), f'Evidence capture · {d["when"]:%d/%m/%Y} {R.randint(9, 20)}:{R.randint(10, 59)} GST · {d.get("where", "")}', fill=(235, 235, 235), font=fs)
    if kind == 'marketplace':
        dr.rectangle([0, 54, W, 120], fill=(250, 196, 40))
        dr.text((24, 70), d['store'], fill=(20, 20, 20), font=fb)
        dr.rounded_rectangle([300, 70, W - 40, 104], 8, fill=(255, 255, 255))
        dr.text((316, 76), f'search: {d["mark"].lower()}', fill=(120, 120, 120), font=fr)
        sub = Image.new('RGB', (420, 420), (245, 245, 245)); sd = ImageDraw.Draw(sub)
        _product(sd, sub, d['mark'], d['product'], (60, 60, 360, 380), R)
        img.paste(sub, (40, 150))
        for k, ln in enumerate(textwrap.wrap(d['title'], 40)[:2]):
            dr.text((500, 160 + 40 * k), ln, fill=(20, 20, 20), font=fb)
        _stars(dr, 500, 250, R.choice([3.9, 4.1, 4.3, 4.6]), sym)
        dr.text((500, 300), f'{d["currency"]} {d["price"]:,}', fill=(180, 20, 20), font=font('segoeuib.ttf', 34))
        dr.text((500, 350), f'was {d["currency"]} {d["old_price"]:,}  ·  {R.randint(35, 62)}% off  ·  {R.randint(20, 400)} sold', fill=(110, 110, 110), font=fr)
        dr.text((500, 400), f'Sold by: {d["seller"]}', fill=(30, 80, 160), font=fr)
        dr.text((500, 432), f'Listing ID {d["listing_id"]}  ·  Ships from {d.get("city", "")}', fill=(90, 90, 90), font=fs)
        dr.rounded_rectangle([500, 490, 760, 545], 10, fill=(250, 196, 40)); dr.text((630, 517), 'Add to cart', fill=(20, 20, 20), font=fb, anchor='mm')
    elif kind == 'app':
        dr.rectangle([0, 54, W, 110], fill=(245, 245, 247))
        dr.text((24, 68), d['store'], fill=(60, 60, 60), font=fb)
        main = PALETTE.get(d['mark'], ((120, 80, 40), (240, 240, 240)))[0]
        dr.rounded_rectangle([40, 140, 240, 340], 40, fill=main)
        dr.text((140, 240), d['mark'][0], fill=(255, 255, 255), font=font('arialbd.ttf', 120), anchor='mm')
        dr.text((280, 150), d['title'], fill=(20, 20, 20), font=font('segoeuib.ttf', 34))
        dr.text((280, 200), d['developer'], fill=(20, 120, 60), font=fr)
        _stars(dr, 280, 240, R.choice([3.8, 4.0, 4.2, 4.4]), sym)
        dr.text((280, 280), f'{d["downloads"]} downloads  ·  Rated 3+  ·  Contains ads', fill=(90, 90, 90), font=fr)
        dr.rounded_rectangle([280, 320, 480, 370], 10, fill=(1, 135, 95)); dr.text((380, 345), 'Install', fill=(255, 255, 255), font=fb, anchor='mm')
        for k in range(4):
            x = 40 + k * 260
            dr.rounded_rectangle([x, 410, x + 230, 660], 18, fill=(30, 30, 30))
            dr.rectangle([x + 12, 430, x + 218, 640], fill=main if k % 2 == 0 else (250, 230, 200))
            dr.text((x + 115, 535), d['mark'], fill=(255, 255, 255) if k % 2 == 0 else main, font=font('arialbd.ttf', 30), anchor='mm')
    else:
        dr.rectangle([0, 54, W, 96], fill=(236, 236, 236))
        dr.rounded_rectangle([20, 62, W - 20, 90], 12, fill=(255, 255, 255))
        dr.text((40, 64), d['domain'], fill=(60, 60, 60), font=fr)
        main = PALETTE.get(d['mark'], ((120, 80, 40), (240, 240, 240)))[0]
        dr.rectangle([0, 96, W, 230], fill=main)
        dr.text((W / 2, 140), f'{d["mark"]} OUTLET', fill=(255, 255, 255), font=font('arialbd.ttf', 48), anchor='mm')
        dr.text((W / 2, 195), 'Official-looking prices · up to 60% off · cash on delivery', fill=(255, 255, 255), font=fr, anchor='mm')
        for k in range(4):
            x = 40 + k * 262
            sub = Image.new('RGB', (230, 230), (248, 248, 248)); sd = ImageDraw.Draw(sub)
            _product(sd, sub, d['mark'], d['product'], (30, 30, 200, 205), R)
            img.paste(sub, (x, 260))
            dr.text((x + 8, 500), f'{d["mark"]} {d["product"][:16]}', fill=(30, 30, 30), font=fs)
            dr.text((x + 8, 526), f'{d["currency"]} {int(d["price"] * (1 + 0.15 * k)):,}', fill=(180, 20, 20), font=fr)
        dr.text((40, 620), f'© {d["when"].year} {d["domain"]} · all rights reserved', fill=(120, 120, 120), font=fs)
    img = img.convert('RGB')
    img.save(path, 'PNG', optimize=True)
    return path

# ----------------------------------------------------------------------------- scans
def pdfdate(day, hh=10, mm=30, tz='+04\'00\''):
    return f"D:{day:%Y%m%d}{hh:02d}{mm:02d}00{tz}"

def _degrade(img, quality, R, page_no):
    g = np.random.default_rng(R.randint(0, 2**31))
    color = R.random() < 0.4
    if not color:
        img = ImageOps.grayscale(img).convert('RGB')
    params = {'good': dict(rot=0.7, blur=0.35, noise=3.5, specks=60, contrast=1.04, jpeg=80),
              'fair': dict(rot=1.3, blur=0.7, noise=7, specks=220, contrast=0.95, jpeg=68),
              'poor': dict(rot=2.6, blur=1.25, noise=15, specks=900, contrast=0.78, jpeg=42)}[quality]
    if quality == 'poor':  # resolution loss, washed out toner
        w, h = img.size
        img = img.resize((int(w * 0.55), int(h * 0.55)), Image.BILINEAR).resize((w, h), Image.BILINEAR)
        img = ImageEnhance.Brightness(img).enhance(R.uniform(1.05, 1.15))
    angle = R.uniform(-params['rot'], params['rot'])
    paper = (R.randint(238, 252), R.randint(236, 250), R.randint(226, 244)) if color else (R.randint(236, 250),) * 3
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=paper, translate=(R.randint(-14, 14), R.randint(-10, 10)))
    a = np.array(img).astype(np.float32)
    a = a / 255.0 * (np.array(paper, dtype=np.float32) / 255.0) * 255.0       # paper tone
    a += g.normal(0, params['noise'], a.shape[:2])[..., None]
    h, w = a.shape[:2]
    ys, xs = g.integers(0, h, params['specks']), g.integers(0, w, params['specks'])
    for y, x in zip(ys, xs):
        r = int(g.integers(1, 3)); v = float(g.uniform(40, 150))
        a[max(0, y - r):y + r, max(0, x - r):x + r] = v
    if R.random() < 0.35:   # scanner edge shadow
        edge = int(w * R.uniform(0.01, 0.03)); ramp = np.linspace(0.55, 1, edge)[None, :, None]
        if R.random() < 0.5:
            a[:, :edge] *= ramp
        else:
            a[:, w - edge:] *= ramp[:, ::-1]
    if R.random() < 0.25:   # punch holes
        for fy in (0.32, 0.68):
            cy, cx, rr = int(h * fy), int(w * 0.035), int(w * 0.012)
            yy, xx = np.ogrid[:h, :w]
            a[(yy - cy) ** 2 + (xx - cx) ** 2 <= rr * rr] = 60
    if R.random() < 0.3:    # fold line
        y = int(h * R.uniform(0.45, 0.55)); a[y:y + 2] *= 0.86
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGB')
    img = img.filter(ImageFilter.GaussianBlur(params['blur']))
    img = ImageEnhance.Contrast(img).enhance(params['contrast'])
    if not color:
        img = ImageOps.grayscale(img)
    return img, params['jpeg']

def scanify(src_pdf, out_pdf, quality, seed, when, flagged_pages=0):
    R = rng('scan', seed)
    src = pymupdf.open(src_pdf); out = pymupdf.open()
    dpi = {'good': 200, 'fair': 170, 'poor': 130}[quality]
    for i, page in enumerate(src):
        q = quality
        if flagged_pages and i in range(src.page_count - flagged_pages, src.page_count):
            q = 'poor' if quality != 'poor' else q
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB)
        img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        img, jq = _degrade(img, q, R, i)
        buf = io.BytesIO(); img.save(buf, 'JPEG', quality=jq, optimize=True)
        p = out.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, stream=buf.getvalue())
    stamp_ = pdfdate(when, R.randint(8, 17), R.randint(0, 59))
    out.set_metadata({'creator': 'Scan to PDF', 'producer': 'Multifunction printer – scan to folder', 'creationDate': stamp_, 'modDate': stamp_, 'title': '', 'author': ''})
    out.save(out_pdf, garbage=4, deflate=True)
    n = out.page_count; out.close(); src.close()
    return n

def finalize_text_pdf(src_pdf, out_pdf, meta, when, password=None):
    doc = pymupdf.open(src_pdf)
    stamp_ = pdfdate(when, 10 + (hash(meta.get('title', '')) % 7), 15)
    m = doc.metadata
    m.update({k: v for k, v in meta.items() if v is not None})
    m['creationDate'] = m['modDate'] = stamp_
    doc.set_metadata(m)
    kw = dict(garbage=3, deflate=True)
    if password:
        kw.update(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw=password + '-owner', user_pw=password,
                  permissions=pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_ACCESSIBILITY)
    doc.save(out_pdf, **kw)
    n = doc.page_count; doc.close()
    return n

def encrypt_pdf(src_pdf, out_pdf, password):
    doc = pymupdf.open(src_pdf)
    doc.save(out_pdf, garbage=3, deflate=True, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw=password + '-owner', user_pw=password,
             permissions=pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_ACCESSIBILITY)
    doc.close()
