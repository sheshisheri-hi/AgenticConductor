# Conductor — Generic Multi-Agent Workflow Framework

A reusable orchestration framework for building multi-agent AI workflows. Write agents + YAML, get confidence gating, filter/router engine, telemetry, plan/execute modes, and audit trail for free.

Inspired by MetaGPT, CrewAI, and production security remediation workflows.

---

## Structure

```
ai-agents/
├── conductor-core/          # Layer 1: pure framework (BaseAgent, Orchestrator, Graph, Store)
├── conductor-agents/        # Layer 2: 10 domain agents with prompts + SKILL.md
├── conductor-integrations/  # Layer 2: pre-built source/git/notify clients
├── conductor-cli/           # Layer 3: conductor CLI (runs, plan, trace, clean, logs)
├── consumer-showcase/       # Layer 3: reference consumer (security remediation)
├── docs/                    # Documentation
│   ├── architecture.md      # full architecture + persistence schema
│   ├── workflow-yaml.md     # YAML config reference
│   ├── consumer-guide.md    # step-by-step new consumer guide
│   ├── scripts.md           # conductor CLI commands reference
│   └── installation.md      # local / GitHub / Artifactory install options
├── samples/                 # Real code files with baked-in issues
├── mocks/                   # Pre-baked JSON fixtures (no scanner tokens needed)
└── Makefile                 # make setup | test | demo
```

---

## 👩‍💻 Path 1: Developer — Run the Samples

You want to explore the framework, run the built-in demo scenarios, and see how it works end-to-end.

### 1. Prerequisites

| Tool | Min version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| Git | any | — |

### Provider Modes — Understanding the 4 Tiers

Every `dev.sh` and `make` command accepts a `--mode` flag. The mode controls three independent layers:

| Mode | LLM | Data (Snyk/Sonar/ADO) | Git Operations | Tokens needed |
|---|---|---|---|---|
| `mock` | StubLLM (instant, free) | Fixture JSON | Stubbed (fake PR URLs) | None |
| `sample` | Real Copilot (`gpt-4.1`) | Fixture JSON | Stubbed (fake PR URLs) | `GITHUB_TOKEN` (Copilot) |
| `integration` | Real Copilot (`gpt-4.1`) | Fixture JSON | **Real branches + PRs** on test repos | `GITHUB_TOKEN` |
| `live` | Real Copilot (`gpt-4.1`) | Real scanner APIs | Real branches + PRs on prod repos | `GITHUB_TOKEN` + scanner tokens |

**Key insight:** `sample` and `integration` both use the same fixture JSON as input — the LLM reasons about pre-baked data. The difference is what happens *after* the plan is approved: `sample` prints fake git URLs; `integration` actually creates a branch, commits the LLM-generated fix, and opens a real PR in your configured test repos.

```bash
# No tokens — runs instantly, great for CI and first exploration
./dev.sh demo snyk                  # mock (default)

# Real LLM reasoning, no git side effects
./dev.sh sample snyk                # sample mode — needs GITHUB_TOKEN for Copilot

# Real LLM + real GitHub branches/PRs in your test repos
./dev.sh sample snyk default integration   # integration mode

# Real LLM + real scanner data + real git (production)
CONDUCTOR_PROVIDER_MODE=live ./dev.sh sample snyk
```

> **Mock mode** requires **no tokens** — all LLM responses are stubs, all git URLs are fake.

### 2. Setup

```bash
git clone https://github.com/sheshisheri-hi/AgenticConductor.git
cd AgenticConductor/ai-agents

make setup          # creates .venv, installs all 5 packages + conductor CLI
```

### 3. Verify

```bash
make test           # runs all unit tests — should all pass, no token needed
```

### 4. Run demo scenarios

```bash
make demo              # all 5 scenarios back-to-back
make demo-snyk         # Snyk CVE: requests 2.18.0 vulnerability
make demo-sonar        # SonarQube: SQL injection + hardcoded credential
make demo-blackduck    # BlackDuck: GPL-3.0 license violation
make demo-ado-defect   # ADO defect: off-by-one + division by zero
make demo-ado-story    # ADO story: unimplemented paginate()
```

### 5. Inspect results with the CLI

```bash
source .venv/bin/activate

# List all runs
conductor runs --store /tmp/runs.db

# See the fix plan
conductor plan SNYK-001-demo --store /tmp/runs.db

# Full reasoning trace (which agent decided what, confidence, cost)
conductor trace SNYK-001-demo --store /tmp/runs.db

# Audit trail (with LLM prompts + raw responses)
conductor trace SNYK-001-demo --store /tmp/runs.db --prompts --raw

# Everything in one view
conductor all --store /tmp/runs.db
```

### 6. Try different workflow configs

