@echo off
title AI YouTube Automation Pro - Server (close this window to stop)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Not installed yet. Run setup.bat first.
  pause
  exit /b 1
)
echo Starting the dashboard at http://localhost:8000 ...
echo Keep this window open. Close it (or run stop.bat) to stop the server.
".venv\Scripts\python.exe" -m ytauto serve --open
if errorlevel 1 (
  echo.
  echo The server stopped with an error. See docs\TROUBLESHOOTING.md
  pause
)
