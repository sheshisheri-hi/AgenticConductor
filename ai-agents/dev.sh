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
    ok "Done. View results:"
    echo "    ./dev.sh runs"
    echo "    ./dev.sh plan SNYK-001-demo"
    ;;

  demo-all)
    ensure_venv
    log "Running all 5 mock scenarios..."
    "$PYTHON" consumer-showcase/main.py --all --mode mock --store /tmp/runs.db
    echo ""
    ok "Done. View results: ./dev.sh runs"
    ;;

  sample)
    ensure_venv
    log "Checking token before running sample mode..."
    "$VENV/bin/conductor" check
    log "Running sample demo (real LLM) — scenario: $SCENARIO"
    "$PYTHON" consumer-showcase/main.py --scenario "$SCENARIO" --mode sample --store /tmp/runs_sample.db
    echo ""
    ok "Done. View results:"
    echo "    ./dev.sh runs sample"
    echo "    ./dev.sh plan <RUN_ID> sample"
    ;;

  sample-all)
    ensure_venv
    log "Checking token before running sample mode..."
    "$VENV/bin/conductor" check
    log "Running all 5 sample scenarios (real LLM)..."
    "$PYTHON" consumer-showcase/main.py --all --mode sample --store /tmp/runs_sample.db
    echo ""
    ok "Done. View results: ./dev.sh runs sample"
    ;;

  test)
    ensure_venv
    log "Running unit tests..."
    (cd conductor-core && ../"$VENV/bin/pytest" tests/unit -q --tb=short)
    (cd conductor-integrations && ../"$VENV/bin/pytest" tests/unit -q --tb=short)
    (cd consumer-showcase && ../"$VENV/bin/pytest" tests/unit -q --tb=short)
    ok "All tests passed."
    ;;

  clean)
    # ./dev.sh clean         → remove venv + build artifacts
    # ./dev.sh clean db      → remove SQLite DBs only
    # ./dev.sh clean all     → remove everything
    WHAT="${2:-venv}"
    if [[ "$WHAT" == "db" ]]; then
      rm -f /tmp/runs.db /tmp/runs_sample.db conductor_runs.db
      ok "SQLite databases removed"
    elif [[ "$WHAT" == "all" ]]; then
      rm -rf "$VENV"
      find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
      find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
      rm -f /tmp/runs.db /tmp/runs_sample.db conductor_runs.db
      ok "Full clean done (venv + build artifacts + databases)"
    else
      rm -rf "$VENV"
      find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
      find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
      ok "Cleaned venv + build artifacts (databases kept)"
      echo "  Run './dev.sh clean db' to also remove SQLite databases"
    fi
    ;;

  runs)
    # ./dev.sh runs          → list mock runs
    # ./dev.sh runs sample   → list sample runs
    ensure_venv
    STORE="${2:-/tmp/runs.db}"
    [[ "${2:-}" == "sample" ]] && STORE="/tmp/runs_sample.db"
    "$VENV/bin/conductor" runs --store "$STORE"
    ;;

  plan)
    # ./dev.sh plan <RUN_ID>          → show plan from mock db
    # ./dev.sh plan <RUN_ID> sample   → show plan from sample db
    ensure_venv
    RUN_ID="${2:-}"
    STORE="/tmp/runs.db"
    [[ "${3:-}" == "sample" ]] && STORE="/tmp/runs_sample.db"
    if [ -z "$RUN_ID" ]; then
      echo "Usage: ./dev.sh plan <RUN_ID> [sample]"
      exit 1
    fi
    "$VENV/bin/conductor" plan "$RUN_ID" --store "$STORE"
    ;;

  trace)
    # ./dev.sh trace <RUN_ID>         → show trace from mock db
    # ./dev.sh trace <RUN_ID> sample  → show trace from sample db
    ensure_venv
    RUN_ID="${2:-}"
    STORE="/tmp/runs.db"
    [[ "${3:-}" == "sample" ]] && STORE="/tmp/runs_sample.db"
    if [ -z "$RUN_ID" ]; then
      echo "Usage: ./dev.sh trace <RUN_ID> [sample]"
      exit 1
    fi
    "$VENV/bin/conductor" trace "$RUN_ID" --store "$STORE"
    ;;

  *)
    echo ""
    echo "Usage: ./dev.sh <command> [args]"
    echo ""
    echo "  Setup & verification:"
    echo "    ./dev.sh setup                  — create venv + install all packages"
    echo "    ./dev.sh check                  — verify Copilot token + access"
    echo ""
    echo "  Run demos (no token needed):"
    echo "    ./dev.sh demo [scenario]        — mock demo (default: snyk)"
    echo "    ./dev.sh demo-all               — all 5 mock scenarios"
    echo ""
    echo "  Run with real LLM (needs GITHUB_COPILOT_TOKEN):"
    echo "    ./dev.sh sample [scenario]      — real LLM demo"
    echo "    ./dev.sh sample-all             — all 5 real LLM scenarios"
    echo ""
    echo "  View results:"
    echo "    ./dev.sh runs                   — list mock runs"
    echo "    ./dev.sh runs sample            — list sample runs"
    echo "    ./dev.sh plan <RUN_ID>          — show fix plan"
    echo "    ./dev.sh trace <RUN_ID>         — show agent trace"
    echo ""
    echo "  Other:"
    echo "    ./dev.sh test                   — run all unit tests"
    echo "    ./dev.sh clean                  — remove venv + build artifacts"
    echo "    ./dev.sh clean db               — remove SQLite databases (/tmp/runs*.db)"
    echo "    ./dev.sh clean all              — remove everything (venv + artifacts + DBs)"
    echo ""
    echo "  Scenarios: snyk sonar blackduck ado-defect ado-story"
    exit 1
    ;;
esac
