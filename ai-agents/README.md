# Conductor — Generic Multi-Agent Workflow Framework

A reusable orchestration framework for building multi-agent AI workflows. Write agents + YAML, get confidence gating, filter/router engine, telemetry, plan/execute modes, and audit trail for free.

Inspired by MetaGPT, CrewAI, and production security remediation workflows.

---

## ✨ Phase 4: Production-Grade Security Stack

**NEW in Phase 4** — 5-layer security hardening + A2A HTTP server + conductor.json manifest:

| Feature | What it does | Docs |
|---|---|---|
| **5-Layer Security** | Input validation → mTLS → secret scrubbing → output validation → supply chain verification | [SECURITY_HARDENING.md](docs/SECURITY_HARDENING.md) |
| **conductor.json** | Project manifest declaring agents, integrations, and security settings | [consumer-showcase/conductor.json](consumer-showcase/conductor.json) |
| **A2A HTTP Server** | Expose agents as REST endpoints with mTLS for external framework integration | [A2A_SERVER_GUIDE.md](docs/A2A_SERVER_GUIDE.md) |
| **TokenScrubber** | Automatically redacts 10+ secret patterns from logs (GitHub, AWS, JWT, Snyk, database, etc.) | [SECURITY_HARDENING.md § Layer 3](docs/SECURITY_HARDENING.md) |
| **DependencyVerifier** | Pre-flight supply chain verification with SHA256 hashing and CVE checking | [SECURITY_HARDENING.md § Layer 4](docs/SECURITY_HARDENING.md) |
| **@validated_agent** | Pydantic schema validation on all agent inputs/outputs | [API_REFERENCE.md](docs/API_REFERENCE.md) |

**Security Stack Diagram:**
```
External Framework
        ↓ (mTLS)
A2A HTTP Server → DependencyVerifier → TokenScrubber → @validated_agent → Agent Logic
```

See [ADR_SUMMARY.md](docs/ADR_SUMMARY.md) for architectural decisions (ADRs 009-013).

### ⚠️ Important: conductor.json Must Declare All Agents

**Every agent referenced in any workflow.yaml file MUST be declared in conductor.json first.**

If a workflow references an agent not in conductor.json, the workflow will **FAIL AT RUNTIME**:
```
agent_not_found:
  stage: "code"
  agent_key: "code_agent"
  registered: ["snyk_triage", "code_analyzer", ...]
  
⚠️ Workflow BLOCKED: "No agent registered for: 'code_agent'"
```

**Example:** If `workflow_execute.yaml` uses 9 agents (triage → code → review → git → notify → feedback), then conductor.json must declare all 9 agents in its `"agents"` array. See [consumer-showcase/conductor.json](consumer-showcase/conductor.json) for reference.

---

## Structure

```
ai-agents/
├── conductor-core/          # Layer 1: pure framework (BaseAgent, Orchestrator, Graph, Store)
├── conductor-agents/        # Layer 2: 10 domain agents with prompts + SKILL.md
├── conductor-integrations/  # Layer 2: pre-built source/git/notify clients
├── conductor-cli/           # Layer 3: conductor CLI (runs, plan, trace, clean, logs)
├── consumer-showcase/       # Layer 3: reference consumer (security remediation + Phase 4)
├── docs/                    # Documentation
│   ├── QUICKSTART.md        # First 15 min start (samples, no real LLM tokens)
│   ├── SECURITY_HARDENING.md # 5-layer security stack + mTLS + deployment checklist
│   ├── API_REFERENCE.md     # Public API docs (WorkflowOrchestrator, @validated_agent, etc.)
│   ├── ADR_SUMMARY.md       # Architectural decisions (ADRs 009-013) + Phase 4 decisions
│   ├── A2A_SERVER_GUIDE.md  # A2A HTTP server setup + endpoints + mTLS configuration
│   ├── DEPLOYMENT_GUIDE.md  # Production deployment guide with security hardening
│   ├── THREAT_MODEL.md      # Security threat analysis + mitigations
│   ├── architecture.md      # Full architecture + persistence schema
│   ├── workflow-yaml.md     # YAML config reference
│   ├── consumer-guide.md    # Step-by-step new consumer guide
│   ├── scripts.md           # conductor CLI commands reference
│   ├── installation.md      # Local / GitHub / Artifactory install options
│   └── adr/                 # Architecture Decision Records (009-013 for Phase 4)
├── samples/                 # Real code files with baked-in issues (4 projects)
├── mocks/                   # Pre-baked JSON fixtures (4 agent mocks)
└── Makefile                 # make setup | test | demo
```

---

## 🛠 Which tool to use?

