@echo off
setlocal

echo === smart-reset build ===
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH.
    pause & exit /b 1
)

REM Install / upgrade PyInstaller
echo [1/3] Installing PyInstaller...
pip install --quiet --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: pip install pyinstaller failed.
    pause & exit /b 1
)

REM Install project dependencies
echo [2/3] Installing project dependencies...
pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install -r requirements.txt failed.
    pause & exit /b 1
)

REM Run PyInstaller
echo [3/3] Building executable...
pyinstaller smart_reset.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed. See output above.
    pause & exit /b 1
)

echo.
echo Build complete: dist\smart-reset.exe
echo.
pause
