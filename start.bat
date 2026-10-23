@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run setup.bat first. See LOCAL_SETUP.md.
  pause
  exit /b 1
)
.venv\Scripts\python.exe server.py
pause
