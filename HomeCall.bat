@echo off
rem Double-click to start HomeCall on this PC.  (Owner: lead)
rem The first time it sets everything up by itself (Python packages, cloudflared).
rem Keep this window open while you use HomeCall; close it to stop.
title HomeCall
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo First time here: setting up HomeCall, this takes a minute or two...
  py -3 -m venv .venv 2>nul || python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" goto nopython
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 11))" || goto nopython

echo Checking HomeCall's Python packages...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt

rem cloudflared: the tunnel that lets your phone reach this PC from anywhere.
where cloudflared >nul 2>nul || if not exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" winget install -e --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements

".venv\Scripts\python.exe" start.py %*
pause
exit /b

:nopython
echo HomeCall needs Python 3.11 or newer: https://www.python.org/downloads/
echo When installing, tick "Add python.exe to PATH". Then double-click HomeCall again.
pause
