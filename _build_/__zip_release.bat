@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo ==================================================
echo  SPAudiobookPlayer - CREATE ZIP RELEASE
echo ==================================================

set "DIST_DIR=dist\SP Audiobook Player"
set "VERSION_FILE=..\resources\version.txt"

if not exist "!DIST_DIR!" (
    echo [ERROR] Distribution directory not found: !DIST_DIR!
    echo Run __build.bat first.
    pause
    exit /b 1
)

REM --- Get version from version.txt ---
if exist "!VERSION_FILE!" (
    set /p VERSION=<"!VERSION_FILE!"
) else (
    set "VERSION=unknown"
)

set "ZIP_NAME=SP_Audiobook_Player_v!VERSION!.zip"

echo.
echo Creating release zip: !ZIP_NAME!
echo Excluding from release: _internal\*.exe, settings.ini, data/
echo.

REM --- Create a temporary directory for zipping ---
set "TEMP_ZIP_DIR=temp_release"

if exist "!TEMP_ZIP_DIR!" rmdir /s /q "!TEMP_ZIP_DIR!"
mkdir "!TEMP_ZIP_DIR!"

echo Copying files to temporary directory...
xcopy /e /i /y "!DIST_DIR!" "!TEMP_ZIP_DIR!" >nul

REM --- Remove specific files from everywhere in temp dir ---
echo Filtering out excluded files...
del /s /f /q "!TEMP_ZIP_DIR!\_internal\*.exe" >nul 2>&1
del /s /f /q "!TEMP_ZIP_DIR!\settings.ini" >nul 2>&1

REM --- Remove data folder from temp dir ---
if exist "!TEMP_ZIP_DIR!\data" (
    echo Removing data folder...
    rmdir /s /q "!TEMP_ZIP_DIR!\data"
)

REM --- Remove data folder if it is in _internal (common with PyInstaller) ---
if exist "!TEMP_ZIP_DIR!\_internal\data" (
    echo Removing _internal\data folder...
    rmdir /s /q "!TEMP_ZIP_DIR!\_internal\data"
)

echo Bundling files into zip with maximum compression...
if exist "!ZIP_NAME!" del /f /q "!ZIP_NAME!"

REM Use Python to create the zip file with maximum compression (level 9)
python -c "import zipfile, os; z = zipfile.ZipFile('!ZIP_NAME!', 'w', zipfile.ZIP_DEFLATED, compresslevel=9); [z.write(os.path.join(root, f), os.path.relpath(os.path.join(root, f), '!TEMP_ZIP_DIR!')) for root, dirs, files in os.walk('!TEMP_ZIP_DIR!') for f in files]; z.close()"

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to create zip file.
    pause
    exit /b 1
)

echo Cleaning up...
rmdir /s /q "!TEMP_ZIP_DIR!"

echo.
echo ==========================================
echo  RELEASE ZIP CREATED SUCCESSFULLY
echo  File: !ZIP_NAME!
echo ==========================================
echo.
pause
