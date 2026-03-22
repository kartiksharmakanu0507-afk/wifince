@echo off
title WIFINCE — Starting...
cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found!
    echo  Download from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b
)

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt >nul 2>&1

:: Kill any old Flask process on port 5000
echo Clearing port 5000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

title WIFINCE — Running!
echo.
echo ==========================================
echo   WIFINCE is starting...
echo   Open: http://192.168.43.1:5000
echo ==========================================
echo.
python app.py
pause
