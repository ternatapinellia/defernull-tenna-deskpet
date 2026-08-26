@echo off
chcp 65001 >nul
echo ========================================
echo    Desk Pet - Packager
echo ========================================
echo.

echo Checking environment...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [ERROR] PyInstaller not found!
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)
echo [SUCCESS] PyInstaller found
echo.

echo Checking required files...
if not exist index.py (
    echo [ERROR] index.py not found!
    pause
    exit /b 1
)
if not exist dialogues.py (
    echo [ERROR] dialogues.py not found!
    pause
    exit /b 1
)
echo [SUCCESS] Required files found
echo.

echo Step 1: Cleaning old builds...
if exist build (
    echo Deleting build folder...
    rmdir /s /q build 2>nul
)
if exist dist (
    echo Deleting dist folder...
    rmdir /s /q dist 2>nul
)
if exist *.spec (
    echo Deleting spec files...
    del /q *.spec 2>nul
)
echo [COMPLETE] Cleanup done
echo.

echo Step 2: Building executable...
echo This may take a few minutes, please wait...
echo.

python -m PyInstaller --onefile --windowed --name="DeskPet" --icon="favicon.ico" --add-data="pet.png;." --add-data="pet-happy.png;." --add-data="pet1.png;." --add-data="pet2.png;." --add-data="pet3.png;." --add-data="pet4.png;." --add-data="pet5.png;." --add-data="pet6.png;." --add-data="pet7.png;." --add-data="pet8.png;." --add-data="pet9.png;." --add-data="bubble.png;." --add-data="panel.png;." --add-data="panel2.png;." --add-data="favicon.ico;." --add-data="dialogues.py;." --hidden-import=PyQt5 --hidden-import=PyQt5.QtCore --hidden-import=PyQt5.QtGui --hidden-import=PyQt5.QtWidgets index.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    echo Please check the error messages above.
    echo.
    pause
    exit /b 1
)

echo.
echo Step 3: Verifying build...
if exist "dist\DeskPet.exe" (
    echo.
    echo ========================================
    echo    BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Executable: dist\DeskPet.exe
    echo File size: about 50-80 MB
    echo.
    echo To run: double-click dist\DeskPet.exe
    echo.
) else (
    echo [ERROR] Build failed: DeskPet.exe not found!
)

echo.
pause
