@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Minijmp virtual environment not found.
    echo Run setup_env.bat first.
    pause
    exit /b 1
)

"%PYTHON%" "%PROJECT_DIR%start.py"
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%