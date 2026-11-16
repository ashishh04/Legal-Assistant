# Solution Approach deck: sources

These files build `../Ferrero-Solution-Approach.pptx` (23 slides, Intertec template, speaker notes on every slide).
The structure follows the Amicorp solution-approach deck; the content is the current Ferrero build.

| File | What it does |
|---|---|
| `build_deck.py` | Builds the deck with python-pptx on the Intertec EPM template, which supplies the masters, layouts, logo and footer. Slide content (titles, cards, diagrams, the plan) lives in this file. |
| `presenter-script.md` | The talk track. Each `## Slide N` section becomes that slide's speaker notes. Edit the notes here, not in PowerPoint. |
| `prep_screens.py` | Crops the raw app screenshots into `screens/*.jpg`. |
| `capture_screens.py` | Captures raw screenshots of the running app over the Chrome DevTools Protocol (needs `websocket-client`, which `.venv` has, and Chrome started with `--remote-debugging-port=9333`). Assistant shots make live, billed model calls. |
| `export-slides.ps1` | Renders the slides to PNG with PowerPoint, for visual checks. |
| `assets/` | Icons from the Intertec decks (white `_w` for magenta circles, pink `_p` for light circles). |
| `screens/` | The cropped app screenshots the deck uses (synthetic data). |

## Rebuild

Run in PowerShell from this folder, with the deck closed in PowerPoint:

```powershell
python -I build_deck.py "$env:USERPROFILE\Downloads\Intertec-EPM.pptx" assets screens presenter-script.md ..\Ferrero-Solution-Approach.pptx
.\export-slides.ps1 -Deck (Resolve-Path ..\Ferrero-Solution-Approach.pptx).Path -OutDir "$env:TEMP\ferrero-png" -Width 1600
```

## Figures that change with the build

- Slides 15 and 21 quote the document sync as of 11 Nov 2026: 150 files, 106 searchable, 685 passages, 40 scans
  awaiting OCR, 4 password-protected. Update them (and the notes) when OCR lands and the index is rebuilt.
- Slide 21's "Next" list and slide 18's "In the demo today" column describe the build on 11 Nov 2026.
- Headings use Poppins, as the template does; PowerPoint substitutes a narrower font where Poppins is not
  installed, so keep headings to about 40 characters.
