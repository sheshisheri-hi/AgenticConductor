#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-time environment bootstrap
# Usage: bash scripts/setup.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔧 Conductor setup starting..."
echo "   Root: $ROOT_DIR"

# --- Python version check ---
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_MAJOR=3
REQUIRED_MINOR=11

MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$MAJOR" -lt "$REQUIRED_MAJOR" ] || ([ "$MAJOR" -eq "$REQUIRED_MAJOR" ] && [ "$MINOR" -lt "$REQUIRED_MINOR" ]); then
  echo "❌ Python $REQUIRED_MAJOR.$REQUIRED_MINOR+ required. Found: $PYTHON_VERSION"
  exit 1
fi
echo "   Python: $PYTHON_VERSION ✅"

# --- GitHub CLI + Copilot extension check ---
if ! command -v gh &>/dev/null; then
  echo "⚠️  GitHub CLI not found."
  echo "   Install: brew install gh"
  echo "   Then:    gh auth login"
  echo "   Then:    gh extension install github/gh-copilot"
  exit 1
fi
echo "   gh CLI: $(gh --version | head -1) ✅"

if ! gh extension list 2>/dev/null | grep -q "copilot"; then
  echo "⚠️  GitHub Copilot CLI extension not installed."
  echo "   Run: gh extension install github/gh-copilot"
  exit 1
fi
echo "   Copilot extension: ✅"

# --- Create virtual environment ---
cd "$ROOT_DIR"
if [ ! -d ".venv" ]; then
  echo "📦 Creating .venv..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip --quiet

# --- Install packages in editable (dev) mode ---
echo "📦 Installing conductor-core..."
pip install -e "conductor-core[dev]" --quiet

echo "📦 Installing conductor-integrations..."
pip install -e "conductor-integrations[dev]" --quiet

echo "📦 Installing consumer-showcase..."
pip install -e "consumer-showcase[dev]" --quiet

# --- .env setup ---
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "📝 Created .env from .env.example"
  echo "   ➜ Open .env and set GITHUB_TOKEN to your GitHub PAT with Copilot subscription"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env — set GITHUB_TOKEN"
echo "  2. source .venv/bin/activate"
echo "  3. make demo"
echo ""
