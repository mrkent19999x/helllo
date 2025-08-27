@echo off
title Tax Protection Cloud GUI Launcher
echo ==================================================
echo    TAX PROTECTION CLOUD GUI - LAUNCHER
echo ==================================================
echo.
echo Starting Tax Protection Cloud GUI...
echo.

cd /d "%~dp0"
python src\cloud_enterprise.py --control

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start GUI
    echo Please check if Python is installed correctly
    pause
) else (
    echo.
    echo GUI closed successfully
)