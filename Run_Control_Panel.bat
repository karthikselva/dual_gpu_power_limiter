@echo off
setlocal
cd /d "%~dp0"

:: --- Admin Check & Elevation ---
openfiles >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process -FilePath '%0' -Verb RunAs"
    exit /b
)

:: --- Launch GUI ---
echo Starting GPU ^& Telemetry Control Center...
cd pc_side
python.exe control_gui.py

if %errorlevel% neq 0 (
    echo.
    echo Error: Failed to start the GUI. 
    echo Ensure Python is installed and added to your PATH.
    pause
)
