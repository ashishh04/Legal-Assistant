"""Crop the raw app screenshots (3200 x 2000, captured at 2x) into the images the deck uses.

    python -I prep_screens.py <raw_dir> <out_dir>

Crop boxes are in raw pixels. Output is JPEG, at most 2400 px wide, so the deck stays small.
"""
import os
import sys

from PIL import Image

RAW, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

CROPS = {
    # name: (source file, (left, top, right, bottom))
    "overview": ("overview.png", (0, 0, 3200, 1950)),        # KPI row and the first two charts
    "dashboard": ("dash-d1.png", (0, 0, 3200, 1960)),        # Superset D1 embedded in the Dashboards page
    "case": ("case-428.png", (0, 0, 3200, 1820)),             # case page down to the documents card
    "documents": ("documents.png", (0, 0, 3200, 1920)),       # document library with its status tiles
    "answer-cited": ("ask-damages.png", (608, 181, 2480, 1640)),   # chat card: answer and the first source
    "answer-access": ("ask-access.png", (608, 181, 3120, 800)),    # refusal plus the "Asking as" panel
    "answer-arabic": ("ask-arabic2.png", (608, 181, 2480, 1575)),  # Arabic question and answer, clauses 1 to 3
}

for name, (src, box) in CROPS.items():
    im = Image.open(os.path.join(RAW, src)).convert("RGB").crop(box)
    if im.width > 2400:
        im = im.resize((2400, round(im.height * 2400 / im.width)), Image.LANCZOS)
    path = os.path.join(OUT, name + ".jpg")
    im.save(path, quality=90, optimize=True)
    print(f"{path}  {im.width}x{im.height}  aspect {im.width / im.height:.3f}")
