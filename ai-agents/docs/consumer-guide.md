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

---

## Step 1: Create the Package

```bash
mkdir my-consumer && cd my-consumer

# Minimal structure
mkdir -p my_consumer/agents
mkdir -p config
mkdir -p tests/unit tests/integration

touch my_consumer/__init__.py
touch my_consumer/agents/__init__.py
```

`pyproject.toml`:
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

```bash
pip install -e "../../conductor-core"
pip install -e "../../conductor-agents"
pip install -e "../../conductor-integrations"
pip install -e ".[dev]"
```

---

## Step 2: Define Your Payload Shape

Conductor's `WorkflowContext.payload` is a plain `dict`. For security findings use the pre-built `WorkItem`:

```python
from conductor_integrations.models import WorkItem

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

For custom domains, put whatever you want in `payload`:
```python
payload = {
    "ticket": {"id": "INC-42", "priority": "P1", "title": "..."},
    "service": "checkout-api",
    "environment": "production",
}
```

---

## Step 3: Write the Workflow YAML

```yaml
# config/workflow.yaml
workflow:
  name: my_pipeline
  mode: plan

filters:
  - field: ticket.priority
    reject_if_in: [p4, p5]

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

See [workflow-yaml.md](workflow-yaml.md) for the full YAML reference.

---

## Step 4: Use Existing Agents (Recommended)

Import agents from `conductor-agents` — no agent code to write:

```python
from conductor_agents import TriageAgent, PlannerAgent, ReviewerAgent
```

See [../conductor-agents/README.md](../conductor-agents/README.md) for all 10 agents and their contracts.

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
    store = SQLiteResultStore(db_path)

    orch = WorkflowOrchestrator(
        agents={
            "triage":  TriageAgent(LLM),
            "planner": PlannerAgent(LLM),
        },
        graph=graph,
        result_store=store,
    )

    ctx = WorkflowContext(run_id=run_id, payload=payload)
    return await orch.run(ctx)

if __name__ == "__main__":
    item = {"id": "INC-42", "title": "...", "priority": "p1", ...}
    result = asyncio.run(run("INC-42-demo", {"ticket": item}))
    print(f"Blocked: {result.blocked}")
    print(f"Decisions: {len(result.decisions)}")
    for d in result.decisions:
        print(f"  [{d.agent_name}] {d.recommendation} conf={d.confidence:.2f}")
```

---

## Step 8: Read Results Back

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

## Adding Real LLM + Live Sources

```bash
# .env
CONDUCTOR_PROVIDER_MODE=live
CONDUCTOR_LLM_MODEL=gpt-4o
GITHUB_TOKEN=ghp_...

# For adversarial reviewer to use a different model
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
