.PHONY: setup test test-unit test-integration demo demo-snyk demo-sonar demo-blackduck demo-ado-defect demo-ado-story demo-adversarial demo-security demo-ado-workflow demo-sample demo-sample-snyk demo-sample-sonar demo-sample-blackduck demo-sample-ado-defect demo-sample-ado-story demo-sample-adversarial demo-sample-security lint clean clean-db clean-all help

WF_DEFAULT    := consumer-showcase/config/workflow.yaml
WF_SECURITY   := consumer-showcase/config/workflow_security.yaml
WF_ADVERSARIAL:= consumer-showcase/config/workflow_adversarial.yaml
WF_ADO        := consumer-showcase/config/workflow_ado.yaml
WF_EXECUTE    := consumer-showcase/config/workflow_execute.yaml

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

help:
	@echo "Conductor — Multi-Agent Workflow Framework"
	@echo ""
	@echo "Usage:"
	@echo "  make setup              One-time setup: venv + install all packages"
	@echo "  make test               Run all unit + integration tests"
	@echo "  make test-unit          Run unit tests only (no LLM token required)"
	@echo "  make test-integration   Run integration tests (requires GITHUB_TOKEN)"
	@echo "  make demo               Run all 5 demo scenarios (mock, default workflow)"
	@echo "  make demo-snyk          Run Snyk CVE scenario (mock)"
	@echo "  make demo-sonar         Run Sonar SAST scenario (mock)"
	@echo "  make demo-blackduck     Run BlackDuck license scenario (mock)"
	@echo "  make demo-ado-defect    Run ADO defect scenario (mock)"
	@echo "  make demo-ado-story     Run ADO user story scenario (mock)"
	@echo "  make demo-adversarial   Run snyk with adversarial workflow (parallel gate)"
	@echo "  make demo-security      Run snyk with security-only workflow"
	@echo "  make demo-ado-workflow  Run ado-defect with ADO workflow"
	@echo "  make demo-sample        Run all 5 scenarios with real LLM (needs GITHUB_TOKEN)"
	@echo "  make demo-sample-snyk   Run Snyk scenario with real LLM"
	@echo "  make demo-sample-adversarial  Run Snyk + adversarial workflow with real LLM"
	@echo "  make demo-sample-security     Run Snyk + security workflow with real LLM"
	@echo "  make lint               Run ruff linter"
	@echo "  make clean              Remove build artifacts and .venv"

setup:
	@echo "🔧 Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "📦 Installing packages..."
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -e "conductor-core[dev]" --quiet
	$(PIP) install -e "conductor-agents[dev]" --quiet
	$(PIP) install -e "conductor-integrations[dev,copilot]" --quiet
	$(PIP) install -e "consumer-showcase[dev]" --quiet
	$(PIP) install -e "conductor-cli[dev]" --quiet
	@if [ ! -f .env ]; then cp .env.example .env && echo "📝 Created .env from .env.example — add your GITHUB_TOKEN"; fi
	@echo "✅ Setup complete. Run: make demo"

test:
	@echo "═══════════════════════════════════════════════"
	@echo "  Conductor Test Suite"
	@echo "═══════════════════════════════════════════════"
	@echo ""
	@echo "▶ conductor-core unit"
	@(cd conductor-core && ../$(PYTEST) tests/unit -q --tb=short)
	@echo ""
	@echo "▶ conductor-integrations unit"
	@(cd conductor-integrations && ../$(PYTEST) tests/unit -q --tb=short)
	@echo ""
	@echo "▶ consumer-showcase unit"
	@(cd consumer-showcase && ../$(PYTEST) tests/unit -q --tb=short)
	@echo ""
	@echo "✅ All unit tests passed"

test-unit:
	@echo "=== conductor-core ===" && (cd conductor-core && ../$(PYTEST) tests/unit -q --tb=short)
	@echo "=== conductor-integrations ===" && (cd conductor-integrations && ../$(PYTEST) tests/unit -q --tb=short)
	@echo "=== consumer-showcase ===" && (cd consumer-showcase && ../$(PYTEST) tests/unit -q --tb=short)

test-integration:
	@(cd consumer-showcase && ../$(PYTEST) tests/integration -v --tb=short)

