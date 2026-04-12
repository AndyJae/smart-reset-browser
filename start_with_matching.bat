@echo off
set SMART_RESET_PLUGIN=C:\smart-matching-local
py web_main.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: startup failed (exit code %errorlevel%)
    pause
)
