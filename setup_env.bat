@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Minijmp virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :failed
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Environment ready.
pause
exit /b 0

:failed
echo.
echo Environment setup failed.
pause
exit /b 1