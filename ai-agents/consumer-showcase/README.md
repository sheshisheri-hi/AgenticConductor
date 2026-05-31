# consumer-showcase

**Reference consumer** demonstrating how to build a full security-remediation pipeline with Conductor. This is Layer 3 — a fully wired, runnable application you can clone, study, and adapt.

It handles findings from Snyk, SonarQube, Black Duck, and Azure DevOps through a multi-stage pipeline (triage → security analysis → resolve → plan), persists results to SQLite, emits OTEL traces, and ships 4 workflow YAML configurations to showcase different pipeline shapes.

---

## Install

```bash
pip install -e .           # installs consumer-showcase + all dependencies
```

Depends on `conductor-agents` → `conductor-core` + `conductor-integrations`.

---

## Quick Start

```bash
# From ai-agents/ root
make setup                 # create .venv, install all packages

# Run one scenario (no LLM token required — uses StubLLM)
cd consumer-showcase
python main.py --scenario snyk --store /tmp/runs.db

# Run all 5 scenarios and persist results
python main.py --all --store /tmp/runs.db

# Run via environment variable
DEMO_SCENARIO=sonar python main.py --store /tmp/runs.db
```

---

## Demo Scenarios

Each scenario uses a real code file in `samples/` and a pre-baked mock JSON in `mocks/`. The `StubLLM` returns realistic per-scenario reasoning without any API calls.

| Scenario | `--scenario` | Source file | Issue |
|---|---|---|---|
| Snyk CVE | `snyk` | `samples/snyk/requirements_vulnerable.txt` | CVE-2023-32681 in `requests 2.18.0` |
| SonarQube | `sonar` | `samples/sonar/auth_handler.py` | SQL injection + hardcoded credential |
| Black Duck | `blackduck` | `samples/blackduck/package_copyleft.py` | GPL-3.0 license violation |
| ADO Defect | `ado-defect` | `samples/ado/buggy_calculator.py` | Off-by-one + division-by-zero |
| ADO Story | `ado-story` | `samples/ado/feature_stub.py` | Unimplemented `paginate()` method |

---

## Pipeline Architecture

```
main.py  →  WorkflowContext(run_id, payload)
                   │
                   ▼
         WorkflowOrchestrator
              │
    ┌─────────┴─────────┐
    ▼                   ▼
FilterEngine        RouterEngine
(reject info/       (snyk/sonar/blackduck → security_remediation
 null repos)         ado              → ado_remediation)
    │
    ▼
 Stage: triage          →  TriageAgent         (severity, risk, route)
    ▼
 Stage: security_analysis →  SecurityAnalystAgent (CVE/SAST analysis)
    ▼                        [skipped for ADO workflow]
 Stage: resolve          →  ResolverAgent      (fix strategy)
    ▼
 Stage: plan             →  PlannerAgent       (ordered steps + PR desc)
    ▼  [HALT in plan mode]
 Stage: code             →  CodeAgent          (diff/patch)
    ▼  [execute mode only]
 Stage: review           →  ReviewerAgent      (adversarial review, diff model)
    ▼
 Stage: scribe           →  ScribeAgent        (PR body, changelog)
    ▼
 Stage: git              →  GitAgent           (branch, commit, PR)
    ▼
 Stage: notify           →  NotifyAgent        (Slack/ADO comment)
    ▼
 Stage: feedback         →  FeedbackAgent      (capture reviewer feedback)
    ▼
 terminal
    │
    ▼
SQLiteResultStore.save_run(context)
  → runs table:      run_id, workflow, source, mode, blocked, tokens, cost
  → decisions table: agent, stage, round, confidence, model_used,
                     prompt_system, prompt_user, raw_llm_response,
                     reasoning, evidence, tokens, latency, cost
```

All 10 agents are imported from **`conductor-agents`** — this consumer is purely wiring.

---

## Module Map

```
consumer-showcase/
├── main.py                         # CLI entry point, StubLLM, scenario wiring
├── config/
│   ├── workflow.yaml               # default (security: snyk/sonar/blackduck)
│   ├── workflow_security.yaml      # plan-only: halts before code stage
│   ├── workflow_ado.yaml           # ADO: skips CVE analysis
│   ├── workflow_execute.yaml       # full 11-stage pipeline
│   └── workflow_adversarial.yaml   # adversarial gate with per-stage model
├── scripts/
│   ├── show_runs.py                # list all runs with tokens/cost
│   ├── show_plan.py                # show fix plan for a run
│   ├── show_trace.py               # full reasoning trace (with prompts/responses)
│   ├── show_all.py                 # everything (runs + traces + plans)
│   ├── show_logs.py                # filter structured JSON log file
│   └── clean_run.py                # delete runs from DB
├── consumer_showcase/
│   └── agents/                     # re-exports from conductor-agents
│       ├── __init__.py
│       ├── triage_agent.py         # backward-compat re-export
│       └── planner_agent.py        # backward-compat re-export
└── tests/
    ├── unit/
    │   └── test_agents.py          # unit tests (stubbed LLM)
    └── integration/
        └── test_scenarios.py       # all 5 scenarios end-to-end
```

---

## Workflow YAML Configurations

Four configurations are included to showcase different pipeline shapes. Select via `--workflow`:

