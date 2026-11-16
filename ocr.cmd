@echo off
rem Ferrero text recognition: reads scanned PDFs with Baidu's Unlimited-OCR-2 and makes them searchable.
rem Safe to stop (close the window or Ctrl+C) and start again: finished pages are kept.
rem Options are passed on, e.g.  ocr.cmd status   or   ocr.cmd --limit 5
cd /d "%~dp0"

if not exist ".venv-ocr\Scripts\python.exe" (
  echo Setting up the text-recognition environment - first run only, about 1 GB...
  python -m venv .venv-ocr || goto :error
  ".venv-ocr\Scripts\python.exe" -m pip install --quiet -e ".[ocr]" || goto :error
)

if not exist "models\Unlimited-OCR-2\model.safetensors.index.json" (
  ".venv-ocr\Scripts\python.exe" -m ferrero.ocr download || goto :error
)

".venv-ocr\Scripts\python.exe" -m ferrero.ocr %*
goto :eof

:error
echo Setup failed - see the messages above.
pause
