@echo off
:: ==========================================
::   Auto Grading System - Tunnel Launcher
::   Protocol: HTTP2 (Solves QUIC blocking)
:: ==========================================

:: Ensure we are in the script's directory
cd /d "%~dp0"

title Cloudflare Tunnel (HTTP2 Mode)
color 0A

echo.
echo [INFO] Checking environment...

if not exist "cloudflared.exe" (
    color 0C
    echo [ERROR] cloudflared.exe not found!
    echo Please download cloudflared.exe and place it in this folder:
    echo %~dp0
    echo.
    pause
    exit /b 1
)

if not exist "tunnel_token.txt" (
    color 0C
    echo [ERROR] tunnel_token.txt not found!
    echo Please create 'tunnel_token.txt' in this folder and paste your Cloudflare Token inside.
    echo.
    pause
    exit /b 1
)

echo [INFO] Found cloudflared.exe
echo [INFO] Found tunnel_token.txt
echo.
echo [START] Starting Cloudflare Tunnel with --protocol http2...
echo         (Keep this window open to maintain the connection)
echo.

:: Run the command using PowerShell to safely read the token
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; try { $token = (Get-Content tunnel_token.txt -Raw).Trim(); .\cloudflared.exe tunnel run --protocol http2 --token $token } catch { Write-Host 'Error: ' $_.Exception.Message -ForegroundColor Red; exit 1 }"

if %ERRORLEVEL% neq 0 (
    color 0C
    echo.
    echo [WARN] Tunnel exited unexpectedly. 
    pause
)
