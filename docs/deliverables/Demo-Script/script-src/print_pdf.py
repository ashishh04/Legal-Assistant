"""Prints demo-script.html to PDF with headless Chrome over the DevTools protocol.

Start Chrome first, for example:
    chrome --headless=new --remote-debugging-port=9333 --user-data-dir=%TEMP%\\ferrero-print about:blank
then:
    python print_pdf.py [output.pdf]
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

import websocket

HERE = Path(__file__).resolve().parent
SRC = HERE / "demo-script.html"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "Ferrero-Live-Demo-Script.pdf"

FOOTER = """
<div style="width:100%; font-family:'Segoe UI',sans-serif; font-size:7px; color:#7a7d85; padding:0 13mm;
            display:flex; justify-content:space-between;">
  <span>Ferrero Case Intelligence &middot; Live demo script &middot; Internal, not for the client &middot; 12 Nov 2026</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>"""

targets = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
page = next(t for t in targets if t.get("type") == "page")
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=120, suppress_origin=True)
_id = 0


def cdp(method, **params):
    global _id
    _id += 1
    ws.send(json.dumps({"id": _id, "method": method, "params": params}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id:
            if "error" in msg:
                raise RuntimeError(f"{method}: {msg['error']}")
            return msg.get("result", {})


cdp("Page.enable")
cdp("Emulation.clearDeviceMetricsOverride")
cdp("Page.navigate", url=SRC.as_uri())
time.sleep(2.5)  # local file with local images
pdf = cdp("Page.printToPDF", printBackground=True, preferCSSPageSize=True, displayHeaderFooter=True,
          headerTemplate="<span></span>", footerTemplate=FOOTER, generateDocumentOutline=True, generateTaggedPDF=True)
OUT.write_bytes(base64.b64decode(pdf["data"]))
ws.close()
print("wrote", OUT, f"{OUT.stat().st_size / 1024:.0f} KB")
