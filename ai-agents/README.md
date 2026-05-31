# Conductor — Generic Multi-Agent Workflow Framework

A reusable orchestration framework for building multi-agent AI workflows. Write agents + YAML, get confidence gating, filter/router engine, telemetry, plan/execute modes, and audit trail for free.

---

## Structure

```
ai-agents/
├── conductor-core/          # Layer 1: pure framework (BaseAgent, Orchestrator, Graph, Store)
├── conductor-agents/        # Layer 2: 10 domain agents with prompts + SKILL.md
├── conductor-integrations/  # Layer 2: pre-built source/git/notify clients
├── conductor-cli/           # Layer 3: planned CLI (not yet implemented)
├── consumer-showcase/       # Layer 3: reference consumer (security remediation)
├── docs/                    # Documentation
│   ├── architecture.md      # full architecture + persistence schema
│   ├── workflow-yaml.md     # YAML config reference
│   ├── consumer-guide.md    # step-by-step new consumer guide
│   └── scripts.md           # all scripts with options
├── samples/                 # Real code files with baked-in issues
├── mocks/                   # Pre-baked JSON fixtures (no scanner tokens needed)
├── Makefile                 # make setup | test | demo
└── scripts/                 # CI/CD shell scripts
```

---

## Quick Start

```bash
# 1. Clone and set up (creates .venv, installs all packages)
cd NewFramework/ai-agents
make setup

# 2. Copy env template and fill in values (mock mode works with no credentials)
cp .env.example .env

# 3. Run all unit tests
make test

# 4. Run a demo scenario (no LLM token required in mock mode)
make demo              # snyk CVE scenario
make demo-sonar        # SQL injection + hardcoded credential
make demo-blackduck    # GPL license violation
make demo-ado-defect   # off-by-one bug
make demo-ado-story    # feature implementation story
```

---

## Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Python | 3.11 | [python.org](https://python.org) |
| `gh` CLI | 2.x | `brew install gh` |
| Copilot extension | latest | `gh extension install github/gh-copilot` |

> For mock mode (`CONDUCTOR_PROVIDER_MODE=mock`) no scanner tokens are needed.
> Real LLM calls require `CONDUCTOR_LLM_PROVIDER` + `COPILOT_GITHUB_TOKEN` (or `GITHUB_TOKEN`).

---

## How It Works

```
WorkflowContext (payload: dict)
       │
       ▼
FilterEngine  ─── reject_if_in, reject_if_null, dedup (zero LLM cost)
       │
       ▼
RouterEngine  ─── payload field matching → workflow graph selection
       │
       ▼
WorkflowOrchestrator
  ┌────────────────┐
  │  stage loop    │
  │  ┌──────────┐  │
  │  │ agent    │◄─┤── BaseAgent (LLM) / FunctionalAgent (no LLM)
  │  │ decision │  │
  │  └──────────┘  │
  │  transitions   │── YAML: on_proceed → next_stage
  └────────────────┘
       │
       ▼
WorkflowContext.decisions  (append-only audit trail)
WorkflowContext.telemetry  (tokens / latency / recode_rounds)
```

---

## Writing Your Own Consumer

The fastest path is to **reuse existing agents** from `conductor-agents` and just write a workflow YAML:

```python
# main.py — minimal new consumer
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.graph import WorkflowGraph
from conductor_core.context import WorkflowContext
from conductor_core.stores.sqlite_store import SQLiteResultStore
from conductor_agents import TriageAgent, PlannerAgent  # reuse existing agents

graph = WorkflowGraph.from_yaml("config/workflow.yaml")
store = SQLiteResultStore("runs.db")
orch  = WorkflowOrchestrator(
    agents={"triage": TriageAgent(llm), "planner": PlannerAgent(llm)},
    graph=graph,
    result_store=store,
)
ctx    = WorkflowContext(run_id="X-001", payload={"work_item": item})
result = await orch.run(ctx)
```

For the full consumer guide (custom agents, prompts, testing): **[docs/consumer-guide.md](docs/consumer-guide.md)**

---

## Environment Variables

See [`.env.example`](.env.example) for the full list.

Key variables:

