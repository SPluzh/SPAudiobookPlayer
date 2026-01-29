@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"
set "PATH=%~dp0bin;%PATH%"

echo ==================================================
echo  SPAudiobookPlayer - BUILD
echo ==================================================

REM --- проверка python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    pause
    exit /b 1
)

REM --- проверка pyinstaller ---
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller not installed
    echo Install: pip install pyinstaller
    pause
    exit /b 1
)

REM --- проверка UPX ---
where upx >nul 2>&1
if errorlevel 1 (
    echo [WARNING] UPX not found in PATH. Exe size will be larger.
    echo Download UPX from https://upx.github.io/ and add to PATH for better compression.
    pause
)

REM --- очистка предыдущих сборок ---
if exist build (
    echo Cleaning build/
    rmdir /s /q build
    if exist build (
        echo [ERROR] Failed to delete 'build' directory. Close open files and try again.
        pause
        exit /b 1
    )
)

if exist dist (
    echo Cleaning dist/
    rmdir /s /q dist
    if exist dist (
        echo [ERROR] Failed to delete 'dist' directory.
        pause
        exit /b 1
    )
)

REM --- сборка ---
echo.
echo Building...
echo.

python -m PyInstaller SPAudiobookPlayer.spec
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

REM --- Cleaning up build folder after build ---
if exist build (
    rmdir /s /q build
)

REM --- Remove duplicated bass.dll from _internal root ---
if exist "dist\SP Audiobook Player\_internal\bass.dll" (
    echo Cleaning duplicated bass.dll...
    del /f /q "dist\SP Audiobook Player\_internal\bass.dll"
)

echo.
echo ==========================================
echo  BUILD SUCCESSFUL
echo ==========================================
echo.

REM --- Open output folder ---
if not exist "dist\SP Audiobook Player" (
    echo [ERROR] Output directory missing.
    pause
    exit /b 1
)
explorer "dist\SP Audiobook Player"

echo Output:
echo   dist\SPAudiobookPlayer\SP Audiobook Player.exe
echo.

