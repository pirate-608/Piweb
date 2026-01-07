# scripts/deploy_public.ps1
$ErrorActionPreference = "Continue" # Don't stop on minor errors like pip warning
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path "$ScriptDir\.."

# Run init_env
try {
    & "$ScriptDir\init_env.ps1"
} catch {
    Write-Host "[ERROR] Environment setup failed." -ForegroundColor Red
    Pause
    exit 1
}

# Activate venv
$env:VIRTUAL_ENV = "$PWD\.venv"
$env:Path = "$PWD\.venv\Scripts;$env:Path"

# Database Configuration (PostgreSQL)
# If you want to switch back to SQLite, comment out the following line
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/grading_system"

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "     Auto Grading System - Public Deploy" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "`n[INFO] Installing production server (waitress)..." -ForegroundColor Yellow
pip install waitress > $null 2>&1

Write-Host ""
if (Test-Path "cloudflared.exe") {
    Write-Host "[INFO] Found cloudflared.exe in project root." -ForegroundColor Green
    
    # Check if cloudflared is already running
    $existing = Get-Process "cloudflared" -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[WARN] cloudflared is already running (PID: $($existing.Id))." -ForegroundColor Yellow
        Write-Host "       This might be a background service or a leftover process."
        $kill = Read-Host "Do you want to stop it and start a new tunnel instance? (Y/N)"
        
        if ($kill -eq "Y" -or $kill -eq "y") {
            Write-Host "[INFO] Stopping existing cloudflared..." -ForegroundColor Yellow
            Stop-Process -InputObject $existing -Force -ErrorAction SilentlyContinue
            # Try to uninstall service just in case it keeps restarting
            Start-Process -FilePath ".\cloudflared.exe" -ArgumentList "service", "uninstall" -NoNewWindow -Wait -ErrorAction SilentlyContinue
            Start-Time-Sleep -Seconds 2
        } else {
            Write-Host "[INFO] Keeping existing process running." -ForegroundColor Cyan
            Write-Host "       Make sure it is connected to the right tunnel!"
        }
    }

    # Re-check if it is still running (if user said N, or if kill failed, or if it wasn't running)
    if (-not (Get-Process "cloudflared" -ErrorAction SilentlyContinue)) {
        Write-Host "[INFO] Starting Cloudflare Tunnel..." -ForegroundColor Green
        
        if (Test-Path "tunnel_token.txt") {
            Write-Host "[INFO] Found tunnel_token.txt, starting custom domain tunnel..." -ForegroundColor Green
            $token = Get-Content "tunnel_token.txt" -Raw
            $token = $token.Trim()
            # Added --protocol http2 to avoid QUIC timeout issues (common in restricted networks)
            Start-Process -FilePath ".\cloudflared.exe" -ArgumentList "tunnel", "run", "--protocol", "http2", "--token", "$token" -NoNewWindow:$false
        } elseif (Test-Path "tunnel_name.txt") {
             # Support running by name if configured locally
            $name = Get-Content "tunnel_name.txt" -Raw
            $name = $name.Trim()
            Write-Host "[INFO] Found tunnel_name.txt, starting tunnel named '$name'..." -ForegroundColor Green
            Start-Process -FilePath ".\cloudflared.exe" -ArgumentList "tunnel", "run", "--protocol", "http2", "$name" -NoNewWindow:$false
        } else {
            Write-Host "[INFO] No Tunnel configuration found." -ForegroundColor Yellow
            Write-Host "       To use your custom domain (Recommended):"
            Write-Host "       1. Create a tunnel in Cloudflare Zero Trust Dashboard."
            Write-Host "       2. Save the token to 'tunnel_token.txt'."
            Write-Host ""
            
            $yn = Read-Host "Do you want to start a temporary Quick Tunnel with a random URL? (Y/N)"
            if ($yn -eq "Y" -or $yn -eq "y") {
                Start-Process -FilePath ".\cloudflared.exe" -ArgumentList "tunnel", "--protocol", "http2", "--url", "http://localhost:8080" -NoNewWindow:$false
                Write-Host "[INFO] Cloudflare Tunnel started in a new window." -ForegroundColor Green
            } else {
                Write-Host "[INFO] Skipping tunnel start. Web server will run locally only." -ForegroundColor Cyan
            }
        }
    }
} else {
    Write-Host "[TIP] cloudflared.exe not found in project root." -ForegroundColor Yellow
    Write-Host "      To enable public access, download cloudflared.exe to this folder."
}

Write-Host "`n[INFO] Starting Production Server (Waitress)..." -ForegroundColor Green
Write-Host "[INFO] Serving on http://0.0.0.0:8080" -ForegroundColor Green
Write-Host "[INFO] Press Ctrl+C to stop."

$env:PYTHONPATH = "web"
python web\wsgi.py
Pause
