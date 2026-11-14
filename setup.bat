@echo off
setlocal EnableDelayedExpansion
title AI YouTube Automation Pro - Setup
cd /d "%~dp0"
echo.
echo  ==========================================================
echo   AI YouTube Automation Pro - one-time setup (Windows)
echo  ==========================================================
echo.

set "PY="
where py >nul 2>nul && (py -3 -c "import sys; exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=py -3")
if not defined PY (
  where python >nul 2>nul && (python -c "import sys; exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=python")
)
if not defined PY (
  echo  [X] Python 3.10 or newer was not found.
  echo      Install it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^)
  echo      or run:  winget install Python.Python.3.12
  echo      Then run setup.bat again.
  pause
  exit /b 1
)
echo  [1/5] Using Python: %PY%

if not exist ".venv\Scripts\python.exe" (
  echo  [2/5] Creating virtual environment .venv ...
  %PY% -m venv .venv || (echo  [X] Could not create the virtual environment. & pause & exit /b 1)
) else (
  echo  [2/5] Virtual environment already exists.
)

echo  [3/5] Installing Python packages ^(first time takes a few minutes^) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo  [X] Package installation failed. Check your internet connection and run setup.bat again.
  pause
  exit /b 1
)

echo  [4/5] Preparing configuration ...
if not exist "data\secrets" mkdir "data\secrets"
if not exist "projects" mkdir "projects"
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo        Created .env  ^(add API keys later in the dashboard: API Settings^)
) else (
  echo        .env already exists - left unchanged.
)

echo  [5/5] Checking the installation ...
".venv\Scripts\python.exe" -m ytauto doctor

echo.
set /p SKILLS="Also install the Claude Code skills (/yt-ideas ... /yt-today) for your user? [y/N] "
if /i "!SKILLS!"=="y" ".venv\Scripts\python.exe" scripts\install_skills.py

echo.
echo  Setup complete.
echo   Next:  1) double-click start.bat
echo          2) the dashboard opens at http://localhost:8000
echo          3) optional: add API keys in API Settings, connect YouTube in Upload Manager
echo.
pause
