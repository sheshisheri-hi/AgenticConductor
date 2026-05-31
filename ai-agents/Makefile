.PHONY: setup test test-unit test-integration demo demo-snyk demo-sonar demo-blackduck demo-ado-defect demo-ado-story lint clean help

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
	@echo "  make demo-snyk          Run Snyk CVE scenario"
	@echo "  make demo-sonar         Run Sonar SAST scenario"
	@echo "  make demo-blackduck     Run BlackDuck license scenario"
	@echo "  make demo-ado-defect    Run ADO defect scenario"
	@echo "  make demo-ado-story     Run ADO user story scenario"
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
	@bash scripts/run_tests.sh

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
		bash scripts/run_demo.sh $$scenario || exit 1; \
	done
	@echo ""
	@echo "✅ All 5 scenarios completed"

demo-snyk:
	@bash scripts/run_demo.sh snyk

demo-sonar:
	@bash scripts/run_demo.sh sonar

demo-blackduck:
	@bash scripts/run_demo.sh blackduck

demo-ado-defect:
	@bash scripts/run_demo.sh ado-defect

demo-ado-story:
	@bash scripts/run_demo.sh ado-story

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
