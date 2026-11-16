@echo off
rem Ferrero case intelligence: starts the web app and opens it in the browser.
rem The port is FERRERO_PORT (environment or .env), 8000 if unset. Embedded Superset dashboards only show
rem when Ferrero is opened from an address Superset allows (its frame-ancestors list), such as http://localhost:8090.
cd /d "%~dp0"

set "PORT=8000"
if exist ".env" for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b /c:"FERRERO_PORT=" ".env"`) do set "PORT=%%b"
if defined FERRERO_PORT set "PORT=%FERRERO_PORT%"

if not exist ".venv\Scripts\python.exe" (
  echo Setting up the Python environment - first run only...
  python -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install --quiet -e ".[bedrock]" || goto :error
)

rem Incremental: unchanged files are skipped, newly recognised scans are added (the first run indexes everything).
echo Updating the document index...
if not exist "data" mkdir "data"
".venv\Scripts\python.exe" -m ferrero.sync > "data\sync.log" 2>&1 || echo Some files could not be read - see data\sync.log

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:%PORT%'"
echo Ferrero is running at http://localhost:%PORT%  (close this window to stop it)
".venv\Scripts\python.exe" -m ferrero.web --port %PORT%
goto :eof

:error
echo Setup failed - see the messages above.
pause
