# Live demo script: sources

Builds `../Ferrero-Live-Demo-Script.pdf` (12 pages, A4): run sheet, pre-flight checklist, the BRD (R1–R11) on one page,
the ten demo steps with SHOW / SAY / YOU WILL SEE, likely questions and a numbers cheat sheet.

| File | What it does |
|---|---|
| `build_script.py` | All the words, the step timings and the layout. Writes `demo-script.html` and prints a speaking-time check (135 words a minute). |
| `print_pdf.py` | Prints the HTML to PDF with headless Chrome over the DevTools protocol (needs `websocket-client`, which `.venv` has). |
| `capture_dashboards.py`, `prep_images.py` | Capture app pages and embedded Superset dashboards, then crop them into `img/`. |
| `img/` | Screenshots from the running app on 12 Nov 2026 (synthetic data). The three answer shots come from the solution deck (11 Nov). |

## Rebuild

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --remote-debugging-port=9333 --user-data-dir="$env:TEMP\ferrero-print" about:blank
python -I build_script.py
..\..\..\..\.venv\Scripts\python.exe -I print_pdf.py
```

Figures that change: the Documents tiles (109 searchable, 3 of 40 scans read, 37 waiting) move as text recognition runs.
