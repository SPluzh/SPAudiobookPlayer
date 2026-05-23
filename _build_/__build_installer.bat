@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

echo ==================================================
echo  SPAudiobookPlayer - BUILD INSTALLER
echo ==================================================

set "DIST_DIR=dist\SP Audiobook Player"
set "VERSION_FILE=dist\SP Audiobook Player\_internal\resources\version.txt"
if not exist "%VERSION_FILE%" set "VERSION_FILE=..\resources\version.txt"
set "SPEC_FILE=installer.iss"
set "INNO_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

REM --- Check dist folder exists ---
if not exist "!DIST_DIR!" (
    echo [ERROR] Distribution directory not found: !DIST_DIR!
    echo Run __build.bat first to build the application.
    pause
    exit /b 1
)

REM --- Check installer.iss exists ---
if not exist "!SPEC_FILE!" (
    echo [ERROR] Inno Setup script not found: !SPEC_FILE!
    echo Create installer.iss first. See installer_plan.md for details.
    pause
    exit /b 1
)

REM --- Check Inno Setup is installed ---
if not exist "!INNO_EXE!" (
    echo [ERROR] Inno Setup not found at: !INNO_EXE!
    echo Download from: https://jrsoftware.org/isinfo.php
    pause
    exit /b 1
)

REM --- Get version from version.txt ---
if exist "%VERSION_FILE%" (
    for /f "usebackq tokens=*" %%i in ("%VERSION_FILE%") do set "VERSION=%%i"
) else (
    set "VERSION=unknown"
)

echo.
echo Version : !VERSION!
echo Source  : !DIST_DIR!
echo Script  : !SPEC_FILE!
echo.

REM --- Run Inno Setup compiler ---
echo Compiling installer...
echo.
"!INNO_EXE!" "!SPEC_FILE!" /DAppVersion=!VERSION! /O.

if errorlevel 1 (
    echo.
    echo [ERROR] Inno Setup compilation failed.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  INSTALLER CREATED SUCCESSFULLY
echo  Version: !VERSION!
echo ==========================================
echo.

REM --- Open output folder ---
explorer .
