# scripts/init_env.ps1
# Auto Grading System - Environment Setup Script
$ErrorActionPreference = "Stop"

# Ensure we are in the project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path "$ScriptDir\.."

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "     Auto Grading System - Init Env" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Check Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found! Please install Python 3.8+ and add it to PATH." -ForegroundColor Red
    Pause
    exit 1
}

# 2. Build C Project
Write-Host "`n[1/5] Building C Core..." -ForegroundColor Yellow
if (Get-Command make -ErrorAction SilentlyContinue) {
    try {
        make
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Build successful." -ForegroundColor Green
        } else {
            throw "Make command failed"
        }
    } catch {
        Write-Host "[ERROR] Build failed." -ForegroundColor Red
        Pause
        exit 1
    }
} else {
    Write-Host "[WARNING] 'make' command not found." -ForegroundColor Yellow
    Write-Host "Please ensure MinGW/GCC is installed if you need to recompile C code."
    Write-Host "If you already have build/auto_grader.exe, you can ignore this."
    $response = Read-Host "Continue without make? (Y/N)"
    if ($response -ne "Y" -and $response -ne "y") { exit 1 }
}

# 3. Setup Virtual Environment
Write-Host "`n[2/5] Setting up Python Virtual Environment..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv..."
    python -m venv .venv
} else {
    Write-Host ".venv already exists."
}

# 4. Install Dependencies
Write-Host "`n[3/5] Installing Dependencies..." -ForegroundColor Yellow
# Activate venv for current session
$env:VIRTUAL_ENV = "$PWD\.venv"
$env:Path = "$PWD\.venv\Scripts;$env:Path"

if (Test-Path "web/requirements.txt") {
    pip install -r web/requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to install dependencies." -ForegroundColor Red
        Pause
        exit 1
    }
    Write-Host "[OK] Dependencies installed." -ForegroundColor Green
} else {
    Write-Host "[WARNING] web/requirements.txt not found." -ForegroundColor Yellow
}

# 5. Check Static Resources
Write-Host "`n[4/5] Checking Static Resources..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "web\static\css" | Out-Null
New-Item -ItemType Directory -Force -Path "web\static\js" | Out-Null

$missing = $false
if (-not (Test-Path "web\static\css\bootstrap.min.css")) { $missing = $true }
if (-not (Test-Path "web\static\js\bootstrap.bundle.min.js")) { $missing = $true }
if (-not (Test-Path "web\static\js\chart.js")) { $missing = $true }

if ($missing) {
    Write-Host "Downloading missing static files..."
    try {
        Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css' -OutFile 'web\static\css\bootstrap.min.css'
        Write-Host "  - Bootstrap CSS downloaded." -ForegroundColor Green
        
        Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js' -OutFile 'web\static\js\bootstrap.bundle.min.js'
        Write-Host "  - Bootstrap JS downloaded." -ForegroundColor Green
        
        Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/chart.js' -OutFile 'web\static\js\chart.js'
        Write-Host "  - Chart.js downloaded." -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Failed to download static files: $_" -ForegroundColor Red
    }
} else {
    Write-Host "[OK] Static resources already exist." -ForegroundColor Green
}

# 6. Initialize Database
Write-Host "`n[5/5] Initializing Database..." -ForegroundColor Yellow
$env:PYTHONPATH = "web"
try {
    python -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized.')"
} catch {
    Write-Host "[WARNING] Database initialization failed." -ForegroundColor Yellow
    Write-Host "$_"
}

Write-Host "`n[SUCCESS] Environment setup complete." -ForegroundColor Green
