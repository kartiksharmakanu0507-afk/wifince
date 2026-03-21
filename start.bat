@echo off
title WIFINCE — Starting...
cd /d "%~dp0"

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
echo ==========================================
echo.
"C:\Users\Dell\AppData\Local\Programs\Python\Python312\python.exe" app.py
pause
