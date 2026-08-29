# Conductor (ai-agents)

Python packages for **AgenticConductor** — a YAML-driven multi-agent workflow kernel and a security-remediation reference consumer.

> **Proof of concept / experiment.** Not a product, not production-certified, not on PyPI. Start at the **[root README](../README.md)** for positioning, architecture bets, and comparison with Devin / MetaGPT / LangGraph. Narrative for sharing: **[docs/LINKEDIN_PRESENTATION.md](../docs/LINKEDIN_PRESENTATION.md)**.

This file is the **developer handbook for the `ai-agents/` tree**: install, env, demos, tests, env vars.

---

## Packages

```
ai-agents/
├── conductor-core/          # Layer 1: BaseAgent, Orchestrator, Graph, filters, store, tracing
├── conductor-agents/        # Layer 2: 10 domain agents (prompts + SKILL.md)
├── conductor-integrations/  # Layer 2: Snyk / Sonar / BlackDuck / ADO / git / notify
├── conductor-cli/           # Layer 3: conductor runs | plan | trace | check | …
├── consumer-showcase/       # Layer 3: reference consumer (security remediation)
├── docs/                    # architecture, YAML spec, ADRs, security notes
├── samples/                 # hello-world, security-remediation, grafana-rca, …
├── mocks/                   # fixture JSON for mock/sample modes
├── Makefile                 # make setup | test | demo
└── dev.sh                   # preferred local driver (creates/uses .venv)
```

`conductor-core` has **zero domain knowledge**. Security, git, and scanners live in agents + integrations + the consumer.

---

## Which command to use

| Tool | When |
|---|---|
| `./dev.sh <cmd>` | Day-to-day. Manages the venv. Prefer this. |
| `make <target>` | Thin aliases (`make demo` → `./dev.sh demo`). |
| `conductor <cmd>` | After a run: `runs`, `plan`, `trace`, `check`. |
| `python consumer-showcase/main.py` | Extra flags (`--scenario`, `--workflow`, `--store`, `--mode`). |

---

## Setup

**Python 3.11+.** Mock mode needs no tokens.

```bash
cd ai-agents
cp .env.example .env          # optional until you leave mock mode
make setup                    # .venv + editable installs
make test                     # unit tests, StubLLM
make demo-snyk                # one mock scenario
```

Clone URL (adjust to your fork):

```bash
git clone https://github.com/sheshi-sheri/AgenticConductor.git
cd AgenticConductor/ai-agents
```

`gh` + GitHub Copilot CLI are only required for `sample` / `integration` / `live` (real LLM).

---

## Provider modes

`CONDUCTOR_PROVIDER_MODE` (or the 4th `dev.sh` argument) controls LLM, scanner data, and git independently:

| Mode | LLM | Data (Snyk/Sonar/ADO) | Git | Tokens |
|---|---|---|---|---|
| `mock` | StubLLM | fixtures | stubbed | none |
| `sample` | Copilot (`gpt-4.1`) | fixtures | stubbed | GitHub token |
| `integration` | Copilot | fixtures | real test-org PRs | token + `GITHUB_ORG` |
| `live` | Copilot | live APIs | real PRs | token + scanner tokens |

```bash
./dev.sh demo snyk                         # mock
./dev.sh sample snyk                       # real LLM, fake git
./dev.sh sample snyk default integration   # real LLM + real PRs in test org
CONDUCTOR_PROVIDER_MODE=live ./dev.sh sample snyk
```

Token resolution (first non-empty wins):  
`CONDUCTOR_GITHUB_TOKEN` → `GITHUB_COPILOT_TOKEN` → `COPILOT_GITHUB_TOKEN` → `GITHUB_TOKEN`

---

## Demos and CLI

```bash
make demo              # all five mock scenarios
make demo-snyk
make demo-sonar
make demo-blackduck
make demo-ado-defect
make demo-ado-story
```

| Scenario | Sample issue |
|---|---|
| `snyk` | CVE in `requests` 2.18.0 |
| `sonar` | SQL injection + hardcoded credential |
| `blackduck` | GPL-3.0 license |
| `ado-defect` | off-by-one + division by zero |
| `ado-story` | unimplemented `paginate()` |

After a run (store path is printed by the demo; `/tmp/runs.db` is typical if you passed `--store`):

```bash
source .venv/bin/activate
conductor runs  --store /tmp/runs.db
conductor plan  SNYK-001-demo --store /tmp/runs.db
conductor trace SNYK-001-demo --store /tmp/runs.db --prompts --raw
```

Workflow variants (same agents, different YAML):

```bash
python consumer-showcase/main.py --scenario snyk \
  --workflow consumer-showcase/config/workflow_security.yaml --store /tmp/runs.db

python consumer-showcase/main.py --scenario snyk \
  --workflow consumer-showcase/config/workflow_execute.yaml --store /tmp/runs.db
```

Plan mode stops before code/git when the YAML has `stop_before: true`. Execute mode runs the rest — **destructive** if git is real.

---

## Tests

| Level | Command | LLM | Tokens |
|---|---|---|---|
| Unit | `make test` / `./dev.sh test` | Stub | none |
| Mock demos | `make demo` | Stub | none |
| Sample | `./dev.sh sample snyk` | real Copilot | GitHub token |
| Integration | `./dev.sh sample snyk default integration` | real + real PRs | token + org |
| Live | `CONDUCTOR_PROVIDER_MODE=live ./dev.sh sample snyk` | real + live scanners | all |

```bash
make lint    # ruff
```

---

## `conductor.json` vs workflow YAML

Every agent **key** used in any `workflow.yaml` must be declared in that project’s `conductor.json`. A mismatch fails at **runtime** (`agent_not_found`), not at install time. This is a PoC limitation — there is no full JSON Schema gate on YAML yet.

