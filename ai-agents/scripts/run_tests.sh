#!/usr/bin/env bash
# =============================================================================
# run_tests.sh — Run full test suite
# Usage: bash scripts/run_tests.sh [unit|integration|all]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

MODE=${1:-all}
source .venv/bin/activate

echo "═══════════════════════════════════════════════"
echo "  Conductor Test Suite — mode: $MODE"
echo "═══════════════════════════════════════════════"

PASS=0
FAIL=0

run_suite() {
  local name=$1
  local pkg_dir=$2
  local test_path=$3
  local extra_flags=${4:-}
  echo ""
  echo "▶ $name"
  if (cd "$pkg_dir" && python -m pytest "$test_path" -v --tb=short $extra_flags); then
    echo "  ✅ $name passed"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name FAILED"
    FAIL=$((FAIL + 1))
  fi
}

if [ "$MODE" = "unit" ] || [ "$MODE" = "all" ]; then
  run_suite "conductor-core unit" "conductor-core" "tests/unit"
  run_suite "conductor-integrations unit" "conductor-integrations" "tests/unit"
  run_suite "consumer-showcase unit" "consumer-showcase" "tests/unit"
fi

if [ "$MODE" = "integration" ] || [ "$MODE" = "all" ]; then
  if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo ""
    echo "⚠️  Skipping integration tests — GITHUB_TOKEN not set"
    echo "   Set GITHUB_TOKEN in .env to run integration tests"
  else
    run_suite "consumer-showcase integration" "consumer-showcase" "tests/integration" "-s"
  fi
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════════════════"

[ "$FAIL" -eq 0 ]
