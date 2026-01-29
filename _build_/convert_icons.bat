@echo off
pushd "%~dp0"
python convert_icons.py "..\resources\icons"
if %errorlevel% neq 0 (
    echo Error occurred during conversion.
    pause
) else (
    echo Conversion completed successfully.
    timeout /t 3 >nul
)
popd