```bash
grep -h "agent:" consumer-showcase/config/*.yaml | awk '{print $NF}' | sort -u
jq -r '.agents[].name' consumer-showcase/conductor.json | sort -u
```

---

## New consumer (short)

Reuse agents + write YAML. Full walkthrough: [docs/consumer-guide.md](docs/consumer-guide.md).

```python
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.graph import WorkflowGraph
from conductor_core.context import WorkflowContext
from conductor_core.stores.sqlite_store import SQLiteResultStore
from conductor_agents import TriageAgent, PlannerAgent

graph = WorkflowGraph.from_yaml("config/workflow.yaml")
orch = WorkflowOrchestrator(
    agents={"triage": TriageAgent(llm), "planner": PlannerAgent(llm)},
    graph=graph,
    result_store=SQLiteResultStore("runs.db"),
)
ctx = WorkflowContext(run_id="X-001", payload={"work_item": item})
result = await orch.run(ctx)
```

Custom agent: subclass `BaseAgent`, add `prompts/*.md`, export, register in YAML + `conductor.json`.

Editable install from this tree:

```bash
pip install -e conductor-core
pip install -e conductor-agents
pip install -e conductor-integrations
pip install -e conductor-cli
```

From GitHub (subdirectory):

```bash
pip install "git+https://github.com/sheshi-sheri/AgenticConductor.git#subdirectory=ai-agents/conductor-core"
```

---

## Environment variables

See [`.env.example`](.env.example). Hierarchy: [docs/consumer-guide.md](docs/consumer-guide.md#settings--environment-variable-hierarchy).

| Variable | Default | Notes |
|---|---|---|
| `CONDUCTOR_PROVIDER_MODE` | `mock` | `mock` / `sample` / `integration` / `live` |
| `CONDUCTOR_CODE_EXECUTION_ENABLED` | `false` | Allow git push + PR in execute mode |
| `CONDUCTOR_LLM_MODEL` | `gpt-4.1` | Default model |
| `CONDUCTOR_REVIEWER_MODEL` | `gpt-4.1` | Prefer a **different** model than the planner |
| `CONDUCTOR_CONFIDENCE_THRESHOLD` | `0.7` | Below this → retry / escalate |
| `CONDUCTOR_DB_URL` | `sqlite+aiosqlite:///conductor_runs.db` | Postgres: `postgresql+asyncpg://…` |
| `CONDUCTOR_OTEL_ENDPOINT` | unset | OTLP gRPC; no-op if empty |
| `CONDUCTOR_LOG_LEVEL` | `INFO` | |
| `GITHUB_ORG` | — | Test/prod org for real git |
| `CONDUCTOR_BRANCH_PREFIX` | `conductor-fix` | |
| `SNYK_TOKEN`, `SONAR_TOKEN`, `ADO_PAT`, … | — | Live scanners only |
| `CONDUCTOR_TOKEN_SCRUBBER_ENABLED` | `true` | Experimental log redaction |
| `CONDUCTOR_MTLS_ENABLED` | `true` | Experimental A2A mTLS |
| `CONDUCTOR_DEPENDENCY_CHECK_ENABLED` | `true` | Experimental supply-chain check |
| `CONDUCTOR_A2A_SERVER_PORT` | `8001` | Optional HTTP agent server |

Consumer-showcase overrides use `CONSUMER_*` (Slack, PagerDuty, etc.).

Postgres: `docker compose up -d postgres` then set `CONDUCTOR_DB_URL` (see `docker-compose.yml`).

---

## How a run works

```
payload → FilterEngine → RouterEngine → WorkflowOrchestrator
            (YAML filters)   (YAML routes)    (stages + parallel groups)
                                              BaseAgent confidence loop
                                              stop_before → plan halt
         → WorkflowContext.decisions (append-only)
         → SQLiteResultStore / Postgres
         → OTEL spans (optional)
```

Details: [docs/architecture.md](docs/architecture.md). YAML: [docs/workflow-yaml.md](docs/workflow-yaml.md). Why not LangGraph: [docs/adr/ADR-008-custom-orchestration-vs-langgraph.md](docs/adr/ADR-008-custom-orchestration-vs-langgraph.md).

---

## Security notes (experimental)

Input/output Pydantic validation, log token scrubbing, optional mTLS A2A, dependency hashing exist as **PoC controls**. They are not a certified stack. Read [docs/SECURITY_HARDENING.md](docs/SECURITY_HARDENING.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) as design notes. Token budgets / rate limits in ADR-013 are **not fully implemented**.

A2A server: [docs/A2A_SERVER_GUIDE.md](docs/A2A_SERVER_GUIDE.md).

---

## Documentation

| Doc | Contents |
|---|---|
| [../README.md](../README.md) | Repo overview, PoC disclaimer, framework comparison |
| [../docs/LINKEDIN_PRESENTATION.md](../docs/LINKEDIN_PRESENTATION.md) | LinkedIn / talk narrative |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | First 15 minutes |
| [docs/architecture.md](docs/architecture.md) | Runtime + persistence schema |
| [docs/workflow-yaml.md](docs/workflow-yaml.md) | YAML reference |
| [docs/consumer-guide.md](docs/consumer-guide.md) | New consumer walkthrough |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Public APIs |
| [docs/adr/](docs/adr/) | ADRs 001–013 |
| [conductor-core/README.md](conductor-core/README.md) | Kernel internals |
| [conductor-agents/README.md](conductor-agents/README.md) | Agent contracts |
| [conductor-cli/README.md](conductor-cli/README.md) | CLI reference |
| [consumer-showcase/README.md](consumer-showcase/README.md) | Showcase scenarios |
