.PHONY: setup test test-unit test-integration demo demo-snyk demo-sonar demo-blackduck demo-ado-defect demo-ado-story demo-sample demo-sample-snyk demo-sample-sonar demo-sample-blackduck demo-sample-ado-defect demo-sample-ado-story lint clean help

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
	@echo "  make demo               Run all 5 demo scenarios (mock mode)"
	@echo "  make demo-snyk          Run Snyk CVE scenario (mock)"
	@echo "  make demo-sonar         Run Sonar SAST scenario (mock)"
	@echo "  make demo-blackduck     Run BlackDuck license scenario (mock)"
	@echo "  make demo-ado-defect    Run ADO defect scenario (mock)"
	@echo "  make demo-ado-story     Run ADO user story scenario (mock)"
	@echo "  make demo-sample        Run all 5 scenarios with real LLM (needs GITHUB_TOKEN)"
	@echo "  make demo-sample-snyk   Run Snyk scenario with real LLM"
	@echo "  make lint               Run ruff linter"
	@echo "  make clean              Remove build artifacts and .venv"

setup:
	@echo "🔧 Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "📦 Installing packages..."
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -e "conductor-core[dev]" --quiet
	$(PIP) install -e "conductor-agents[dev]" --quiet
	$(PIP) install -e "conductor-integrations[dev]" --quiet
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
		source $(VENV)/bin/activate && CONDUCTOR_PROVIDER_MODE=mock $(PYTHON) consumer-showcase/main.py --scenario $$scenario || exit 1; \
	done
	@echo ""
	@echo "✅ All 5 scenarios completed"

demo-snyk:
	@source $(VENV)/bin/activate && CONDUCTOR_PROVIDER_MODE=mock $(PYTHON) consumer-showcase/main.py --scenario snyk

demo-sonar:
	@source $(VENV)/bin/activate && CONDUCTOR_PROVIDER_MODE=mock $(PYTHON) consumer-showcase/main.py --scenario sonar

demo-blackduck:
	@source $(VENV)/bin/activate && CONDUCTOR_PROVIDER_MODE=mock $(PYTHON) consumer-showcase/main.py --scenario blackduck

demo-ado-defect:
	@source $(VENV)/bin/activate && CONDUCTOR_PROVIDER_MODE=mock $(PYTHON) consumer-showcase/main.py --scenario ado-defect

demo-ado-story:
	@source $(VENV)/bin/activate && CONDUCTOR_PROVIDER_MODE=mock $(PYTHON) consumer-showcase/main.py --scenario ado-story

demo-sample:
	@for scenario in snyk sonar blackduck ado-defect ado-story; do \
		echo ""; \
		echo "═══════════════════════════════════════"; \
		echo "  [sample mode] scenario: $$scenario"; \
		echo "═══════════════════════════════════════"; \
		$(PYTHON) consumer-showcase/main.py --scenario $$scenario --mode sample --store /tmp/runs_sample.db || exit 1; \
	done
	@echo ""
	@echo "✅ All 5 sample scenarios completed (real LLM)"

demo-sample-snyk:
	@$(PYTHON) consumer-showcase/main.py --scenario snyk --mode sample --store /tmp/runs_sample.db

demo-sample-sonar:
	@$(PYTHON) consumer-showcase/main.py --scenario sonar --mode sample --store /tmp/runs_sample.db

demo-sample-blackduck:
	@$(PYTHON) consumer-showcase/main.py --scenario blackduck --mode sample --store /tmp/runs_sample.db

demo-sample-ado-defect:
	@$(PYTHON) consumer-showcase/main.py --scenario ado-defect --mode sample --store /tmp/runs_sample.db

demo-sample-ado-story:
	@$(PYTHON) consumer-showcase/main.py --scenario ado-story --mode sample --store /tmp/runs_sample.db

lint:
	$(VENV)/bin/ruff check conductor-core conductor-integrations consumer-showcase
	$(VENV)/bin/ruff format --check conductor-core conductor-integrations consumer-showcase

clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"