| Tool | When to use |
|---|---|
| `./dev.sh <cmd>` | **Day-to-day development.** Manages the virtualenv for you — no `source .venv/bin/activate` needed. Preferred for running tests, demos, and sample mode. |
| `make <target>` | **Shorthand aliases** for common dev.sh commands. `make demo` = `./dev.sh demo`. Same underlying logic; use whichever you prefer. |
| `conductor <cmd>` | **Inspecting persisted results.** After a run, use the CLI to view runs, fix plans, reasoning traces, and audit logs: `conductor runs`, `conductor plan`, `conductor trace`. |
| `python consumer-showcase/main.py` | **Advanced/scripted usage.** Pass custom flags (`--scenario`, `--workflow`, `--store`, `--mode`). Useful when you need full control not exposed via `dev.sh`. |

---

## 👩‍💻 Path 1: Developer — Run the Samples

You want to explore the framework, run the built-in demo scenarios, and see how it works end-to-end.

### 1. Prerequisites

| Tool | Min version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| Git | any | — |
| `gh` CLI | 2.x | `brew install gh` (macOS) / [cli.github.com](https://cli.github.com) |
| GitHub Copilot extension | latest | `gh extension install github/gh-copilot` |

> **Mock mode** (`CONDUCTOR_PROVIDER_MODE=mock`) requires **no tokens** — all LLM calls are instant stubs. The `gh` CLI + Copilot extension are only needed for `sample` / `integration` / `live` modes.

### 2. Required environment variables

Copy `.env.example` to `.env` and fill in the values you need:

```bash
cp .env.example .env
```

| Variable | Required for | Description |
|---|---|---|
| `CONDUCTOR_GITHUB_TOKEN` | `sample`, `integration`, `live` | GitHub PAT — used for **both** Copilot LLM calls and git operations. Resolves via: `CONDUCTOR_GITHUB_TOKEN` → `GITHUB_COPILOT_TOKEN` → `COPILOT_GITHUB_TOKEN` → `GITHUB_TOKEN` (first non-empty wins). |
| `GITHUB_ORG` | `integration` | GitHub org/user where test branches + PRs are created (e.g. `sheshisheri-hi`). |
| `CONDUCTOR_PROVIDER_MODE` | always | `mock` (default, no token) / `sample` / `integration` / `live` |
| `CONDUCTOR_DB_URL` | optional | SQLite path (default: `sqlite+aiosqlite:///conductor_runs.db`). Switch to `postgresql+asyncpg://...` for production. |
| `SNYK_TOKEN`, `SONAR_TOKEN`, etc. | `live` only | Real scanner API tokens. See `.env.example` for full list. |

### Provider Modes — Understanding the 4 Tiers

`dev.sh` and `make` use `CONDUCTOR_PROVIDER_MODE` (or the optional 4th CLI argument) to control three independent runtime layers — LLM, data source, and git operations:

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

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Orchestration** | Custom pipeline (no LangGraph) | YAML-driven graph, sequential + parallel runners. See [ADR-008](docs/adr/ADR-008-custom-orchestration-vs-langgraph.md) for why LangGraph was considered and not adopted. |
| **LLM** | GitHub Copilot SDK (`gpt-4.1`) | Pluggable via `ILLMProvider` — swap to OpenAI, Azure, Anthropic without changing agents. |
| **Security (Phase 4)** | 5-layer stack | Input validation (Pydantic) → mTLS → TokenScrubber → output validation → DependencyVerifier. See [ADRs 009-013](docs/ADR_SUMMARY.md) and [SECURITY_HARDENING.md](docs/SECURITY_HARDENING.md). |
| **A2A HTTP (Phase 4)** | FastAPI + mTLS | Expose agents as REST endpoints with client certificate verification. See [A2A_SERVER_GUIDE.md](docs/A2A_SERVER_GUIDE.md). |
| **Result store (dev)** | SQLite (`aiosqlite`) | Zero setup. Stores 2 tables: `runs` (summary per run) and `agent_decisions` (full prompt/response/reasoning per agent call). Configure path via `CONDUCTOR_DB_URL`. |
| **Result store (prod)** | PostgreSQL | `docker compose up -d postgres`, set `CONDUCTOR_DB_URL=postgresql+asyncpg://...`. Same `IResultStore` interface — no code change. |
| **Tracing** | OpenTelemetry | Per-stage spans with agent/token/confidence attributes. Silent no-op locally; plug in Jaeger/Honeycomb/Datadog via `CONDUCTOR_OTEL_ENDPOINT`. |
| **Logging** | structlog (JSON) | Stdout by default. Set `CONDUCTOR_LOG_FILE=logs/conductor.log` to also write to file. TokenScrubber redacts secrets automatically. |
| **Packaging** | `pyproject.toml` (PEP 621) + `pip install -e` | Modern Python packaging standard (replaces `setup.py`). Used by FastAPI, Pydantic, and most major Python projects. |
| **Task runner** | `Makefile` + `dev.sh` | Makefile is a thin alias layer over `dev.sh`. Both are standard tooling — Make is used by Linux kernel, NumPy, and most open-source projects. |

---

## Writing Your Own Consumer

The fastest path is to **reuse existing agents** from `conductor-agents` and just write a workflow YAML.

> **`ctx` = `WorkflowContext`** — the runtime object that flows through the entire pipeline. It holds the input `payload` (work item from your ingest/triage pipeline), accumulates `decisions` from each agent, and tracks `telemetry` (tokens, latency). You create it, the orchestrator runs it.

> **`SQLiteResultStore`** is one implementation of the `IResultStore` interface. You can swap it for a `PostgresResultStore` (or write your own) without changing any agent or orchestrator code. The path/URL is set via `CONDUCTOR_DB_URL`.

```python
# main.py — minimal new consumer
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.graph import WorkflowGraph
from conductor_core.context import WorkflowContext
from conductor_core.stores.sqlite_store import SQLiteResultStore
from conductor_agents import TriageAgent, PlannerAgent  # reuse existing agents

graph = WorkflowGraph.from_yaml("config/workflow.yaml")
store = SQLiteResultStore("runs.db")  # or PostgresResultStore for production
orch  = WorkflowOrchestrator(
    agents={"triage": TriageAgent(llm), "planner": PlannerAgent(llm)},
    graph=graph,
    result_store=store,
)
# ctx carries the work item from your ingest pipeline (Snyk webhook, ADO trigger, etc.)
ctx    = WorkflowContext(run_id="X-001", payload={"work_item": item})
result = await orch.run(ctx)
```

For the full consumer guide (custom agents, prompts, testing): **[docs/consumer-guide.md](docs/consumer-guide.md)**

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. For the full hierarchy and prefix rules, see [docs/consumer-guide.md](docs/consumer-guide.md#settings--environment-variable-hierarchy).

Key variables:

| Variable | Default | Description |
|---|---|---|
| `CONDUCTOR_PROVIDER_MODE` | `mock` | `mock` / `sample` / `integration` / `live` |
| `CONDUCTOR_CODE_EXECUTION_ENABLED` | `false` | Enable execute mode (git push + PR) |
| `CONDUCTOR_LLM_MODEL` | `gpt-4.1` | Default LLM model for all agents |
| `CONDUCTOR_REVIEWER_MODEL` | `gpt-4.1` | Model for adversarial ReviewerAgent (should differ from LLM_MODEL) |
| `CONDUCTOR_LOG_LEVEL` | `INFO` | Log level |
| `CONDUCTOR_CONFIDENCE_THRESHOLD` | `0.7` | Min confidence to proceed |
| `COPILOT_GITHUB_TOKEN` | — | GitHub token for Copilot LLM (sample/integration/live). Token resolution chain: `CONDUCTOR_GIT_TOKEN` → `CONDUCTOR_GITHUB_TOKEN` → `GITHUB_COPILOT_TOKEN` → `COPILOT_GITHUB_TOKEN` → `GITHUB_TOKEN` |
| `CONDUCTOR_DB_URL` | `sqlite+aiosqlite:///conductor_runs.db` | Result store database URL |
| `CONDUCTOR_OTEL_ENDPOINT` | _(none)_ | OTLP gRPC endpoint for traces |
| `CONDUCTOR_OTEL_SERVICE_NAME` | `conductor` | Service name in trace UIs |
| `GITHUB_ORG` | — | GitHub org/user for real git ops (integration/live). Uses `alias=` — no prefix needed. |
| `CONDUCTOR_BRANCH_PREFIX` | `conductor-fix` | Branch prefix for real git ops |
| `CONDUCTOR_GIT_EMAIL` | `conductor-bot@users.noreply.github.com` | Git commit author email |
| `SNYK_TOKEN` | — | Snyk API token (live mode only) |
| `SNYK_ORG_ID` | — | Snyk organisation ID (live mode only) |
| `SONAR_URL` | — | SonarQube server URL (live mode only) |
| `SONAR_TOKEN` | — | SonarQube user token (live mode only) |
| `ADO_ORG` | — | Azure DevOps org URL e.g. `https://dev.azure.com/myorg` (live mode only) |
| `ADO_PAT` | — | Azure DevOps Personal Access Token (live mode only) |
| **Phase 4 Security (NEW)** | | |
| `CONDUCTOR_TOKEN_SCRUBBER_ENABLED` | `true` | Enable automatic secret redaction in logs |
| `CONDUCTOR_MTLS_ENABLED` | `true` | Enable mTLS for A2A agent communication |
| `CONDUCTOR_DEPENDENCY_CHECK_ENABLED` | `true` | Enable pre-flight supply chain verification |
| `CONDUCTOR_A2A_SERVER_PORT` | `8001` | Port for A2A HTTP server (use `python main.py --a2a-server`) |
| `CONDUCTOR_A2A_SERVER_MTLS` | `true` | Enable mTLS for A2A server (recommended for production) |
| `CONDUCTOR_OUTPUT_VALIDATOR_ENABLED` | `true` | Validate all agent outputs against Pydantic schemas |

**Consumer-level overrides** (consumer-showcase only): Variables prefixed `CONSUMER_` override `CONDUCTOR_` defaults for that consumer. See `consumer-showcase/consumer_showcase/config/settings.py`.

| Variable | Default | Description |
|---|---|---|
| `CONSUMER_SLACK_CHANNEL` | `#security-alerts` | Slack channel for notifications |
| `CONSUMER_SLACK_TOKEN` | — | Slack Bot token for notify agent |
| `CONSUMER_PAGERDUTY_KEY` | — | PagerDuty integration key |

---

## 🔐 Phase 4: Production Security Hardening

All Phase 4 features are production-ready and enabled by default. This section is a quick reference — for complete details, see [SECURITY_HARDENING.md](docs/SECURITY_HARDENING.md).

### Layer 1: Input Validation (Pydantic Schemas)
- All agent inputs validated before execution
- Rejects malformed data with clear error messages
- Decorator: `@validated_agent(input_schema=...)`

```python
from conductor_core.decorators import validated_agent
from pydantic import BaseModel

class TriageInput(BaseModel):
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    source: str    # snyk | sonar | blackduck | ado

@validated_agent(input_schema=TriageInput)
async def my_agent(context, **kwargs):
    # Guaranteed: context.kwargs matches schema
    ...
```

### Layer 2: Execution Security (mTLS)
- Agent-to-agent communication encrypted with TLS
- Client certificates verify agent identity
- Auto-generated CA and per-agent certificates

```bash
# Enable mTLS (recommended for production)
CONDUCTOR_MTLS_ENABLED=true python main.py --a2a-server

# Or via conductor.json
{
  "settings": {
    "a2a_server": {"use_mtls": true}
  }
}
```

See [A2A_SERVER_GUIDE.md](docs/A2A_SERVER_GUIDE.md) for certificate setup.

### Layer 3: Secret Management (TokenScrubber)
- Automatically redacts 10+ secret patterns from all logs
- Patterns: GitHub tokens, AWS keys, API keys, JWT, Snyk tokens, database passwords, etc.
- Active globally — no per-logger configuration needed
- Enabled by default: `CONDUCTOR_TOKEN_SCRUBBER_ENABLED=true`

```python
# Example: this log will have secrets redacted
logger.info("Connecting to GitHub with token: ghp_abc123def456789")
# Output: "Connecting to GitHub with token: <REDACTED>"
```

Verify it's working:
```bash
python -c "
import logging
from conductor_core.secrets.token_scrubber import ScrubFilter

logging.basicConfig(level=logging.INFO)
logging.getLogger().addFilter(ScrubFilter())
log = logging.getLogger()
log.info('GitHub token: gh_abc123def456789')  # ✅ <REDACTED>
"
```

### Layer 4: Output Validation (SchemaCatalog)
- Agent outputs validated against Pydantic schemas
- Invalid outputs fail fast with clear errors
- Prevents bad data from flowing downstream

See `API_REFERENCE.md` for schema definitions.

### Layer 5: Supply Chain Verification (DependencyVerifier)
- Pre-flight CVE scanning on application startup
- SHA256 hashing detects compromised dependencies
- Blocks deployment if vulnerabilities found
- Enabled by default: `CONDUCTOR_DEPENDENCY_CHECK_ENABLED=true`

```python
# Runs automatically on startup
# If vulnerabilities found, raises DependencyCheckFailed

# Manual check:
from conductor_core.supply_chain.dependencies import DependencyVerifier

verifier = DependencyVerifier()
result = await verifier.verify("requirements.txt")
if result["has_risks"]:
    print(f"⚠️ {len(result['risks'])} vulnerabilities found")
    for risk in result['risks']:
        print(f"  - {risk['package']}: {risk['cve']}")
else:
    print("✅ All dependencies safe")
```

### A2A HTTP Server (External Framework Integration)
Expose agents as REST endpoints for external frameworks:

```bash
# Start server with mTLS
python main.py --a2a-server --port 8001 --mtls

# Available endpoints:
# GET  /health               — Health check
# GET  /a2a/info             — Server info (agents, port, mTLS status)
# GET  /a2a/agents           — List available agents
# POST /a2a/call             — Call an agent
# GET  /a2a/stats            — Server stats (uptime, calls, errors)
```

Example call:
```bash
curl -X POST http://localhost:8001/a2a/call \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "triage_agent",
    "context": {"run_id": "test-001"},
    "kwargs": {"severity": "HIGH", "source": "snyk"}
  }'
```

With mTLS (production):
```bash
curl -X POST https://localhost:8001/a2a/call \
  --cert ./agent.crt \
  --key ./agent.key \
  --cacert ./ca.crt \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "triage_agent", ...}'
```

See [A2A_SERVER_GUIDE.md](docs/A2A_SERVER_GUIDE.md) for complete setup.

### conductor.json — Project Manifest
Declares what agents exist, what integrations available, and what security settings enabled:

```json
{
  "name": "security-remediation",
  "version": "1.0.0",
  "agents": [
    {"name": "triage_agent", "capabilities": ["triage"]},
    {"name": "code_analyzer", "capabilities": ["analyze"]},
    {"name": "planner_agent", "capabilities": ["plan"]}
  ],
  "integrations": ["snyk", "github", "sonarqube"],
  "settings": {
    "token_scrubber": true,
    "output_validator": true,
    "dependency_check": true,
    "a2a_server": {
      "enabled": false,
      "port": 8001,
      "use_mtls": true
    }
  }
}
```

### Production Deployment Checklist
See [SECURITY_HARDENING.md](docs/SECURITY_HARDENING.md) for the full guide. Quick checklist:

- [ ] All 5 security layers enabled (verify in conductor.json)
- [ ] TokenScrubber active (check logs for no secrets)
- [ ] DependencyVerifier pre-flight check passed
- [ ] mTLS certificates generated and distributed
- [ ] Environment secrets in vault (not .env file)
- [ ] OTEL tracing configured
- [ ] Monitoring/alerting in place
- [ ] Security tests passing: `pytest tests/ -k security -v`

---

## 🚧 Roadmap: Phase 5 — OWASP LLM Top 10 Token Limits

**Status:** Documented in ADR-013, NOT YET IMPLEMENTED

Currently implemented OWASP controls:
- ✅ **LLM-01** (Information Disclosure) — TokenScrubber redacts secrets
- ✅ **LLM-07** (Supply Chain) — DependencyVerifier checks vulnerabilities
- ✅ **LLM-10** (Output Validation) — @validated_agent + SchemaCatalog
- ⚠️ **LLM-04** (Plugin Security) — Input validation partially via Pydantic

**Pending for Phase 5 (estimated 10 hours):**
- ❌ **Token budgets per agent** — `"model_dos_protection": { "max_tokens": 100000 }`
- ❌ **Input size limits** — `"max_input_chars": 50000` in PromptSanitizer
- ❌ **Request timeouts** — Per-agent and per-workflow timeouts
- ❌ **Rate limiting** — Prevent DoS via rapid requests

### How to Enable (Future)

```json
{
  "settings": {
    "model_dos_protection": {
      "max_tokens_per_agent": 100000,
      "max_input_chars": 50000,
      "timeout_sec": 60,
      "rate_limit_per_min": 60
    }
  }
}
```

See [ADR-013](docs/adr/ADR-013-owasp-llm-top-10-security-controls.md) and [THREAT_MODEL.md](docs/THREAT_MODEL.md) for details.

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

## Architecture — End-to-End System Design

The Conductor framework is a **5-layer orchestration platform** for multi-agent AI workflows:

```
┌──────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                 │
├──────────────────────────────────────────────────────────────────────┤
│ Snyk │ SonarQube │ BlackDuck │ Azure DevOps │ GitHub │ REST APIs     │
│                                                                       │
│ ↓ (Work items: CVEs, code issues, defects, PRs, user stories)       │
└──────────────────────────────────────────────────────────────────────┘
                                 ↓
┌──────────────────────────────────────────────────────────────────────┐
│                   WORKFLOW ORCHESTRATOR                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  conductor.json (Manifest)     workflow.yaml (DAG)                   │
│  ├─ Agents list              ├─ Stages (triage → code → review)     │
│  ├─ Integrations             ├─ Gates (parallel execution)          │
│  └─ Security settings        ├─ Routes (rule-based workflow select) │
│                              └─ Filters (pre-filter logic)           │
│                                                                       │
│  WORKFLOW CONTEXT (Mutable State)                                    │
│  ├─ run_id, payload, decisions, metadata                            │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
                                 ↓
        ┌────────────────────────┼────────────────────────┐
        ↓                        ↓                        ↓
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  PRE-AGENT HOOK  │   │ AGENT EXECUTION  │   │ POST-AGENT HOOK  │
├──────────────────┤   ├──────────────────┤   ├──────────────────┤
│ • run_start      │   │ 1. TokenScrubber │   │ • post_agent_run │
│ • filter_match   │   │    (redacts logs)│   │ • decision_made  │
│ • pre_agent_run  │   │                  │   │ • stage_complete │
│ • route_selected │   │ 2. Rate Limiter  │   │ • run_end        │
│                  │   │    (Phase 5)     │   │                  │
│ Fire events to   │   │                  │   │ Fire events to   │
│ hooks registry   │   │ 3. InputLimiter  │   │ hooks registry   │
│                  │   │    (Phase 5)     │   │                  │
│ Can modify       │   │                  │   │ Can trigger      │
│ context/payload  │   │ 4. LLM Call      │   │ notifications    │
│                  │   │    (with model   │   │                  │
│                  │   │     settings)    │   │                  │
│                  │   │                  │   │                  │
│                  │   │ 5. Timeout       │   │                  │
│                  │   │    (Phase 5)     │   │                  │
│                  │   │                  │   │                  │
│                  │   │ 6. @validated_   │   │                  │
│                  │   │    agent         │   │                  │
│                  │   │    (schema       │   │                  │
│                  │   │     validation)  │   │                  │
│                  │   │                  │   │                  │
│                  │   │ 7. TokenLimiter  │   │                  │
│                  │   │    (Phase 5)     │   │                  │
│                  │                       │
└──────────────────┘   └──────────────────┘   └──────────────────┘
                                 ↓
        ┌────────────────────────┼────────────────────────┐
        ↓                        ↓                        ↓
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ FILTERING LAYER  │   │  13+ AGENTS      │   │ OUTPUT VALIDATION│
├──────────────────┤   ├──────────────────┤   ├──────────────────┤
│ Pre-filter rules │   │ • TriageAgent    │   │ @validated_agent │
│ ├─ Source check  │   │ • SecurityAnalyst│   │ decorator checks │
│ ├─ Severity      │   │ • Resolver       │   │ against schemas: │
│ ├─ Duplicates    │   │ • PlannerAgent   │   │                  │
│ ├─ Quota limits  │   │ • CodeAgent      │   │ • SecurityFinding
│ └─ Schedule OK   │   │ • ReviewerAgent  │   │ • CodeGenOutput  │
│                  │   │ • ScribeAgent    │   │ • RemediationPlan
│ Filter.yaml      │   │ • GitAgent       │   │ • DecisionOutput │
│ + runtime logic  │   │ • NotifyAgent    │   │ • ... (20+ total)
│                  │   │ • FeedbackAgent  │   │                  │
│                  │   │ • + more         │   │ Returns error if │
│                  │   │                  │   │ validation fails │
│                  │   │ Each agent:      │   │                  │
│                  │   │ • Has context    │   │                  │
│                  │   │ • Calls LLM      │   │                  │
│                  │   │ • Returns:       │   │                  │
│                  │   │   {decision,     │   │                  │
│                  │   │    confidence,   │   │                  │
│                  │   │    reasoning}    │   │                  │
│                  │                       │
└──────────────────┘   └──────────────────┘   └──────────────────┘
                                 ↓
        ┌────────────────────────┼────────────────────────┐
        ↓                        ↓                        ↓
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  SECURITY LAYER  │   │  MODEL CONTROL   │   │  PERSISTENCE     │
├──────────────────┤   ├──────────────────┤   ├──────────────────┤
│ TokenScrubber:   │   │ LLM Provider:    │   │ SQLiteResultStore
│ • Redacts keys   │   │ • CopilotLLM     │   │ or PostgreSQL    │
│ • Redacts tokens │   │ • OpenAI         │   │                  │
│ • Redacts secrets│   │ • Mock (for dev) │   │ Stores:           │
│ • 10+ patterns   │   │                  │   │ • Run metadata   │
│                  │   │ Model settings:  │   │ • Agent decisions│
│ DependencyChecker│   │ • Model name     │   │ • Token counts   │
│ • CVE checks     │   │ • Temperature    │   │ • Costs/tokens   │
│ • SHA hashing    │   │ • Max tokens     │   │ • Timestamps     │
│ • Supply chain   │   │ • Top-p sampling │   │ • Payloads       │
│                  │   │                  │   │                  │
│ mTLS/A2A Server: │   │ DoS Protection   │   │ Query results:   │
│ • Cert validation│   │ (Phase 5):       │   │ $ conductor runs │
│ • Agent-to-Agent │   │ • max_tokens     │   │ $ conductor trace
│ • HTTP endpoints │   │ • max_input_size │   │ $ conductor plan │
│ • Ports 8001/2   │   │ • timeout_sec    │   │                  │
│                  │   │ • rate_limit_min │   │                  │
│                  │                       │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

### 5-Layer Security Stack:

1. **Input Validation** — Pydantic models enforce agent input schema
2. **TokenScrubber** — Redacts 10+ secret patterns from logs before they're stored
3. **@validated_agent** — Outputs validated against Pydantic schemas; errors logged but don't halt workflow
4. **DependencyChecker** — Pre-flight CVE and SHA256 verification; non-blocking
5. **mTLS/A2A Server** — Agents exposed as authenticated HTTP endpoints (port 8001, optional)

### Configuration Hierarchy:

```
conductor.json          ← What agents exist, security settings
  ↓
workflow.yaml           ← How agents are chained (stages, gates, routes)
  ↓
settings.py             ← Runtime config (LLM, logging, database, etc.)
  ↓
Model DoS Protection    ← Phase 5: Per-agent token budgets, timeouts
```

### Execution Flow Example (Snyk CVE):

```
1. SOURCE INGESTION
   Snyk API → fetch_items() → [CVE-2023-32681, ...]

2. FILTERING
   filter_engine.evaluate() → "security" filter matched? YES → Route to workflow_security.yaml

3. AGENT PIPELINE
   Triage Agent (Stage 1)
   ├─ Pre-hook: fire(PRE_AGENT_RUN)
   ├─ TokenScrubber: redact API keys from logs
   ├─ LLM Call: gpt-4 → "CVSS 6.1, needs fix"
   ├─ @validated_agent: check output schema → ✓
   ├─ Post-hook: fire(POST_AGENT_RUN)
   └─ Persist: SQLite (run_id, agent, confidence, tokens, cost)

   ... (more agents, some in parallel at gates) ...

   Review Gate (Parallel)
   ├─ SecurityGatekeeper → "approve"
   └─ ReviewerAgent → "approve"
   Both complete → Continue

4. OUTPUT VALIDATION
   All outputs validated against SchemaCatalog (20+ schemas)

5. SECURITY CHECK
   TokenScrubber removes any leaked secrets from final output

6. PERSISTENCE
   SQLiteResultStore saves: runs, agent_decisions, context snapshots

7. OPTIONAL: A2A SERVER
   Each agent becomes HTTP endpoint (POST /agents/{agent_name})
   mTLS enforced if --mtls enabled
```

See [SECURITY_HARDENING.md](docs/SECURITY_HARDENING.md), [A2A_SERVER_GUIDE.md](docs/A2A_SERVER_GUIDE.md), and [API_REFERENCE.md](docs/API_REFERENCE.md) for detailed layer documentation.

---

## ⚙️ Best Practices: conductor.json Maintenance

### 1. Keep conductor.json in Sync with Workflows

Every agent referenced in ANY workflow.yaml file must be declared in conductor.json:

```python
# GOOD: All agents declared
conductor.json:
  "agents": ["triage_agent", "code_agent", "review_agent", "git_agent"]

workflow_execute.yaml:
  stages:
    - stage: triage → agent: triage_agent ✅
    - stage: code → agent: code_agent ✅
    - stage: review → agent: review_agent ✅
    - stage: git → agent: git_agent ✅

# BAD: Missing agent in conductor.json
conductor.json:
  "agents": ["triage_agent", "code_agent"]  # ← Missing review_agent

workflow_execute.yaml:
  stages:
    - stage: review → agent: review_agent ❌ FAILS AT RUNTIME
    
Output:
  ❌ agent_not_found: stage=review, agent_key=review_agent
  ❌ workflow BLOCKED: "No agent registered for: 'review_agent'"
```

### 2. Validation Checklist

Use this before pushing a new workflow or agent:

```bash
# 1. Extract all agents referenced in workflows
grep -h "agent:" config/*.yaml | awk '{print $NF}' | sort -u

# 2. Extract all agents declared in conductor.json
jq -r '.agents[].name' conductor.json | sort -u

# 3. Verify they match
# If they don't match, update conductor.json!
```

### 3. Adding a New Agent

When you add a new agent that will be used in any workflow:

1. **First:** Add agent to conductor.json `"agents"` array
2. **Then:** Reference agent in workflow.yaml `agent:` field
3. **Test:** Run workflow to verify agent is found

---

## Running Tests

Conductor has **5 testing levels**, each adding more real dependencies. Pick the right level for your use case:

### Testing Hierarchy

| Level | Name | Speed | LLM | Data Source | Git Ops | Token | Phase 4 Check | When to Use |
|---|---|---|---|---|---|---|---|---|
| 1 | **Unit Tests** | 10s | 🤖 Stub | — | ❌ | None | ✅ | CI/CD, fastest feedback |
| 2 | **Mock Demos** | 30s | 🤖 Stub | Fixture JSON | ❌ | None | ✅✅ | **Validate Phase 4 features** |
| 3 | **Sample Demos** | 2m | ✅ Real | Fixture JSON | 🤖 Stub | `GITHUB_TOKEN` | ✅✅ | See real LLM reasoning |
| 4 | **Integration** | 5m | ✅ Real | Fixture JSON | ✅ Real | Token + org | ✅✅ | Full end-to-end |
| 5 | **Live Mode** | 10m | ✅ Real | ✅ Real APIs | ✅ Real | All tokens | ✅✅ | Production validation |

---

### Quick Start: Running Tests

**First time setup:**
```bash
make setup                      # Install dependencies
```

**Run mock tests (validates Phase 4 features - NO TOKEN NEEDED):**
```bash
make demo                       # Run all 5 scenarios
# OR
make demo-snyk                  # Just Snyk
# OR  
./dev.sh demo snyk security     # Snyk + security workflow
```

**After running, inspect results:**
```bash
conductor runs --store runs.db
conductor trace <run_id>
```

---

### Level 1 — Unit Tests (10 seconds, no tokens)

```bash
make test-unit              # Fast CI-safe tests
# OR
./dev.sh test              # Same thing
```

- ✅ No LLM calls (uses `StubLLM`)
- ✅ No external APIs
- ✅ No git operations
- ✅ No tokens needed
- Use in CI on every push

---

### Level 2 — Mock Demos (30 seconds, no tokens, VALIDATES PHASE 4)

```bash
make demo                   # All 5 scenarios
make demo-snyk              # Just Snyk scenario
./dev.sh demo snyk          # Same
./dev.sh demo snyk security # Snyk + security workflow
./dev.sh demo snyk execute  # Snyk + full pipeline
```

**What runs:**
- `StubLLM` returns instant pre-canned responses
- Fixture JSON (pre-baked mock scanner data)
- All Phase 4 security features validated at runtime
- No git operations

**Output validates:**
- ✅ TokenScrubber initialized
- ✅ Supply chain verification passed
- ✅ @validated_agent schemas working
- ✅ mTLS ready (if A2A server enabled)

---

### Level 3 — Sample Demos (2 minutes, real LLM, fixture data)

```bash
export GITHUB_COPILOT_TOKEN=ghp_...
make demo-sample            # All 5 scenarios with real LLM
make demo-sample-snyk       # Just Snyk
./dev.sh sample snyk        # Same
```

**What runs:**
- ✅ Real GitHub Copilot LLM (gpt-4.1)
- Fixture JSON (still pre-baked)
- 🤖 Stubbed git (no branches/PRs created)

**Use this to:** See real LLM reasoning with predictable data

---

### Level 4 — Integration Tests (5 minutes, real LLM + real git)

```bash
export GITHUB_COPILOT_TOKEN=ghp_...
export GITHUB_ORG=my-test-org
./dev.sh sample snyk default integration  # One scenario
./dev.sh sample-all default integration   # All 5 scenarios

# Cleanup (delete branches/PRs)
./dev.sh clean-integration
```

**What runs:**
- ✅ Real GitHub Copilot LLM
- Fixture JSON (still mocks)
- ✅ **REAL branches + PRs** on test repos

**Use this to:** Full end-to-end validation with real git

---

### Level 5 — Live Mode (10 minutes, everything real)

```bash
export GITHUB_COPILOT_TOKEN=ghp_...
export GITHUB_ORG=my-prod-org
export SNYK_TOKEN=...
export SONAR_TOKEN=...
CONDUCTOR_PROVIDER_MODE=live ./dev.sh sample snyk
```

**What runs:**
- ✅ Real GitHub Copilot LLM
- ✅ Real scanner APIs (Snyk, SonarQube, etc)
- ✅ **REAL branches + PRs** on production repos

**Use this to:** Production validation

---

### Lint

```bash
make lint              # ruff linter across all packages
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
| [docs/context-engineering-rca.md](docs/context-engineering-rca.md) | Defect RCA context engineering (Grafana sample design) |
| [docs/scripts.md](docs/scripts.md) | All scripts with options and examples |
| [conductor-agents/README.md](conductor-agents/README.md) | All 10 agents, prompt guide, how to extend |
| [conductor-core/README.md](conductor-core/README.md) | Framework internals |
| [conductor-integrations/README.md](conductor-integrations/README.md) | Mock + live source/git clients |
| [consumer-showcase/README.md](consumer-showcase/README.md) | Reference consumer and all demo scenarios |