| Variable | Default | Description |
|---|---|---|
| `CONDUCTOR_PROVIDER_MODE` | `mock` | `mock` or `live` |
| `CONDUCTOR_CODE_EXECUTION_ENABLED` | `false` | Enable execute mode |
| `CONDUCTOR_LLM_MODEL` | `gpt-4o` | Default LLM model for all agents |
| `CONDUCTOR_REVIEWER_MODEL` | `gpt-4o` | Model for adversarial ReviewerAgent |
| `CONDUCTOR_LOG_LEVEL` | `INFO` | Log level |
| `CONDUCTOR_CONFIDENCE_THRESHOLD` | `0.7` | Min confidence to proceed |
| `COPILOT_GITHUB_TOKEN` | — | GitHub token for Copilot LLM |
| `CONDUCTOR_DB_URL` | `sqlite+aiosqlite:///conductor_runs.db` | Result store database URL |
| `CONDUCTOR_OTEL_ENDPOINT` | _(none)_ | OTLP gRPC endpoint for traces |
| `CONDUCTOR_OTEL_SERVICE_NAME` | `conductor` | Service name in trace UIs |

---

## Persistence — SQLite Result Store

Every run is automatically saved to SQLite (or Postgres in production). No extra setup needed for development.

```python
from conductor_core.stores.sqlite_store import SQLiteResultStore

store = SQLiteResultStore("conductor_runs.db")
result = await orch.run(ctx, result_store=store)

# Retrieve later
run   = await store.get_run("SNYK-001")
runs  = await store.list_runs(limit=50)
```

**CLI flag (consumer-showcase):**
```bash
python main.py --scenario snyk --store /tmp/my_runs.db
python main.py --all --store /tmp/my_runs.db   # all 5 scenarios
```

**Switch to Postgres (production):**
```bash
docker compose up -d postgres   # starts Postgres on port 5435
# .env:
CONDUCTOR_DB_URL=postgresql+asyncpg://conductor:conductor_dev@localhost:5435/conductor
```

---

## Observability — OpenTelemetry

OTEL traces are emitted per run with spans for each stage and agent. Zero configuration needed for local dev (uses NoOp provider silently).

```
workflow:security_remediation          (root span)
  ├── stage:triage                     (per-stage span)
  │     └── agent=triage, tokens=370
  └── stage:plan                       (per-stage span)
        └── agent=planner, tokens=441
```

**Enable traces (Jaeger, Honeycomb, Datadog, etc.):**
```bash
# .env
CONDUCTOR_OTEL_ENDPOINT=http://localhost:4317    # OTLP gRPC
CONDUCTOR_OTEL_SERVICE_NAME=conductor
```

**Span attributes recorded:**
- `run_id`, `workflow`, `mode`, `route`
- Per stage: `agent`, `recommendation`, `confidence`
- On completion: `blocked`, `decision_count`, `total_tokens`

---

## Running Tests

```bash
make test              # all unit tests (fast, no LLM)
make test-unit         # same as above
make test-integration  # real LLM calls (requires COPILOT_GITHUB_TOKEN)
make lint              # ruff check across all packages
```

---

## Demo Scenarios

Each scenario uses a real code file in `samples/` and a pre-baked mock JSON in `mocks/`:

| Scenario | File | Issue |
|---|---|---|
| `snyk` | `samples/snyk/requirements_vulnerable.txt` | CVE-2023-32681 in requests 2.18.0 |
| `sonar` | `samples/sonar/auth_handler.py` | SQL injection + hardcoded credential |
| `blackduck` | `samples/blackduck/package_copyleft.py` | GPL-3.0 license violation |
| `ado-defect` | `samples/ado/buggy_calculator.py` | Off-by-one + division by zero |
| `ado-story` | `samples/ado/feature_stub.py` | Unimplemented `paginate()` |

---

## Package Dependency Graph

```
consumer-showcase
    └── conductor-agents
            └── conductor-core

conductor-integrations
    └── conductor-core
```

Each package can be installed independently:
```bash
pip install conductor-core               # framework only
pip install conductor-agents             # + 10 domain agents with prompts
pip install conductor-integrations       # + source/git/notify clients
pip install consumer-showcase            # + full security-remediation reference consumer
```

---

## Documentation

| Doc | Description |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Full architecture, runtime flow, persistence schema |
| [docs/workflow-yaml.md](docs/workflow-yaml.md) | Complete YAML config reference |
| [docs/consumer-guide.md](docs/consumer-guide.md) | Step-by-step new consumer guide |
| [docs/scripts.md](docs/scripts.md) | All scripts with options and examples |
| [conductor-agents/README.md](conductor-agents/README.md) | All 10 agents, prompt guide, how to extend |
| [conductor-core/README.md](conductor-core/README.md) | Framework internals |
| [conductor-integrations/README.md](conductor-integrations/README.md) | Mock + live source/git clients |
| [consumer-showcase/README.md](consumer-showcase/README.md) | Reference consumer and all demo scenarios |
