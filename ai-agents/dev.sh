#!/usr/bin/env bash
# dev.sh — One-shot developer setup + run script
#
# Usage:
#   ./dev.sh                        # setup venv + run mock demo (snyk)
#   ./dev.sh setup                  # setup only (venv + install all packages)
#   ./dev.sh demo [scenario]        # run mock demo (no token needed)
#   ./dev.sh sample [scenario]      # run sample demo (needs GITHUB_COPILOT_TOKEN)
#   ./dev.sh check                  # verify token + Copilot access
#   ./dev.sh test                   # run all unit tests
#
# Scenarios: snyk sonar blackduck ado-defect ado-story (default: snyk)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

# ── helpers ────────────────────────────────────────────────────────────────
log()  { echo ""; echo "▶  $*"; }
ok()   { echo "✅  $*"; }
err()  { echo "❌  $*" >&2; exit 1; }

setup() {
  log "Creating virtual environment..."
  python3 -m venv "$VENV"

  log "Installing packages (core → agents → integrations → showcase → cli)..."
  "$PIP" install --upgrade pip --quiet
  "$PIP" install -e "conductor-core[dev]" --quiet
  "$PIP" install -e "conductor-agents[dev]" --quiet
  "$PIP" install -e "conductor-integrations[dev,copilot]" --quiet
  "$PIP" install -e "consumer-showcase[dev]" --quiet
  "$PIP" install -e "conductor-cli[dev]" --quiet

  if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝  Created .env from .env.example — add CONDUCTOR_GITHUB_TOKEN for sample mode"
  fi

  ok "Setup complete."
  echo ""
  echo "  Next steps:"
  echo "    ./dev.sh demo           — run mock demo (no token)"
  echo "    ./dev.sh sample         — run real LLM demo (needs GITHUB_COPILOT_TOKEN)"
  echo "    ./dev.sh check          — verify Copilot token + access"
}

ensure_venv() {
  if [ ! -f "$PYTHON" ]; then
    log "Virtual environment not found — running setup first..."
    setup
  fi
}

# ── commands ───────────────────────────────────────────────────────────────
CMD="${1:-demo}"
SCENARIO="${2:-snyk}"

case "$CMD" in
  setup)
    setup
    ;;

  check)
    ensure_venv
    log "Checking Copilot token and access..."
    "$VENV/bin/conductor" check
    ;;

  demo)
    ensure_venv
    log "Running mock demo — scenario: $SCENARIO"
    "$PYTHON" consumer-showcase/main.py --scenario "$SCENARIO" --mode mock --store /tmp/runs.db
    echo ""
    ok "Done."
    echo "  View results (activate venv first or use full path):"
    echo "    source .venv/bin/activate && conductor runs --store /tmp/runs.db"
    echo "    source .venv/bin/activate && conductor plan SNYK-001-demo --store /tmp/runs.db"
    ;;

  demo-all)
    ensure_venv
    log "Running all 5 mock scenarios..."
    "$PYTHON" consumer-showcase/main.py --all --mode mock --store /tmp/runs.db
    echo ""
    ok "Done. View results: conductor runs --store /tmp/runs.db"
    ;;

  sample)
    ensure_venv
    log "Checking token before running sample mode..."
    "$VENV/bin/conductor" check
    log "Running sample demo (real LLM) — scenario: $SCENARIO"
    "$PYTHON" consumer-showcase/main.py --scenario "$SCENARIO" --mode sample --store /tmp/runs_sample.db
    echo ""
    ok "Done."
    echo "  View results:"
    echo "    source .venv/bin/activate && conductor runs --store /tmp/runs_sample.db"
    echo "    source .venv/bin/activate && conductor plan --store /tmp/runs_sample.db"
    ;;

  sample-all)
    ensure_venv
    log "Checking token before running sample mode..."
    "$VENV/bin/conductor" check
    log "Running all 5 sample scenarios (real LLM)..."
    "$PYTHON" consumer-showcase/main.py --all --mode sample --store /tmp/runs_sample.db
    echo ""
    ok "Done. View results: conductor runs --store /tmp/runs_sample.db"
    ;;

  test)
    ensure_venv
    log "Running unit tests..."
    (cd conductor-core && ../"$VENV/bin/pytest" tests/unit -q --tb=short)
    (cd conductor-integrations && ../"$VENV/bin/pytest" tests/unit -q --tb=short)
    (cd consumer-showcase && ../"$VENV/bin/pytest" tests/unit -q --tb=short)
    ok "All tests passed."
    ;;

  *)
    echo "Usage: ./dev.sh [setup|check|demo|demo-all|sample|sample-all|test] [scenario]"
    echo "Scenarios: snyk sonar blackduck ado-defect ado-story"
    exit 1
    ;;
esac
