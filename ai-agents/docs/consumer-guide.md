# Building a New Consumer

This guide walks you through creating a new Conductor consumer from scratch — wiring existing agents into a custom pipeline for your domain.

---

## Overview

A **consumer** is a thin application that:
1. Provides domain payload (your work items / findings / tickets)
2. Selects which agents to use (import from `conductor-agents` or write your own)
3. Writes a `workflow.yaml` defining the pipeline
4. Wires everything together in `main.py`

The framework handles orchestration, LLM calling, multi-round reasoning, telemetry, tracing, and persistence automatically.

For **defect RCA + product memory (glossary / similar bugs / ownership)**, see [context-engineering-rca.md](context-engineering-rca.md) and the runnable sample [`samples/projects/grafana-rca/`](../samples/projects/grafana-rca/).

---

## Step 1: Create the Package

> **What is a "package" in Python?** It's just a folder with a `pyproject.toml` file — the modern equivalent of `setup.py`. This tells pip the package name, version, and what it depends on. You don't need to publish it anywhere; `pip install -e .` installs it locally in "editable" mode so your code changes are reflected immediately without reinstalling.

```bash
mkdir my-consumer && cd my-consumer

# Minimal folder structure
mkdir -p my_consumer/agents
mkdir -p config
mkdir -p tests/unit tests/integration

touch my_consumer/__init__.py
touch my_consumer/agents/__init__.py
```

`pyproject.toml` — create this file in the `my-consumer/` root:
```toml
[project]
name = "my-consumer"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "conductor-agents",
    "conductor-integrations",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]
```

**Install the packages** — run these from inside the `my-consumer/` folder. These commands do **not** download from PyPI; they install from the local cloned monorepo source into your virtual environment:

```bash
# From inside my-consumer/ — installs Conductor packages from the local repo
pip install -e "../../conductor-core"          # framework: BaseAgent, Orchestrator, Graph, Store
pip install -e "../../conductor-agents"        # 10 pre-built domain agents
pip install -e "../../conductor-integrations"  # source/git/notify clients (Snyk, ADO, etc.)
pip install -e ".[dev]"                        # installs my-consumer itself + dev tools (pytest)
```

> The `-e` flag means "editable" — any change to Conductor source code is immediately available without reinstalling. Packages are registered in your virtualenv's `site-packages` as a reference to the source folder (no files are copied to `pycache`).

---

## Step 2: Define Your Payload Shape

`WorkflowContext.payload` is a plain `dict` that flows through every agent in the pipeline. Think of it as the "work order" — agents read from it and write back their results as they run.

**For security findings** (Snyk, SonarQube, BlackDuck, ADO), use the pre-built `WorkItem` model — this is what `consumer-showcase` uses. Pre-built models include: `WorkItem` (generic finding), `SnykFinding`, `SonarIssue`, `BlackDuckAlert`, `ADOWorkItem`. See [conductor-integrations/README.md](../conductor-integrations/README.md) for the full list.

```python
from conductor_integrations.models import WorkItem

# This is what your ingest pipeline provides — from a Snyk webhook, an ADO query, etc.
item = WorkItem(
    id="JIRA-1234",
    source="jira",
    severity="HIGH",
    type="bug",
    title="Null pointer in payment handler",
    description="PaymentHandler.process() throws NPE when amount=None",
    file_path="src/payments/handler.py",
    repo_name="payment-service",
)
payload = {"work_item": item.model_dump()}
```

**For custom domains** — put whatever you need in the dict:
```python
# Example: PR review agent
payload = {
    "pull_request": {"id": "PR-789", "title": "Add auth middleware", "diff_url": "..."},
    "repo": "api-gateway",
    "author": "dev-team",
}

# Example: incident response agent
payload = {
    "incident": {"id": "INC-42", "priority": "P1", "title": "Payment service down"},
    "service": "checkout-api",
    "environment": "production",
    "runbook_url": "https://...",
}

# Example: compliance check agent
payload = {
    "audit_item": {"control": "SOC2-CC6.1", "finding": "MFA not enforced", "risk": "HIGH"},
    "tenant": "customer-xyz",
}
```

---

## Step 3: Write the Workflow YAML

