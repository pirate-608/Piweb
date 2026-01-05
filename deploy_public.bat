@echo off
chcp 65001 > nul

:: Run common setup
call init_env.bat
if %errorlevel% neq 0 exit /b %errorlevel%

:: Activate venv
call .venv\Scripts\activate

echo.
echo ==========================================
echo      Auto Grading System - Public Deploy
echo ==========================================
echo.
echo [INFO] Installing production server (waitress)...
pip install waitress > nul 2>&1

echo.
echo [INFO] Starting Production Server (Waitress)...
echo [INFO] Serving on http://0.0.0.0:8080
echo.
echo [TIP] To expose to public internet, run Cloudflare Tunnel in another terminal:
echo        .\cloudflared.exe tunnel --url http://localhost:8080
echo.
echo Press Ctrl+C to stop.

python wsgi.py
pause
