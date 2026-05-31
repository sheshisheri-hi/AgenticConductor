#!/usr/bin/env bash
# dev.sh — One-shot developer setup + run script
#
# Usage:
#   ./dev.sh                                           # setup venv + run mock demo (snyk)
#   ./dev.sh setup                                     # setup only (venv + install all packages)
#   ./dev.sh demo [scenario] [workflow]                # mock demo — StubLLM + fixtures, no token needed
#   ./dev.sh sample [scenario] [workflow]              # sample demo — real LLM + fixtures, stub git
#   ./dev.sh sample [scenario] [workflow] integration  # integration — real LLM + fixtures + REAL git/PRs
#   ./dev.sh check                                     # verify token + Copilot access
#   ./dev.sh test                                      # run all unit tests
#   ./dev.sh clean-integration                         # delete conductor/* branches + open PRs in test repos
#
# Scenarios: snyk sonar blackduck ado-defect ado-story (default: snyk)
# Workflows: default | security | adversarial | ado | execute (default: default)
# Provider modes: mock | sample | integration | live (default depends on command)

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
WORKFLOW_ARG="${3:-default}"
PROVIDER_ARG="${4:-}"  # optional: integration | live (overrides default for the command)

# Resolve workflow YAML path from short name
# Usage: WORKFLOW_FILE=$(resolve_workflow "adversarial")
resolve_workflow() {
  local name="${1:-default}"
  case "$name" in
    default)   echo "consumer-showcase/config/workflow.yaml" ;;
    security)  echo "consumer-showcase/config/workflow_security.yaml" ;;
    adversarial) echo "consumer-showcase/config/workflow_adversarial.yaml" ;;
    ado)       echo "consumer-showcase/config/workflow_ado.yaml" ;;
    execute)   echo "consumer-showcase/config/workflow_execute.yaml" ;;
    *)
      # Allow passing a direct path too
      if [ -f "$name" ]; then echo "$name"
      else err "Unknown workflow: $name. Valid: default, security, adversarial, ado, execute"
      fi
      ;;
  esac
}

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
    WFILE=$(resolve_workflow "$WORKFLOW_ARG")
    log "Running mock demo — scenario: $SCENARIO  workflow: $WORKFLOW_ARG"
    "$PYTHON" consumer-showcase/main.py --scenario "$SCENARIO" --mode mock --workflow "$WFILE" --store /tmp/runs.db
    echo ""
    ok "Done. View results:"
    echo "    ./dev.sh runs"
    echo "    ./dev.sh plan SNYK-001-demo"
    ;;

  demo-all)
    ensure_venv
    WFILE=$(resolve_workflow "$WORKFLOW_ARG")
    log "Running all 5 mock scenarios (workflow: $WORKFLOW_ARG)..."
    "$PYTHON" consumer-showcase/main.py --all --mode mock --workflow "$WFILE" --store /tmp/runs.db
    echo ""
    ok "Done. View results: ./dev.sh runs"
    ;;

  sample)
    ensure_venv
    WFILE=$(resolve_workflow "$WORKFLOW_ARG")
    PMODE="${PROVIDER_ARG:-sample}"
    if [[ "$PMODE" != "sample" && "$PMODE" != "integration" && "$PMODE" != "live" ]]; then
      err "Unknown provider mode '$PMODE'. Valid 4th arg: sample | integration | live"
    fi
    log "Checking token before running $PMODE mode..."
    "$VENV/bin/conductor" check
    log "Running $PMODE demo (real LLM) — scenario: $SCENARIO  workflow: $WORKFLOW_ARG  mode: $PMODE"
    "$PYTHON" consumer-showcase/main.py --scenario "$SCENARIO" --mode "$PMODE" --workflow "$WFILE" --store /tmp/runs_sample.db
    echo ""
    ok "Done. View results:"
    echo "    ./dev.sh runs sample"
    echo "    ./dev.sh plan <RUN_ID> sample"
    ;;

  sample-all)
    ensure_venv
    WFILE=$(resolve_workflow "$WORKFLOW_ARG")
    PMODE="${PROVIDER_ARG:-sample}"
    if [[ "$PMODE" != "sample" && "$PMODE" != "integration" && "$PMODE" != "live" ]]; then
      err "Unknown provider mode '$PMODE'. Valid 4th arg: sample | integration | live"
    fi
    log "Checking token before running $PMODE mode..."
    "$VENV/bin/conductor" check
    log "Running all 5 $PMODE scenarios (real LLM, workflow: $WORKFLOW_ARG)..."
    "$PYTHON" consumer-showcase/main.py --all --mode "$PMODE" --workflow "$WFILE" --store /tmp/runs_sample.db
    echo ""
    ok "Done. View results: ./dev.sh runs sample"
    ;;

  test)
    ensure_venv
    log "Running unit tests..."
    (cd conductor-core && "$VENV/bin/pytest" tests/unit -q --tb=short)
    (cd conductor-integrations && "$VENV/bin/pytest" tests/unit -q --tb=short)
    (cd consumer-showcase && "$VENV/bin/pytest" tests/unit -q --tb=short)
    ok "All tests passed."
    ;;

  test-integration)
    ensure_venv
    log "Running integration tests (all 5 workflows × all scenarios)..."
    (cd consumer-showcase && "$VENV/bin/pytest" tests/integration -v --tb=short)
    ok "All integration tests passed."
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

  clean-integration)
    # Delete all conductor/* branches + open PRs from test repos after integration testing
    ensure_venv
    ORG="${GITHUB_ORG:-sheshisheri-hi}"
    REPO="${CONDUCTOR_INTEGRATION_REPO:-conductor-sample-app}"
    TOKEN="${GITHUB_TOKEN:-${CONDUCTOR_GITHUB_TOKEN:-}}"
    if [ -z "$TOKEN" ]; then
      err "GITHUB_TOKEN or CONDUCTOR_GITHUB_TOKEN must be set to clean integration branches"
    fi
    log "Cleaning conductor/* branches and open PRs in $ORG/$REPO..."
    # List and close open PRs with conductor/* head branches
    OPEN_PRS=$(curl -sf -H "Authorization: token $TOKEN" \
      "https://api.github.com/repos/$ORG/$REPO/pulls?state=open&per_page=100" \
      | "$PYTHON" -c "import sys,json; [print(p['number'],p['head']['ref']) for p in json.load(sys.stdin) if p['head']['ref'].startswith('conductor/')]" 2>/dev/null || true)
    if [ -n "$OPEN_PRS" ]; then
      while IFS=' ' read -r pr_num branch_name; do
        log "Closing PR #$pr_num ($branch_name)..."
        curl -sf -X PATCH -H "Authorization: token $TOKEN" \
          "https://api.github.com/repos/$ORG/$REPO/pulls/$pr_num" \
          -d '{"state":"closed"}' > /dev/null
      done <<< "$OPEN_PRS"
    fi
    # Delete conductor/* branches
    BRANCHES=$(curl -sf -H "Authorization: token $TOKEN" \
      "https://api.github.com/repos/$ORG/$REPO/branches?per_page=100" \
      | "$PYTHON" -c "import sys,json; [print(b['name']) for b in json.load(sys.stdin) if b['name'].startswith('conductor/')]" 2>/dev/null || true)
    if [ -n "$BRANCHES" ]; then
      while IFS= read -r branch_name; do
        log "Deleting branch $branch_name..."
        curl -sf -X DELETE -H "Authorization: token $TOKEN" \
          "https://api.github.com/repos/$ORG/$REPO/git/refs/heads/$branch_name" > /dev/null
      done <<< "$BRANCHES"
    fi
    ok "Integration cleanup done for $ORG/$REPO"
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
    echo "    ./dev.sh demo [scenario] [workflow]    — mock demo (default: snyk, default workflow)"
    echo "    ./dev.sh demo snyk adversarial         — mock with adversarial workflow (parallel gate)"
    echo "    ./dev.sh demo snyk security            — mock with security workflow"
    echo "    ./dev.sh demo ado-defect ado           — mock with ADO workflow"
    echo "    ./dev.sh demo-all [workflow]           — all 5 mock scenarios"
    echo ""
    echo "  Run with real LLM (needs GITHUB_TOKEN):"
    echo "    ./dev.sh sample [scenario] [workflow]              — real LLM + fixture data, stub git"
    echo "    ./dev.sh sample snyk adversarial                   — real LLM + adversarial workflow"
    echo "    ./dev.sh sample snyk default integration           — real LLM + REAL branches/PRs in test repo"
    echo "    ./dev.sh sample-all [workflow]                     — all 5 real LLM scenarios"
    echo "    ./dev.sh sample-all default integration            — all 5 with real git operations"
    echo ""
    echo "  View results:"
    echo "    ./dev.sh runs                   — list mock runs"
    echo "    ./dev.sh runs sample            — list sample runs"
    echo "    ./dev.sh plan <RUN_ID>          — show fix plan"
    echo "    ./dev.sh trace <RUN_ID>         — show agent trace"
    echo ""
    echo "  Integration test cleanup:"
    echo "    ./dev.sh clean-integration      — delete conductor/* branches + PRs in test repo"
    echo ""
    echo "  Other:"
    echo "    ./dev.sh test                   — run all unit tests"
    echo "    ./dev.sh test-integration       — run integration tests (all 5 workflows × all scenarios)"
    echo "    ./dev.sh clean                  — remove venv + build artifacts"
    echo "    ./dev.sh clean db               — remove SQLite databases (/tmp/runs*.db)"
    echo "    ./dev.sh clean all              — remove everything (venv + artifacts + DBs)"
    echo ""
    echo "  Scenarios: snyk sonar blackduck ado-defect ado-story"
    echo "  Workflows: default | security | adversarial | ado | execute"
    echo "  Modes:     mock | sample | integration | live"
    exit 1
    ;;
esac
