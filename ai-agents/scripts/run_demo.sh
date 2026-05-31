#!/usr/bin/env bash
# =============================================================================
# run_demo.sh — Run a consumer-showcase demo scenario
# Usage: bash scripts/run_demo.sh [snyk|sonar|blackduck|ado-defect|ado-story]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

SCENARIO=${1:-snyk}
VALID_SCENARIOS=("snyk" "sonar" "blackduck" "ado-defect" "ado-story")

# Validate scenario
VALID=false
for s in "${VALID_SCENARIOS[@]}"; do
  [ "$s" = "$SCENARIO" ] && VALID=true
done

if [ "$VALID" = false ]; then
  echo "❌ Unknown scenario: $SCENARIO"
  echo "   Valid scenarios: ${VALID_SCENARIOS[*]}"
  exit 1
fi

# Load .env if present
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

source .venv/bin/activate

echo "▶ Running scenario: $SCENARIO (CONDUCTOR_PROVIDER_MODE=mock)"
echo ""

CONDUCTOR_PROVIDER_MODE=mock \
python consumer-showcase/main.py --scenario "$SCENARIO"
