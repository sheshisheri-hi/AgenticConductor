# conductor-core

The **generic multi-agent workflow orchestration framework**. This package has zero domain knowledge — it knows nothing about Snyk, ADO, or security. Any consumer can build any multi-agent pipeline on top of it.

---

## Install

```bash
pip install conductor-core          # from PyPI (future)
pip install -e .                    # editable local install
```

---

## Core Concepts

| Concept | Class | Description |
|---|---|---|
| **Context** | `WorkflowContext` | Carries `run_id`, `payload`, `decisions`, `telemetry` through the pipeline |
| **Agent** | `IAgent` / `BaseAgent` | One async method: `run(ctx) → AgentDecision` |
| **Decision** | `AgentDecision` | `recommendation` (proceed/block/escalate), `confidence`, `reasoning` |
| **Graph** | `WorkflowGraph` | Loaded from YAML — stages, filters, routes, mode |
| **Orchestrator** | `WorkflowOrchestrator` | Drives context through stages, persists result |
| **Filter Engine** | `FilterEngine` | Pre-stage rejection rules (zero LLM cost) |
| **Router Engine** | `RouterEngine` | Tags route from payload fields |
| **Result Store** | `IResultStore` / `SQLiteResultStore` | Persists every run for audit/replay |
| **Tracing** | `get_tracer()` | OTEL spans per stage — NoOp when no endpoint configured |

---

## Module Map

```
conductor_core/
├── interfaces.py        # IAgent, ILLMProvider, IResultStore  (contracts only)
├── context.py           # WorkflowContext, TelemetryData
├── decisions.py         # AgentDecision dataclass
├── base_agent.py        # BaseAgent — handles LLM call, JSON parse, telemetry
├── orchestrator.py      # WorkflowOrchestrator — main entry point
├── graph.py             # WorkflowGraph.from_yaml()
├── filter_engine.py     # FilterEngine, FilterResult
├── router_engine.py     # RouterEngine
├── tracing.py           # configure_tracing(), get_tracer()
├── exceptions.py        # ConductorError, AgentError, ConfigError
├── config/
│   └── settings.py      # ConductorSettings (pydantic-settings, reads .env)
├── runners/
│   └── sequential.py    # SequentialRunner — runs one agent, times it
└── stores/
    └── sqlite_store.py  # SQLiteResultStore (aiosqlite, upsert via ON CONFLICT)
```

---

## Workflow YAML

```yaml
workflow:
  name: my_pipeline
  mode: plan              # plan = read-only reasoning | execute = real side effects

filters:
  - field: severity
    reject_if_in: [info, low]
  - field: work_item.repo_name
    reject_if_null: true

routes:
  - match_field: work_item.source
    match_values: [snyk, sonar]
    route: security_remediation
  - match_field: "*"
    route: escalate_human

stages:
  - name: triage
    agent: triage          # key in agents dict passed to WorkflowOrchestrator
    on_proceed: plan
    on_block: terminal
    on_escalate: terminal

  - name: plan
    agent: planner
    on_proceed: terminal
    stop_before: true      # plan mode halts here (won't execute)
```

---

## Writing an Agent

```python
from conductor_core.base_agent import BaseAgent
from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision

class MyAgent(BaseAgent):
    AGENT_NAME = "my_agent"

    _SYSTEM = "You are a helpful assistant..."
    _USER_TEMPLATE = "Analyse: $title"

    async def run(self, ctx: WorkflowContext) -> AgentDecision:
        user_prompt = self._USER_TEMPLATE.replace("$title", ctx.payload["title"])
        response = await self._call_llm(self._SYSTEM, user_prompt, ctx)
        decision = self._parse_decision(response)
        ctx.append_decision(decision)
        return decision
```

`BaseAgent._call_llm()` handles:
- LLM call via injected `ILLMProvider`
- Token counting + latency tracking into `ctx.telemetry`
- Structured JSON parsing + validation
- Retry on malformed responses

---

## Wiring an Orchestrator

```python
import asyncio
from conductor_core.graph import WorkflowGraph
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.context import WorkflowContext
from conductor_core.stores.sqlite_store import SQLiteResultStore

graph = WorkflowGraph.from_yaml("workflow.yaml")
store = SQLiteResultStore("runs.db")

orch = WorkflowOrchestrator(
    agents={"triage": MyTriageAgent(llm), "planner": MyPlannerAgent(llm)},
    graph=graph,
    result_store=store,        # optional — omit to skip persistence
)

ctx = WorkflowContext(run_id="WI-001", payload={"title": "SQL injection found"})
result = await orch.run(ctx)

print(result.decisions)        # list[AgentDecision]
print(result.telemetry.total_tokens)
print(result.blocked)
```

---

## Result Store

```python
from conductor_core.stores.sqlite_store import SQLiteResultStore

store = SQLiteResultStore("conductor_runs.db")

# Get one run
run = await store.get_run("WI-001")

# List recent runs
runs = await store.list_runs(limit=50)
```

Schema stored per run: `run_id`, `workflow`, `mode`, `blocked`, `blocked_reason`, `pipeline_route`, `decisions` (JSON), `telemetry` (JSON), `payload` (JSON), `started_at`, `completed_at`.

---

## Telemetry

`WorkflowContext.telemetry` (`TelemetryData`) tracks automatically:

```python
result.telemetry.total_tokens          # int — total tokens across all agents
result.telemetry.per_agent             # dict[agent_name, {tokens, calls, latency_ms}]
result.telemetry.total_latency_ms      # float
result.telemetry.recode_rounds         # int — LLM retry rounds
```

---

## OTEL Tracing

Zero config needed for local dev (NoOp). Enable for Jaeger / Honeycomb / Datadog:

```bash
CONDUCTOR_OTEL_ENDPOINT=http://localhost:4317
CONDUCTOR_OTEL_SERVICE_NAME=conductor
```

Span hierarchy:
```
workflow:<name>
  ├── stage:triage    → attributes: agent, recommendation, confidence
  └── stage:plan      → attributes: agent, recommendation, confidence
```

---

## Configuration

All settings via `ConductorSettings` (reads from `.env` or environment):

```python
from conductor_core.config.settings import get_settings
s = get_settings()
print(s.llm_model)            # gpt-4o
print(s.db_url)               # sqlite+aiosqlite:///conductor_runs.db
print(s.otel_endpoint)        # None (unless set)
```

| Setting | Env var | Default |
|---|---|---|
| `llm_model` | `CONDUCTOR_LLM_MODEL` | `gpt-4o` |
| `confidence_threshold` | `CONDUCTOR_CONFIDENCE_THRESHOLD` | `0.7` |
| `provider_mode` | `CONDUCTOR_PROVIDER_MODE` | `mock` |
| `db_url` | `CONDUCTOR_DB_URL` | `sqlite+aiosqlite:///conductor_runs.db` |
| `otel_endpoint` | `CONDUCTOR_OTEL_ENDPOINT` | `None` |
| `otel_service_name` | `CONDUCTOR_OTEL_SERVICE_NAME` | `conductor` |

---

## Tests

```bash
cd conductor-core
pytest tests/unit -q          # 91 tests, ~0.2s, no LLM needed
```

Test coverage includes: orchestrator (plan/execute/filter/route), filter engine, router engine, context/telemetry, decisions, graph parsing, result store, settings, tracing.
