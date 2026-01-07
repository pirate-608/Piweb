# scripts/deploy_local.ps1
$ErrorActionPreference = "Stop"
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

# Activate venv explicitly again just in case
$env:VIRTUAL_ENV = "$PWD\.venv"
$env:Path = "$PWD\.venv\Scripts;$env:Path"

# Database Configuration (PostgreSQL)
# If you want to switch back to SQLite, comment out the following line
$env:DATABASE_URL = "postgresql://postgres:mysecretpassword@localhost:5432/postgres"

function Show-Menu {
    Clear-Host
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "     Auto Grading System - Local Deploy" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "1. Run Web Interface (Dev Mode)"
    Write-Host "2. Run CLI Mode (Command Line)"
    Write-Host "3. Rebuild C Core"
    Write-Host "4. Exit"
    Write-Host "==========================================" -ForegroundColor Cyan
}

while ($true) {
    Show-Menu
    $choice = Read-Host "Please select (1-4)"
    
    switch ($choice) {
        "1" {
            Write-Host "`nStarting Web Server (Development Mode)..." -ForegroundColor Green
            $env:PYTHONPATH = "web"
            python -m app
            Pause
        }
        "2" {
            Write-Host "`nStarting CLI..." -ForegroundColor Green
            if (Test-Path "build\auto_grader.exe") {
                .\build\auto_grader.exe
            } else {
                Write-Host "[ERROR] Executable not found. Please build first." -ForegroundColor Red
            }
            Pause
        }
        "3" {
            Write-Host "`nRebuilding..." -ForegroundColor Yellow
            if (Get-Command make -ErrorAction SilentlyContinue) {
                make clean
                make
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[OK] Rebuild complete." -ForegroundColor Green
                }
            } else {
                Write-Host "[ERROR] 'make' not found." -ForegroundColor Red
            }
            Pause
        }
        "4" {
            exit
        }
        default {
            # continue loop
        }
    }
}