demo:
	@for scenario in snyk sonar blackduck ado-defect ado-story; do \
		echo ""; \
		echo "═══════════════════════════════════════"; \
		echo "  Running scenario: $$scenario"; \
		echo "═══════════════════════════════════════"; \
		$(PYTHON) consumer-showcase/main.py --scenario $$scenario --mode mock --workflow $(WF_DEFAULT) --store /tmp/runs.db || exit 1; \
	done
	@echo ""
	@echo "✅ All 5 scenarios completed"

demo-snyk:
	@$(PYTHON) consumer-showcase/main.py --scenario snyk --mode mock --workflow $(WF_DEFAULT) --store /tmp/runs.db

demo-sonar:
	@$(PYTHON) consumer-showcase/main.py --scenario sonar --mode mock --workflow $(WF_DEFAULT) --store /tmp/runs.db

demo-blackduck:
	@$(PYTHON) consumer-showcase/main.py --scenario blackduck --mode mock --workflow $(WF_DEFAULT) --store /tmp/runs.db

demo-ado-defect:
	@$(PYTHON) consumer-showcase/main.py --scenario ado-defect --mode mock --workflow $(WF_DEFAULT) --store /tmp/runs.db

demo-ado-story:
	@$(PYTHON) consumer-showcase/main.py --scenario ado-story --mode mock --workflow $(WF_DEFAULT) --store /tmp/runs.db

demo-adversarial:
	@echo "▶ Running snyk with adversarial workflow (parallel gate)..."
	@$(PYTHON) consumer-showcase/main.py --scenario snyk --mode mock --workflow $(WF_ADVERSARIAL) --store /tmp/runs.db

demo-security:
	@echo "▶ Running snyk with security-only workflow..."
	@$(PYTHON) consumer-showcase/main.py --scenario snyk --mode mock --workflow $(WF_SECURITY) --store /tmp/runs.db

demo-ado-workflow:
	@echo "▶ Running ado-defect with ADO workflow..."
	@$(PYTHON) consumer-showcase/main.py --scenario ado-defect --mode mock --workflow $(WF_ADO) --store /tmp/runs.db

demo-sample:
	@for scenario in snyk sonar blackduck ado-defect ado-story; do \
		echo ""; \
		echo "═══════════════════════════════════════"; \
		echo "  [sample mode] scenario: $$scenario"; \
		echo "═══════════════════════════════════════"; \
		$(PYTHON) consumer-showcase/main.py --scenario $$scenario --mode sample --workflow $(WF_DEFAULT) --store /tmp/runs_sample.db || exit 1; \
	done
	@echo ""
	@echo "✅ All 5 sample scenarios completed (real LLM)"

demo-sample-snyk:
	@$(PYTHON) consumer-showcase/main.py --scenario snyk --mode sample --workflow $(WF_DEFAULT) --store /tmp/runs_sample.db

demo-sample-sonar:
	@$(PYTHON) consumer-showcase/main.py --scenario sonar --mode sample --workflow $(WF_DEFAULT) --store /tmp/runs_sample.db

demo-sample-blackduck:
	@$(PYTHON) consumer-showcase/main.py --scenario blackduck --mode sample --workflow $(WF_DEFAULT) --store /tmp/runs_sample.db

demo-sample-ado-defect:
	@$(PYTHON) consumer-showcase/main.py --scenario ado-defect --mode sample --workflow $(WF_DEFAULT) --store /tmp/runs_sample.db

demo-sample-ado-story:
	@$(PYTHON) consumer-showcase/main.py --scenario ado-story --mode sample --workflow $(WF_DEFAULT) --store /tmp/runs_sample.db

demo-sample-adversarial:
	@echo "▶ Running snyk + adversarial workflow (real LLM)..."
	@$(PYTHON) consumer-showcase/main.py --scenario snyk --mode sample --workflow $(WF_ADVERSARIAL) --store /tmp/runs_sample.db

demo-sample-security:
	@echo "▶ Running snyk + security workflow (real LLM)..."
	@$(PYTHON) consumer-showcase/main.py --scenario snyk --mode sample --workflow $(WF_SECURITY) --store /tmp/runs_sample.db

lint:
	$(VENV)/bin/ruff check conductor-core conductor-integrations consumer-showcase
	$(VENV)/bin/ruff format --check conductor-core conductor-integrations consumer-showcase

clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned (venv + build artifacts)"

clean-db:
	rm -f /tmp/runs.db /tmp/runs_sample.db conductor_runs.db
	@echo "✅ SQLite databases removed"

clean-all: clean clean-db
	@echo "✅ Full clean done"
