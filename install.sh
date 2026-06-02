#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# Crypto Trading Bot — Linux / macOS Installer
# Run: bash install.sh
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✔${NC}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
skip() { echo -e "  ${CYAN}⏭${NC}  $1 (already installed)"; }
err()  { echo -e "  ${RED}✘${NC}  $1"; }
step() { echo -e "\n${YELLOW}[$1]${NC} $2"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Crypto Trading Bot — Linux/macOS Setup           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

OS="$(uname -s)"

# ── Step 1: Python ────────────────────────────────────────────────────────────

step "1/6" "Checking Python 3.10+"

if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version)
    skip "Python: $PY_VER"
else
    warn "Python3 not found — installing..."
    if [[ "$OS" == "Darwin" ]]; then
        brew install python@3.11 || { err "Install Homebrew first: https://brew.sh"; exit 1; }
    else
        sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip python3-venv
    fi
    ok "Python installed"
fi

# ── Step 2: Git ───────────────────────────────────────────────────────────────

step "2/6" "Checking Git"

if command -v git &>/dev/null; then
    skip "Git: $(git --version)"
else
    if [[ "$OS" == "Darwin" ]]; then
        xcode-select --install 2>/dev/null || true
    else
        sudo apt-get install -y git
    fi
    ok "Git installed"
fi

# ── Step 3: Python virtual environment ───────────────────────────────────────

step "3/6" "Creating Python virtual environment"

if [[ -d "venv" ]]; then
    skip "venv exists"
else
    python3 -m venv venv
    ok "Created ./venv"
fi

# shellcheck disable=SC1091
source venv/bin/activate
ok "Virtual environment activated"

# ── Step 4: Python dependencies ───────────────────────────────────────────────

step "4/6" "Installing Python packages (2-5 minutes)"

pip install --upgrade pip --quiet
pip install -r bot/requirements.txt
ok "All Python packages installed"

# ── Step 5: Node.js dependencies ─────────────────────────────────────────────

step "5/6" "Installing Node.js dependencies (dashboard)"

if command -v node &>/dev/null; then
    skip "Node.js: $(node --version)"
    if ! command -v pnpm &>/dev/null; then
        npm install -g pnpm --quiet
    fi
    pnpm install --reporter=silent
    ok "pnpm packages installed"
else
    warn "Node.js not found — skipping dashboard. Install from https://nodejs.org"
fi

# ── Step 6: Environment file ──────────────────────────────────────────────────

step "6/6" "Setting up .env configuration"

if [[ -f ".env" ]]; then
    skip ".env already exists"
else
    cp .env.example .env
    ok "Created .env from template"
    echo ""
    warn "IMPORTANT: Open .env and fill in:"
    echo -e "     ${CYAN}TELEGRAM_BOT_TOKEN${NC}  ← from @BotFather on Telegram"
    echo -e "     ${CYAN}TELEGRAM_CHAT_ID${NC}    ← from getUpdates API call"
    echo -e "     ${CYAN}GROQ_API_KEY${NC}        ← free at console.groq.com"
fi

# ── Optional: Ollama ──────────────────────────────────────────────────────────

echo ""
read -rp "Install Ollama (local AI, no API key needed)? [y/N]: " INSTALL_OLLAMA
if [[ "${INSTALL_OLLAMA,,}" == "y" ]]; then
    if command -v ollama &>/dev/null; then
        skip "Ollama already installed"
    else
        echo "  Downloading and installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
        ok "Ollama installed"
    fi
    echo "  Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
    echo "  Pulling mistral model (~4GB, please wait)..."
    ollama pull mistral
    ok "Mistral model ready at http://localhost:11434"
fi

# ── Create required directories ───────────────────────────────────────────────

mkdir -p bot/user_data/{data,logs,backtest_results}
chmod +x scripts/setup_ollama.sh scripts/download_data.py scripts/run_backtest.py

# ── Done ───────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✔  Setup Complete!                                  ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                      ║${NC}"
echo -e "${GREEN}║  Next steps:                                         ║${NC}"
echo -e "${GREEN}║  1. Edit .env with your Telegram/Groq keys           ║${NC}"
echo -e "${GREEN}║  2. source venv/bin/activate                         ║${NC}"
echo -e "${GREEN}║  3. python scripts/download_data.py                  ║${NC}"
echo -e "${GREEN}║  4. python scripts/run_backtest.py                   ║${NC}"
echo -e "${GREEN}║  5. cd bot && pytest tests/ -v                       ║${NC}"
echo -e "${GREEN}║  6. freqtrade trade \\                                ║${NC}"
echo -e "${GREEN}║        --config bot/config.paper.json \\              ║${NC}"
echo -e "${GREEN}║        --strategy AIRSIStrategy                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
