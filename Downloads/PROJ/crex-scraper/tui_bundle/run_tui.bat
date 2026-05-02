@echo off
echo ========================================
echo  CREX Cricket TUI
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.9+ from python.org
    pause
    exit /b 1
)

REM Run the TUI
python tui.py