The workflow YAML defines your pipeline declaratively — no Python code for routing logic. The 5 built-in YAMLs in `consumer-showcase/config/` are good starting points.

**YAML structure:**

| Section | Purpose |
|---|---|
| `workflow.name` | Logical name of this pipeline (used in traces and logs) |
| `workflow.mode` | `plan` (stops before code/git) or `execute` (runs all agents including git/PR) |
| `filters` | Pre-flight rules run **before any LLM call** — reject items that don't match criteria (e.g. skip INFO severity). Zero token cost. |
| `routes` | Match payload fields to route tags — lets one YAML handle multiple paths (e.g. snyk vs ado gets a different graph). |
| `stages` | Ordered list of pipeline steps. Each stage names an agent and defines what happens on `proceed`, `block`, or `escalate`. |
| `stages[].groups` | **Parallel runner** — multiple agents run concurrently in one stage (e.g. a review team, notification fan-out). All must proceed for the pipeline to continue. |
| `stages[].model` | Override the LLM model just for this stage (e.g. use `o1-preview` for the adversarial review stage only). |
| `stages[].stop_before: true` | Plan mode gate — pipeline halts here without running this stage. Used to separate "plan" from "execute". |

```yaml
# config/workflow.yaml
workflow:
  name: my_pipeline
  mode: plan

filters:
  - field: ticket.priority
    reject_if_in: [p4, p5]   # don't waste tokens on low priority

routes:
  - match_field: ticket.priority
    match_values: [p1, p2]
    route: critical_path
  - match_field: "*"
    route: standard_path

stages:
  - name: triage
    agent: triage
    on_proceed: plan
    on_block: terminal
    on_escalate: terminal

  - name: plan
    agent: planner
    on_proceed: terminal
    on_block: terminal
    stop_before: true    # remove this for execute mode

  - name: terminal
```

See [workflow-yaml.md](workflow-yaml.md) for the complete YAML reference including parallel groups, model overrides, and all filter operators.

---

## Step 4: Use Existing Agents (Recommended)

Import agents from `conductor-agents` — no agent code to write:

```python
from conductor_agents import TriageAgent, PlannerAgent, ReviewerAgent
```

**All 10 built-in agents** and their contracts: [../conductor-agents/README.md](../conductor-agents/README.md)

Each agent in `conductor-agents` has a `SKILL.md` file — this is the **agent's "contract document"**: what inputs it expects in the payload, what it writes back, what models it supports, and when to use it. Read the SKILL.md before wiring an agent into your pipeline. Example: `conductor-agents/conductor_agents/agents/triage/SKILL.md`.

---

## Step 5: Write Custom Agents (Optional)

If existing agents don't fit, create your own by extending `BaseAgent`:

```python
# my_consumer/agents/intake_agent.py
from pathlib import Path
from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext

class IntakeAgent(BaseAgent):
    AGENT_NAME = "intake"

    def __init__(self, llm, **kwargs):
        super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts", **kwargs)

    def _get_system_prompt_name(self) -> str:
        return "intake_system"

    def _get_user_prompt_name(self) -> str:
        return "intake_user"

    def _get_prompt_variables(self, ctx: WorkflowContext, round_num: int) -> dict:
        ticket = ctx.payload.get("ticket", {})
        return {
            "ticket_id":    ticket.get("id", ""),
            "title":        ticket.get("title", ""),
            "priority":     ticket.get("priority", ""),
            "description":  ticket.get("description", ""),
        }
```

Create prompt files:
```
my_consumer/agents/prompts/
├── intake_system.md     ← system role / persona
└── intake_user.md       ← per-call context (uses $variable substitution)
```

`intake_system.md`:
```markdown
You are an intake agent for incident triage. Your job is to classify
incoming incidents and decide whether to escalate immediately or
follow standard remediation.

Respond in JSON:
{
  "recommendation": "proceed" | "block" | "escalate",
  "confidence": 0.0-1.0,
  "reasoning": ["bullet 1", "bullet 2"],
  "evidence": ["supporting fact"],
  "concerns": ["concern if any"]
}
```

`intake_user.md`:
```markdown
Incident: $ticket_id
Priority: $priority
Title: $title

Description:
$description
```

---

## Step 6: Set Up the LLM

**For testing — StubLLM (no API calls):**

