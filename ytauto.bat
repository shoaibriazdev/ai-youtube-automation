@echo off
rem Command line access from any folder:  ytauto today ^| ytauto ideas ^| ytauto doctor ^| ytauto --help
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
"%~dp0.venv\Scripts\python.exe" -m ytauto %*
