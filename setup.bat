@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo.
echo Setup complete. Run start.bat to open Nuts.
echo For rewriting, install Ollama and run: ollama pull qwen2.5:7b
pause
exit /b 0
:fail
echo Setup failed. Install Python 3.12 and check your internet connection.
pause
exit /b 1