```python
from conductor_core.interfaces import ILLMProvider
from conductor_core.decisions import AgentDecision

class StubLLM(ILLMProvider):
    async def call(self, system_prompt: str, user_prompt: str, model: str = "") -> str:
        return '{"recommendation":"proceed","confidence":0.9,"reasoning":["stub"],"evidence":[],"concerns":[]}'
```

**For production — Copilot provider:**

```python
from conductor_core.providers.copilot import CopilotLLMProvider
llm = CopilotLLMProvider()   # reads GITHUB_TOKEN from env
```

---

## Step 7: Wire Everything in main.py

```python
# my_consumer/main.py
import asyncio
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.graph import WorkflowGraph
from conductor_core.context import WorkflowContext
from conductor_core.stores.sqlite_store import SQLiteResultStore
from conductor_agents import TriageAgent, PlannerAgent
# from my_consumer.agents.intake_agent import IntakeAgent  # custom agent

LLM = StubLLM()  # replace with CopilotLLMProvider() for live

async def run(run_id: str, payload: dict, db_path: str = "runs.db") -> WorkflowContext:
    graph = WorkflowGraph.from_yaml("config/workflow.yaml")

    # SQLiteResultStore for dev/test — set CONDUCTOR_DB_URL for Postgres in production
    # Implements IResultStore — swap for PostgresResultStore without changing agent code
    store = SQLiteResultStore(db_path)

    orch = WorkflowOrchestrator(
        agents={
            "triage":  TriageAgent(LLM),
            "planner": PlannerAgent(LLM),
        },
        graph=graph,
        result_store=store,
    )

    # payload comes from your ingest pipeline — a Snyk webhook, ADO query, manual trigger, etc.
    # In production this is NOT hardcoded; it's populated by your source client (SnykClient, ADOClient, etc.)
    ctx = WorkflowContext(run_id=run_id, payload=payload)
    return await orch.run(ctx)

if __name__ == "__main__":
    # Example: replace this with a call to your real ingest client
    item = {"id": "INC-42", "title": "...", "priority": "p1"}
    result = asyncio.run(run("INC-42-demo", {"ticket": item}))
    print(f"Blocked: {result.blocked}")
    print(f"Decisions: {len(result.decisions)}")
    for d in result.decisions:
        print(f"  [{d.agent_name}] {d.recommendation} conf={d.confidence:.2f}")
```

---

## Step 8: Read Results Back

> **`SQLiteResultStore`** stores everything automatically when you pass it to the orchestrator. Two tables: `runs` (one row per execution) and `agent_decisions` (one row per agent call — full prompt, response, reasoning, model used). The path is set via `CONDUCTOR_DB_URL` env var or passed directly as a string.

```python
from conductor_core.stores.sqlite_store import SQLiteResultStore

async def show():
    store = SQLiteResultStore("runs.db")

    # Get a specific run
    run = await store.get_run("INC-42-demo")
    print(run["plan_markdown"])

    # List recent runs
    runs = await store.list_runs(limit=20)
    for r in runs:
        print(r["run_id"], r["workflow"], r["total_tokens"], f"${r['estimated_cost_usd']:.4f}")

    # Get all decisions (prompts, responses, model used)
    decisions = await store.get_decisions("INC-42-demo")
    for d in decisions:
        print(d["agent_name"], d["model_used"], d["recommendation"])
        print("  PROMPT:", d["prompt_user"][:100])
        print("  RESPONSE:", d["raw_llm_response"][:100])
```

---

## Step 9: Run the Operational Scripts

The consumer-showcase scripts work for any SQLite database:

```bash
# List all runs
python ../../consumer-showcase/scripts/show_runs.py --store runs.db

# Show fix plan for a run
python ../../consumer-showcase/scripts/show_plan.py --store runs.db --run INC-42-demo

# Show full reasoning trace (with prompts + responses)
python ../../consumer-showcase/scripts/show_trace.py --store runs.db --run INC-42-demo --prompts --raw

# Show everything
python ../../consumer-showcase/scripts/show_all.py --store runs.db
```

---

## Settings & Environment Variable Hierarchy

Conductor uses **pydantic-settings** with a two-level inheritance chain:

