"""Crop the raw app screenshots into JPEGs for the demo script (coordinates in original 3200x2000 pixels)."""
import sys
from pathlib import Path
from PIL import Image

raw, out, deck = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
S = 1.6  # displayed -> original
def box(x0, y0, x1, y1):  # displayed coords (2000x1250) -> original
    return tuple(int(v * S) for v in (x0, y0, x1, y1))
JOBS = {
    "overview":        ("overview.png",        box(370, 105, 1945, 785)),
    "dash-d1":         ("dash-d1b.png",        box(370, 245, 1945, 1250)),
    "dash-d2":         ("dash-d2.png",         box(370, 245, 1945, 1110)),
    "case428":         ("case428.png",         box(370, 105, 1945, 1125)),
    "dash-ds1":        ("dash-ds1.png",        box(370, 245, 1945, 905)),
    "overview-omar":   ("overview-omar.png",   box(370, 105, 1945, 785)),
    "dash-d1-omar":    ("dash-d1-omar.png",    box(370, 245, 1945, 860)),
    "case428-omar":    ("case428-omar.png",    box(790, 130, 1540, 540)),
    "documents":       ("documents.png",       box(370, 105, 1945, 1010)),
    "docview-ar-scan": ("docview-ar-scan.png", box(370, 105, 1945, 1250)),
    "docview-flagged": ("docview-flagged.png", box(370, 105, 1945, 720)),
    "persona":         ("overview-omar.png",   box(0, 1085, 330, 1250)),
}
for name, (src, b) in JOBS.items():
    p = raw / src
    if not p.exists():
        print("missing", p); continue
    im = Image.open(p).convert("RGB").crop(b)
    if im.width > 1700:
        im = im.resize((1700, round(im.height * 1700 / im.width)), Image.LANCZOS)
    im.save(out / f"{name}.jpg", quality=84, optimize=True, progressive=True)
    print(name, im.size)
for name in ["answer-cited", "answer-arabic", "answer-access"]:
    im = Image.open(deck / f"{name}.jpg").convert("RGB")
    if im.width > 1700:
        im = im.resize((1700, round(im.height * 1700 / im.width)), Image.LANCZOS)
    im.save(out / f"{name}.jpg", quality=84, optimize=True, progressive=True)
    print(name, im.size)