```bash
# Plan-only (stops before code generation)
python consumer-showcase/main.py --scenario snyk --workflow consumer-showcase/config/workflow_security.yaml --store /tmp/runs.db

# Adversarial: reviewer uses a different model than planner
python consumer-showcase/main.py --scenario snyk --workflow consumer-showcase/config/workflow_adversarial.yaml --store /tmp/runs.db

# Full execute mode (plan → code → git → PR → notify)
python consumer-showcase/main.py --scenario snyk --workflow consumer-showcase/config/workflow_execute.yaml --store /tmp/runs.db
```

---

## 🏗️ Path 2: New Consumer — Build From This

You want to build your own pipeline on top of Conductor (e.g., a different domain than security remediation).

### Option A — Reuse existing agents (fastest)

Pick from the 10 agents in `conductor-agents` and wire them in a YAML:

```python
# my_consumer/main.py
import asyncio
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.graph import WorkflowGraph
from conductor_core.context import WorkflowContext
from conductor_core.stores.sqlite_store import SQLiteResultStore
from conductor_agents import TriageAgent, PlannerAgent, ReviewerAgent
from conductor_integrations.sources.factory import SourceFactory

async def main():
    llm        = ...                   # your LLM client
    graph      = WorkflowGraph.from_yaml("config/workflow.yaml")
    store      = SQLiteResultStore("runs.db")
    orch       = WorkflowOrchestrator(
        agents={"triage": TriageAgent(llm), "planner": PlannerAgent(llm), "reviewer": ReviewerAgent(llm)},
        graph=graph,
        result_store=store,
    )
    payload    = {"work_item": {"id": "MY-001", "title": "...", "severity": "HIGH"}}
    ctx        = WorkflowContext(run_id="MY-001", payload=payload)
    result     = await orch.run(ctx)
    print(result.decisions[-1].recommendation)

asyncio.run(main())
```

### Option B — Write a custom agent

```python
# my_consumer/agents/my_agent.py
from conductor_core.base_agent import BaseAgent
from conductor_core.decisions import AgentDecision

class MyAgent(BaseAgent):
    NAME = "my_agent"

    async def decide(self, context) -> AgentDecision:
        response = await self._reason(
            system="You are a specialist in ...",
            user=f"Evaluate: {context.payload}",
            context=context,
        )
        return AgentDecision(
            agent=self.NAME,
            recommendation=response.get("recommendation", "PROCEED"),
            confidence=response.get("confidence", 0.8),
            reasoning=response.get("reasoning", []),
        )
```

Customize the prompt by editing `agents/my_agent/prompts/system.md` — no code change needed.

### Install from GitHub

```bash
pip install "git+https://github.com/sheshisheri-hi/AgenticConductor.git#subdirectory=ai-agents/conductor-core"
pip install "git+https://github.com/sheshisheri-hi/AgenticConductor.git#subdirectory=ai-agents/conductor-agents"
```

### Full consumer guide

→ **[docs/consumer-guide.md](docs/consumer-guide.md)** — 9-step walkthrough: setup, agents, YAML, testing, persistence, OTEL

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
SQLiteResultStore          (persist runs + decisions → query with conductor CLI)
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
| `CONDUCTOR_PROVIDER_MODE` | `mock` | `mock` / `sample` / `integration` / `live` |
| `CONDUCTOR_CODE_EXECUTION_ENABLED` | `false` | Enable execute mode |
| `CONDUCTOR_LLM_MODEL` | `gpt-4.1` | Default LLM model for all agents |
| `CONDUCTOR_REVIEWER_MODEL` | `gpt-4.1` | Model for adversarial ReviewerAgent |
| `CONDUCTOR_LOG_LEVEL` | `INFO` | Log level |
| `CONDUCTOR_CONFIDENCE_THRESHOLD` | `0.7` | Min confidence to proceed |
| `COPILOT_GITHUB_TOKEN` | — | GitHub token for Copilot LLM (sample/integration/live) |
| `CONDUCTOR_DB_URL` | `sqlite+aiosqlite:///conductor_runs.db` | Result store database URL |
| `CONDUCTOR_OTEL_ENDPOINT` | _(none)_ | OTLP gRPC endpoint for traces |
| `CONDUCTOR_OTEL_SERVICE_NAME` | `conductor` | Service name in trace UIs |
| `GITHUB_ORG` | — | GitHub org/user for real git ops (integration/live) |
| `CONDUCTOR_BRANCH_PREFIX` | `conductor` | Branch prefix for real git ops |
| `CONDUCTOR_GIT_EMAIL` | `conductor-bot@users.noreply.github.com` | Git commit author email |
| `SNYK_TOKEN` | — | Snyk API token (live mode only) |
| `SNYK_ORG_ID` | — | Snyk organisation ID (live mode only) |
| `SONAR_URL` | — | SonarQube server URL (live mode only) |
| `SONAR_TOKEN` | — | SonarQube user token (live mode only) |
| `ADO_ORG` | — | Azure DevOps org URL e.g. `https://dev.azure.com/myorg` (live mode only) |
| `ADO_PAT` | — | Azure DevOps Personal Access Token (live mode only) |

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
