@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo    DNT Desktop Pet - Pack Script
echo ========================================
echo.

echo 正在检查打包环境...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [错误] 未安装 PyInstaller！
    echo 请先运行 install.bat 安装依赖。
    echo.
    pause
    exit /b 1
)
echo [成功] 打包环境正常
echo.

echo 检查必要文件...
if not exist index.py (
    echo [错误] 找不到 index.py！
    pause
    exit /b 1
)
if not exist dialogues.py (
    echo [错误] 找不到 dialogues.py！
    pause
    exit /b 1
)
if not exist dnt.save (
    echo [错误] 找不到 dnt.save！
    pause
    exit /b 1
)
if not exist tenna_voice_normal (
    echo [错误] 找不到 tenna_voice_normal 文件夹！
    pause
    exit /b 1
)
if not exist tenna_voice_reminder (
    echo [错误] 找不到 tenna_voice_reminder 文件夹！
    pause
    exit /b 1
)
echo [成功] 必要文件检查通过
echo.

echo 步骤1: 清理旧的打包文件...
if exist build (
    echo 删除 build 文件夹...
    rmdir /s /q build 2>nul
)
if exist dist (
    echo 删除 dist 文件夹...
    rmdir /s /q dist 2>nul
)
if exist *.spec (
    echo 删除 spec 文件...
    del /q *.spec 2>nul
)
echo [完成] 清理完成
echo.

echo 步骤2: 开始打包程序...
echo WAV 音频不会嵌入 EXE，而是作为外部文件复制到 dist。
echo 这可能需要几分钟时间，请耐心等待...
echo.

python -m PyInstaller --onefile --windowed --name="DesktopPet" --icon="favicon.ico" --add-data="pet.png;." --add-data="pet-happy.png;." --add-data="pet1.png;." --add-data="pet2.png;." --add-data="pet3.png;." --add-data="pet4.png;." --add-data="pet5.png;." --add-data="pet6.png;." --add-data="pet7.png;." --add-data="pet8.png;." --add-data="pet9.png;." --add-data="bubble.png;." --add-data="panel.png;." --add-data="panel2.png;." --add-data="favicon.ico;." --add-data="dialogues.py;." --hidden-import=PyQt5 --hidden-import=PyQt5.QtCore --hidden-import=PyQt5.QtGui --hidden-import=PyQt5.QtWidgets index.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    echo 请检查上面的错误信息。
    echo.
    pause
    exit /b 1
)

echo.
echo 步骤3: 复制外部资源到 dist...
if exist dnt.save copy /Y "dnt.save" "dist\dnt.save" >nul
if exist note.txt copy /Y "note.txt" "dist\note.txt" >nul
if exist "tenna_voice_normal" xcopy /E /I /Y "tenna_voice_normal" "dist\tenna_voice_normal" >nul
if exist "tenna_voice_reminder" xcopy /E /I /Y "tenna_voice_reminder" "dist\tenna_voice_reminder" >nul

echo.
echo 步骤4: 验证打包结果...
if exist "dist\DesktopPet.exe" (
    echo [成功] DesktopPet.exe 打包成功！
) else (
    echo [错误] 找不到 DesktopPet.exe 文件！
    pause
    exit /b 1
)
if exist "dist\dnt.save" (
    echo [成功] dnt.save 已复制
) else (
    echo [警告] 未找到 dist\dnt.save
)
if exist "dist\tenna_voice_normal\tenna_voice_01.wav" (
    echo [成功] 普通对话音频已复制
) else (
    echo [警告] 未找到普通对话音频
)
if exist "dist\tenna_voice_reminder\tenna_voice_01.wav" (
    echo [成功] 提醒音频已复制
) else (
    echo [警告] 未找到提醒音频
)

echo.
echo ========================================
echo    打包完成！
echo.
echo    dist\DesktopPet.exe
echo    dist\dnt.save
echo    dist\note.txt
echo   dist\tenna_voice_normal\
echo   dist\tenna_voice_reminder\
echo.
echo    WAV 不会嵌入 EXE，程序从 EXE 同目录读取。
echo ========================================
echo.
pause
endlocal
