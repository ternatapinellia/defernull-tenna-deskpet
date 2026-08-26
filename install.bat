@echo off
chcp 65001 >nul
echo ========================================
echo    Desk Pet - Dependency Installer
echo ========================================
echo.

echo Checking Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python and add it to PATH.
    echo.
    pause
    exit /b 1
)
echo [SUCCESS] Python environment OK
echo.

echo Upgrading pip...
python -m pip install --upgrade pip
echo.

echo Installing PyQt5...
python -m pip install PyQt5 PyQt5-sip
if errorlevel 1 (
    echo [ERROR] PyQt5 installation failed!
    pause
    exit /b 1
)
echo [SUCCESS] PyQt5 installed
echo.

echo Installing PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] PyInstaller installation failed!
    pause
    exit /b 1
)
echo [SUCCESS] PyInstaller installed
echo.

echo Verifying installations...
python -c "import PyQt5; print('PyQt5 version:', PyQt5.__version__)" 2>nul
python -c "import PyInstaller; print('PyInstaller version:', PyInstaller.__version__)" 2>nul
echo.

echo ========================================
echo    All dependencies installed!
echo    You can now run run.bat to start
echo ========================================
echo.
pause
