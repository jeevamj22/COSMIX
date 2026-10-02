@echo off
cd /d "%~dp0"
title COSMIX
echo.
echo  COSMIX will open at http://127.0.0.1:8000
echo  Leave this window open while you use it.
echo  Close the window when you want to stop.
echo.
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not installed, or it is not on PATH.
  echo Install Python from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Could not install COSMIX.
  pause
  exit /b 1
)
set COSMIX_OPEN_BROWSER=1
call .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
