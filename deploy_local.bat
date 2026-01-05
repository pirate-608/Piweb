@echo off
chcp 65001 > nul

:: Run common setup
call init_env.bat
if %errorlevel% neq 0 exit /b %errorlevel%

:: Activate venv (init_env.bat uses setlocal so we need to activate again)
call .venv\Scripts\activate

:menu
cls
echo ==========================================
echo      Auto Grading System - Local Deploy
echo ==========================================
echo 1. Run Web Interface (Dev Mode)
echo 2. Run CLI Mode (Command Line)
echo 3. Rebuild C Core
echo 4. Exit
echo ==========================================
set /p choice="Please select (1-4): "

if "%choice%"=="1" goto run_web
if "%choice%"=="2" goto run_cli
if "%choice%"=="3" goto rebuild
if "%choice%"=="4" goto end

goto menu

:run_web
echo.
echo Starting Web Server (Development Mode)...
echo Press Ctrl+C to stop.
python web/app.py
pause
goto menu

:run_cli
echo.
echo Starting CLI...
if not exist build\auto_grader.exe (
    echo [ERROR] Executable not found. Please build first.
    pause
    goto menu
)
build\auto_grader.exe
pause
goto menu

:rebuild
echo.
echo Rebuilding...
make clean
make
pause
goto menu

:end
