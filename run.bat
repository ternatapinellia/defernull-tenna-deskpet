@echo off
chcp 65001 >nul
echo ========================================
echo    Desk Pet - Launcher
echo ========================================
echo.

if not exist index.py (
    echo [ERROR] index.py not found!
    echo Please make sure index.py is in the current directory.
    echo.
    echo Current directory files:
    dir /b *.py 2>nul
    echo.
    pause
    exit /b 1
)

if not exist dialogues.py (
    echo [WARNING] dialogues.py not found!
    echo The program may not work properly without dialogue files.
    echo.
)

echo Starting Desk Pet...
echo Press Ctrl+C to exit
echo.

python index.py

echo.
echo Program exited
pause
