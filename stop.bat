@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist "data\server.pid" (
  echo No running server found.
  ping -n 3 127.0.0.1 >nul
  exit /b 0
)
set /p PID=<"data\server.pid"
taskkill /PID !PID! /T /F >nul 2>nul && (echo Server stopped.) || (echo Server was not running.)
del "data\server.pid" >nul 2>nul
ping -n 3 127.0.0.1 >nul
