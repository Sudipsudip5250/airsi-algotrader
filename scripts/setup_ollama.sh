#!/usr/bin/env bash
# Setup Ollama (local AI) on Linux/Mac
# Run: bash scripts/setup_ollama.sh

set -euo pipefail

MODEL="${1:-mistral}"

echo ""
echo "🤖  Ollama Setup Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Install Ollama ──────────────────────────────────────────────────
if command -v ollama &>/dev/null; then
  echo "✅  Ollama already installed: $(ollama --version)"
else
  echo "📥  Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
  echo "✅  Ollama installed."
fi

# ── Start Ollama service ────────────────────────────────────────────
echo "🚀  Starting Ollama service..."
if pgrep -x "ollama" > /dev/null; then
  echo "   (Already running)"
else
  ollama serve &
  sleep 3
  echo "   Started."
fi

# ── Pull model ──────────────────────────────────────────────────────
echo "📦  Pulling model: $MODEL (~4GB, may take a few minutes)..."
ollama pull "$MODEL"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅  Ollama is ready with model: $MODEL"
echo "   Test it: ollama run $MODEL 'Hello!'"
echo "   API URL: http://localhost:11434"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
