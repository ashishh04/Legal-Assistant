"""Draws the registered-mark specimens shown in the visual trademark comparison (src/ferrero/web/marks/MK-0n.png).

The marks are the pack's sample marks (dim_mark.csv), so these are representative word marks, not real registrations.
Replace a file with the specimen from the registration certificate to compare against the registered form itself.

    python scripts/make_mark_specimens.py          (needs Pillow; uses fonts that ship with Windows)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "src" / "ferrero" / "web" / "marks"
W, H = 1200, 760
FONTS = Path("C:/Windows/Fonts")


def font(names: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        try:
            return ImageFont.truetype(str(FONTS / name), size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), (255, 255, 255))
    return img, ImageDraw.Draw(img)


def centred(d: ImageDraw.ImageDraw, y: int, text: str, f: ImageFont.FreeTypeFont, fill, spacing: int = 0) -> None:
    if spacing:
        widths = [d.textlength(ch, font=f) for ch in text]
        x = (W - (sum(widths) + spacing * (len(text) - 1))) / 2
        for ch, w in zip(text, widths):
            d.text((x, y), ch, font=f, fill=fill, anchor="lm")
            x += w + spacing
    else:
        d.text((W / 2, y), text, font=f, fill=fill, anchor="mm")


def velora() -> Image.Image:
    """Hazelnut spread: a cream oval label with a gold border, the name in deep red."""
    img, d = canvas()
    d.ellipse((150, 120, W - 150, H - 120), fill=(250, 240, 214), outline=(201, 160, 72), width=14)
    d.ellipse((178, 148, W - 178, H - 148), outline=(201, 160, 72), width=3)
    centred(d, H // 2 - 30, "VELORA", font(("seguibl.ttf", "ariblk.ttf", "segoeuib.ttf"), 170), (150, 26, 30))
    centred(d, H // 2 + 95, "HAZELNUT COCOA SPREAD", font(("segoeuib.ttf", "arialbd.ttf"), 40), (96, 62, 40), spacing=6)
    return img


def crispino() -> Image.Image:
    """Wafer bars: a bold slanted word on a wafer-pattern band."""
    img, d = canvas()
    d.rounded_rectangle((110, 230, W - 110, 530), radius=40, fill=(214, 64, 36))
    for x in range(140, W - 140, 46):  # wafer grid
        d.line([(x, 250), (x, 510)], fill=(232, 112, 72), width=3)
    centred(d, 380, "CRISPINO", font(("ariblk.ttf", "seguibl.ttf"), 150), (255, 247, 230))
    centred(d, 610, "CRISPY WAFER", font(("segoeuib.ttf", "arialbd.ttf"), 42), (120, 40, 24), spacing=8)
    return img


def dolcetta() -> Image.Image:
    """Boxed pralines: an elegant italic serif in burgundy over a gold rule."""
    img, d = canvas()
    centred(d, 330, "Dolcetta", font(("georgiaz.ttf", "palabi.ttf", "georgiab.ttf"), 190), (110, 22, 44))
    d.line([(330, 470), (W - 330, 470)], fill=(190, 150, 70), width=6)
    centred(d, 540, "FINE PRALINES", font(("georgia.ttf", "pala.ttf"), 44), (110, 22, 44), spacing=10)
    return img


def mintiq() -> Image.Image:
    """Mints and gum: a rounded green word."""
    img, d = canvas()
    centred(d, 360, "mintiq", font(("seguibl.ttf", "segoeuib.ttf", "arialbd.ttf"), 210), (14, 140, 108))
    centred(d, 540, "FRESH MINTS", font(("segoeuib.ttf", "arialbd.ttf"), 42), (14, 110, 88), spacing=10)
    return img


def piccolini() -> Image.Image:
    """Children's treats: playful letters in alternating colours."""
    img, d = canvas()
    f = font(("seguibl.ttf", "ariblk.ttf"), 150)
    word, colours = "PICCOLINI", [(232, 64, 52), (250, 176, 34), (40, 120, 220), (60, 170, 90)]
    widths = [d.textlength(ch, font=f) for ch in word]
    x = (W - sum(widths) - 6 * (len(word) - 1)) / 2
    for i, (ch, w) in enumerate(zip(word, widths)):
        d.text((x, 360 + (-14 if i % 2 else 14)), ch, font=f, fill=colours[i % 4], anchor="lm")
        x += w + 6
    centred(d, 560, "CHOCOLATE SURPRISE", font(("segoeuib.ttf", "arialbd.ttf"), 40), (60, 60, 80), spacing=8)
    return img


def aurelia() -> Image.Image:
    """Gold-wrapped chocolates: spaced gold capitals in a fine frame."""
    img, d = canvas()
    d.rectangle((150, 170, W - 150, H - 170), outline=(186, 146, 64), width=4)
    d.rectangle((166, 186, W - 166, H - 186), outline=(186, 146, 64), width=1)
    centred(d, 350, "AURELIA", font(("georgiab.ttf", "palab.ttf"), 140), (170, 128, 48), spacing=14)
    centred(d, 470, "HAZELNUT PRALINES", font(("georgia.ttf", "pala.ttf"), 38), (120, 92, 40), spacing=12)
    return img


SPECIMENS = {"MK-01": velora, "MK-02": crispino, "MK-03": dolcetta, "MK-04": mintiq, "MK-05": piccolini,
             "MK-06": aurelia}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for mark_id, draw in SPECIMENS.items():
        draw().save(OUT / f"{mark_id}.png", optimize=True)
        print("wrote", OUT / f"{mark_id}.png")