```
ConductorSettings  (env_prefix="CONDUCTOR_")   ← framework base, lives in conductor-core
    └── ConsumerSettings (env_prefix="CONSUMER_")  ← your consumer, add your own vars here
```

**How the prefix works:**  
pydantic-settings reads `.env` and shell env, then strips the prefix to map to field names.  
- `CONDUCTOR_LLM_MODEL` → `ConductorSettings.llm_model`  
- `CONSUMER_SNYK_TOKEN` → `ConsumerSettings.snyk_token`  
- Fields with an explicit `alias=` (e.g. `alias="GITHUB_ORG"`) bypass the prefix entirely.

**Important:** pydantic-settings does **not** write to `os.environ`. If you need an env var accessible via `os.getenv()` outside pydantic (e.g. in a third-party library), always declare it as a field with `alias=`.

**Override precedence** (highest wins):
1. Shell environment variables
2. `.env` file
3. Field `default=` values

**To add your own env vars**, extend `ConsumerSettings`:
```python
from consumer_showcase.config.settings import ConsumerSettings
from pydantic import Field

class MyConsumerSettings(ConsumerSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_", env_file=".env", extra="ignore")

    my_api_key: str | None = Field(default=None)          # reads MYAPP_MY_API_KEY
    github_org: str = Field(default="", alias="GITHUB_ORG")  # reads GITHUB_ORG directly (no prefix)
```

**Full variable reference:**

| Variable | Prefix | Description |
|---|---|---|
| `CONDUCTOR_PROVIDER_MODE` | framework | `mock` / `sample` / `live` |
| `CONDUCTOR_LLM_MODEL` | framework | Default model (`gpt-4.1`) |
| `CONDUCTOR_REVIEWER_MODEL` | framework | Adversarial reviewer model (auto-differs from planner) |
| `CONDUCTOR_CODE_EXECUTION_ENABLED` | framework | `true` to run git/PR in execute mode |
| `CONDUCTOR_DB_URL` | framework | SQLite path or Postgres URL for result store |
| `CONDUCTOR_GIT_TOKEN` | framework | PAT for git push + PR creation (`repo` scope) |
| `GITHUB_ORG` | alias | Target GitHub org/user for git agent |
| `CONSUMER_SNYK_TOKEN` | consumer | Snyk API token (live mode) |
| `CONSUMER_SONAR_TOKEN` | consumer | SonarQube/SonarCloud token |
| `CONSUMER_BLACKDUCK_TOKEN` | consumer | Black Duck API token |
| `CONSUMER_ADO_PAT` | consumer | Azure DevOps PAT |

---

## Adding Real LLM + Live Sources

```bash
# .env
CONDUCTOR_PROVIDER_MODE=live
CONDUCTOR_LLM_MODEL=gpt-4o
CONDUCTOR_GIT_TOKEN=ghp_...   # classic PAT with 'repo' scope

# Adversarial reviewer auto-picks a different model; override if needed:
CONDUCTOR_REVIEWER_MODEL=gpt-4-turbo
```

Then swap the StubLLM:
```python
from conductor_core.providers.copilot import CopilotLLMProvider
LLM = CopilotLLMProvider()
```

---

## Reusing vs Writing Agents

| Situation | Recommendation |
|---|---|
| Standard security remediation (CVE, SAST, license) | Import all from `conductor-agents` |
| Custom domain (incidents, compliance, legal) | Extend `BaseAgent`, write custom prompts |
| Existing agent needs different prompt tone/output | Edit prompt files in `conductor-agents` |
| Existing agent needs totally different logic | Subclass the agent, override `_get_prompt_variables` |
| Need parallel agents (e.g. concurrent review + notify) | Use `parallel` runner type in stage config |

---

## Checklist

- [ ] `pyproject.toml` with correct dependencies
- [ ] `config/workflow.yaml` with stages, filters, routes
- [ ] Agents wired in `main.py` agents dict
- [ ] LLM provider set (stub for tests, real for production)
- [ ] `SQLiteResultStore` passed to orchestrator
- [ ] `.env` with `CONDUCTOR_PROVIDER_MODE=mock` for local dev
- [ ] Unit tests using `StubLLM` (no API calls)
- [ ] Integration tests exercising full pipeline end-to-end
