# ══════════════════════════════════════════════════════════════════════════════
# Crypto Trading Bot — Windows Installer
# Run in PowerShell (as Administrator):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\install.ps1
# ══════════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Crypto Trading Bot — Windows Setup               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Helper functions ──────────────────────────────────────────────────────────

function Check-Command($name) {
    return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

function Print-Step($step, $msg) {
    Write-Host "[$step] $msg" -ForegroundColor Yellow
}

function Print-OK($msg) {
    Write-Host "  ✔  $msg" -ForegroundColor Green
}

function Print-Skip($msg) {
    Write-Host "  ⏭  $msg (already installed)" -ForegroundColor Gray
}

function Print-Error($msg) {
    Write-Host "  ✘  $msg" -ForegroundColor Red
}

# ── Step 1: Check Python ──────────────────────────────────────────────────────

Print-Step "1/6" "Checking Python 3.10+"

if (Check-Command "python") {
    $pyVersion = python --version 2>&1
    Print-Skip "Python found: $pyVersion"
} else {
    Write-Host "  Python not found. Opening download page..." -ForegroundColor Yellow
    Start-Process "https://www.python.org/downloads/"
    Write-Host ""
    Write-Host "  Please install Python 3.10 or newer, then re-run this script." -ForegroundColor Red
    Write-Host "  IMPORTANT: Check 'Add Python to PATH' during installation!" -ForegroundColor Red
    Read-Host "  Press Enter after Python is installed"
}

# ── Step 2: Check/install Git ─────────────────────────────────────────────────

Print-Step "2/6" "Checking Git"

if (Check-Command "git") {
    Print-Skip "Git found: $(git --version)"
} else {
    Write-Host "  Git not found. Opening download page..." -ForegroundColor Yellow
    Start-Process "https://git-scm.com/download/win"
    Read-Host "  Press Enter after Git is installed"
}

# ── Step 3: Create virtual environment ───────────────────────────────────────

Print-Step "3/6" "Creating Python virtual environment"

if (Test-Path ".\venv") {
    Print-Skip "venv already exists"
} else {
    python -m venv venv
    Print-OK "Created .\venv"
}

# Activate venv
$activateScript = ".\venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
    Print-OK "Virtual environment activated"
} else {
    Print-Error "Could not activate venv — run manually: .\venv\Scripts\activate"
}

# ── Step 4: Install Python dependencies ──────────────────────────────────────

Print-Step "4/6" "Installing Python packages (this may take 2-5 minutes)"

pip install --upgrade pip --quiet
pip install -r bot/requirements.txt
Print-OK "All Python packages installed"

# ── Step 5: Install Node.js dependencies ──────────────────────────────────────

Print-Step "5/6" "Installing Node.js dependencies (dashboard)"

if (Check-Command "node") {
    Print-OK "Node.js found: $(node --version)"
    if (Check-Command "pnpm") {
        pnpm install
        Print-OK "pnpm packages installed"
    } elseif (Check-Command "npm") {
        npm install -g pnpm
        pnpm install
        Print-OK "pnpm installed and packages installed"
    }
} else {
    Write-Host "  Node.js not found — skipping dashboard setup." -ForegroundColor Yellow
    Write-Host "  Install from https://nodejs.org if you want the dashboard." -ForegroundColor Yellow
}

# ── Step 6: Setup .env ───────────────────────────────────────────────────────

Print-Step "6/6" "Setting up environment configuration"

if (Test-Path ".env") {
    Print-Skip ".env already exists"
} else {
    Copy-Item ".env.example" ".env"
    Print-OK "Created .env from template"
    Write-Host ""
    Write-Host "  ⚠  IMPORTANT: Open .env and fill in your keys:" -ForegroundColor Yellow
    Write-Host "     - TELEGRAM_BOT_TOKEN    (from @BotFather)" -ForegroundColor Cyan
    Write-Host "     - TELEGRAM_CHAT_ID      (from getUpdates API)" -ForegroundColor Cyan
    Write-Host "     - GROQ_API_KEY          (from console.groq.com — free)" -ForegroundColor Cyan
    Write-Host "     - OPENROUTER_API_KEY    (from openrouter.ai/keys)" -ForegroundColor Cyan
    Write-Host "     - HUGGINGFACE_API_KEY   (from hf.co/settings/tokens)" -ForegroundColor Cyan
}

# ── Optional: Ollama ──────────────────────────────────────────────────────────

Write-Host ""
$installOllama = Read-Host "Install Ollama (local AI, no API key needed)? [y/N]"
if ($installOllama -eq "y" -or $installOllama -eq "Y") {
    if (Check-Command "ollama") {
        Print-Skip "Ollama already installed"
    } else {
        Write-Host "  Downloading Ollama for Windows..." -ForegroundColor Yellow
        $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
        $dest = "$env:TEMP\OllamaSetup.exe"
        Invoke-WebRequest -Uri $ollamaUrl -OutFile $dest
        Start-Process $dest -Wait
        Print-OK "Ollama installed"
    }
    Write-Host "  Pulling mistral model (may take 5-10 min on first run)..."
    ollama pull mistral
    Print-OK "Mistral model ready"
}

# ── Create required folders ───────────────────────────────────────────────────

New-Item -ItemType Directory -Force -Path "bot\user_data\data"            | Out-Null
New-Item -ItemType Directory -Force -Path "bot\user_data\logs"            | Out-Null
New-Item -ItemType Directory -Force -Path "bot\user_data\backtest_results" | Out-Null

# ── Done ───────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✔  Setup Complete!                                  ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║                                                      ║" -ForegroundColor Green
Write-Host "║  Next steps:                                         ║" -ForegroundColor Green
Write-Host "║  1. Edit .env with your Telegram/Groq keys           ║" -ForegroundColor Green
Write-Host "║  2. Download data:                                   ║" -ForegroundColor Green
Write-Host "║     python scripts/download_data.py                  ║" -ForegroundColor Green
Write-Host "║  3. Run backtest:                                    ║" -ForegroundColor Green
Write-Host "║     python scripts/run_backtest.py                   ║" -ForegroundColor Green
Write-Host "║  4. Run unit tests:                                  ║" -ForegroundColor Green
Write-Host "║     cd bot && pytest tests/ -v                       ║" -ForegroundColor Green
Write-Host "║  5. Start paper trading:                             ║" -ForegroundColor Green
Write-Host "║     freqtrade trade --config bot/config.paper.json   ║" -ForegroundColor Green
Write-Host "║        --strategy AIRSIStrategy                      ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