| YAML | Stages | Use case |
|---|---|---|
| `workflow_security.yaml` | triage → analysis → resolve → **plan** [HALT] | Review plan without applying code |
| `workflow_ado.yaml` | triage → resolve → **plan** [HALT] | ADO items — skip CVE analysis |
| `workflow_execute.yaml` | triage → analysis → resolve → plan → code → review → scribe → git → notify → feedback | Fully automated |
| `workflow_adversarial.yaml` | …plan → **review** (model=gpt-4-turbo) → scribe [HALT] | Per-stage model override demo |

```bash
python main.py --scenario snyk --workflow config/workflow_adversarial.yaml --store /tmp/runs.db
```

See [docs/workflow-yaml.md](../docs/workflow-yaml.md) for the full YAML reference.

---

## Agents

All 10 agents live in `conductor-agents` (Layer 2). This consumer just imports and wires them:

| Agent | Stage key | Role |
|---|---|---|
| `TriageAgent` | `triage` | Severity, risk, route decision |
| `SecurityAnalystAgent` | `security_analysis` | CVE scoring, CVSS, attack surface |
| `ResolverAgent` | `resolve` | Fix strategy mapping |
| `PlannerAgent` | `plan` | Ordered fix steps + PR description |
| `CodeAgent` | `code` | Produce diff/patch |
| `ReviewerAgent` | `review` | Adversarial review (different model) |
| `ScribeAgent` | `scribe` | PR body, changelog, ticket comment |
| `GitAgent` | `git` | Branch, commit, open PR |
| `NotifyAgent` | `notify` | Slack/Teams/ADO notification |
| `FeedbackAgent` | `feedback` | Capture reviewer feedback |

**To update an agent's prompts or behaviour:** edit the files in `conductor-agents/conductor_agents/agents/<name>/prompts/`. No Python changes needed. See [conductor-agents/README.md](../conductor-agents/README.md).

---

## Operational Scripts

```bash
# List all runs (with workflow, source, tokens, cost)
python scripts/show_runs.py --store /tmp/runs.db

# Show fix plan
python scripts/show_plan.py --store /tmp/runs.db --run SNYK-001-demo

# Full reasoning trace (agent decisions, model used, confidence)
python scripts/show_trace.py --store /tmp/runs.db --run SNYK-001-demo

# Trace with prompts + raw LLM responses (full audit)
python scripts/show_trace.py --store /tmp/runs.db --run SNYK-001-demo --prompts --raw

# Everything (all runs + traces + plans)
python scripts/show_all.py --store /tmp/runs.db

# View structured logs
python main.py --scenario snyk --store /tmp/runs.db --log-file /tmp/conductor.log
python scripts/show_logs.py --log /tmp/conductor.log --events
python scripts/show_logs.py --log /tmp/conductor.log --run SNYK-001-demo

# Delete a run
python scripts/clean_run.py --store /tmp/runs.db --run SNYK-001-demo
python scripts/clean_run.py --list --store /tmp/runs.db
```

See [docs/scripts.md](../docs/scripts.md) for full options reference.

---

## Persistence

Results are saved to SQLite automatically when `--store` is provided:

```bash
python main.py --all --store runs.db

# Query programmatically
import asyncio
from conductor_core.stores.sqlite_store import SQLiteResultStore

async def main():
    store = SQLiteResultStore("runs.db")
    runs = await store.list_runs(limit=10)
    for r in runs:
        print(r["run_id"], r["workflow"], r["total_tokens"], f"${r['estimated_cost_usd']:.4f}")

    # Get full reasoning trace with prompts + raw responses
    decisions = await store.get_decisions("SNYK-001-demo")
    for d in decisions:
        print(d["agent_name"], d["model_used"], d["recommendation"])
        print("  prompt:", d["prompt_user"][:80])
        print("  raw_response:", d["raw_llm_response"][:80])

asyncio.run(main())
```

Every decision stores: agent name, stage, round, confidence, model used, **system prompt verbatim**, **user prompt verbatim**, **raw LLM response verbatim**, reasoning bullets, tokens, latency, cost.

---

## Adding a Real LLM

Replace `StubLLM` with the Copilot provider:

```python
# main.py — swap this line:
llm = _build_stub_llm(scenario)

# with:
from conductor_core.providers.copilot import CopilotLLMProvider
llm = CopilotLLMProvider()           # reads GITHUB_TOKEN from env
```

Then set:
```bash
GITHUB_TOKEN=ghp_...                 # PAT with Copilot subscription
CONDUCTOR_PROVIDER_MODE=live
CONDUCTOR_LLM_MODEL=gpt-4o           # or gpt-4-turbo, o1-preview, etc.
CONDUCTOR_REVIEWER_MODEL=gpt-4-turbo # adversarial reviewer uses a different model
```

---

## Running Tests

```bash
cd consumer-showcase

# Unit tests (fast, no LLM)
pytest tests/unit -q

# Integration tests (end-to-end pipeline, still no real LLM)
pytest tests/integration -q

# All together
pytest tests/ -q     # 116 tests total across all packages
```

---

## Adapting for Your Domain

To use this as a starting point for your own consumer:

1. **Import agents** from `conductor-agents` — no need to copy or rewrite agent code
2. **Write** `config/workflow.yaml` — filters, routes, stages for your domain
3. **Update prompts** in `conductor-agents/conductor_agents/agents/<name>/prompts/` — no Python needed
4. **Replace** `StubLLM` with your real LLM provider
5. **Add** any custom agents if needed (extend `BaseAgent`, write prompt files)

See [docs/consumer-guide.md](../docs/consumer-guide.md) for a full step-by-step walkthrough.
