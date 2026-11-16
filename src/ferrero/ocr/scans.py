"""Page images of image-only PDFs (scans), ready for text recognition.

A scanner's "scan to PDF" stores each page as one image covering the page. JPEG pages are passed on exactly as
stored (no re-encoding, so no quality loss); other encodings and rotated pages need Pillow (OCR environment).
"""
from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.generic import IndirectObject


class ScanError(Exception):
    """The PDF's pages cannot be turned into images for recognition."""


def _images(resources) -> list:
    """Image XObjects on a page, including those wrapped in form XObjects (some scanners do that)."""
    found = []
    xobjects = resources.get("/XObject") if resources else None
    if xobjects is None:
        return found
    xobjects = xobjects.get_object()
    for name in xobjects:
        obj = xobjects[name]
        obj = obj.get_object() if isinstance(obj, IndirectObject) else obj
        subtype = obj.get("/Subtype")
        if subtype == "/Image":
            found.append(obj)
        elif subtype == "/Form":
            found += _images(obj.get("/Resources"))
    return found


def _filters(obj) -> list[str]:
    f = obj.get("/Filter")
    if f is None:
        return []
    return [str(x) for x in f] if isinstance(f, list) else [str(f)]


def page_images(reader: PdfReader) -> list[bytes]:
    """One encoded image (JPEG or PNG bytes) per page, in page order."""
    out: list[bytes] = []
    for number, page in enumerate(reader.pages, start=1):
        images = _images(page.get("/Resources"))
        if not images:
            raise ScanError(f"Page {number} has no image to recognise")
        # The page image is the largest one (a few scanners add a small logo or stamp next to it).
        obj = max(images, key=lambda o: int(o.get("/Width", 0)) * int(o.get("/Height", 0)))
        rotate = int(page.get("/Rotate", 0) or 0) % 360
        if _filters(obj) == ["/DCTDecode"] and rotate == 0:
            out.append(obj.get_data())  # pypdf leaves JPEG data encoded: the stored JPEG file, byte for byte
            continue
        out.append(_via_pillow(page, rotate, number))
    return out


def _via_pillow(page, rotate: int, number: int) -> bytes:
    """Decode the page's largest image with Pillow (other encodings, rotated pages) and re-encode it losslessly."""
    try:
        from PIL import Image  # noqa: F401  (pypdf needs Pillow to decode images)
    except ImportError:
        raise ScanError(f"Page {number}: decoding this kind of page image needs Pillow (the OCR environment)") from None
    decoded = [im.image for im in page.images]
    if not decoded:
        raise ScanError(f"Page {number} has no image to recognise")
    image = max(decoded, key=lambda im: im.width * im.height)
    if rotate:
        image = image.rotate(-rotate, expand=True)  # /Rotate is clockwise; PIL rotates counter-clockwise
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "PNG")
    return buf.getvalue()
