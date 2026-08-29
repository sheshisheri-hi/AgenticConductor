# AgenticConductor

**A YAML-driven multi-agent orchestration kernel for governed AI workflows.**

Write agents + a workflow graph. Get confidence gating, plan/execute modes, parallel adversarial review, an append-only audit trail, and mock-first tests without pulling in LangGraph or a SaaS coding agent.

> **Status: proof of concept / experiment.** This is a personal research project, not a product. It is not production-certified, not published on PyPI, and not a drop-in replacement for Devin, MetaGPT, CrewAI, LangGraph, or AutoGen. Use it to learn the architecture, run the samples, and fork the ideas. Do not treat checkpoint docs or “Phase 4” language as a production SLA.

**LinkedIn / narrative write-up:** [docs/LINKEDIN_PRESENTATION.md](docs/LINKEDIN_PRESENTATION.md)

---

## What this is

Conductor is a **framework**, not an autonomous employee.

You ingest a work item (CVE, SAST finding, ADO ticket, incident). A **filter engine** drops noise before any LLM call. A **router** picks a YAML graph. Agents run as stages: each returns `proceed` / `block` / `escalate` plus confidence and reasoning. The orchestrator persists every prompt, response, and decision so you can `conductor trace` a run later.

The reference consumer is **security remediation**: Snyk / Sonar / BlackDuck / ADO → plan → optional code + PR. The core (`conductor-core`) has **no domain knowledge** — a different consumer can wire incident RCA, compliance, or custom agents on the same kernel.

```
work item
    │
    ▼
FilterEngine  ── reject_if_in / reject_if_null / dedup   (zero LLM cost)
    │
    ▼
RouterEngine  ── payload field → workflow graph
    │
    ▼
WorkflowOrchestrator  (YAML stages + parallel groups)
    │     sequential agent  →  AgentDecision
    │     parallel group    →  merge (all_must_pass | majority_vote | first_pass)
    │     stop_before       →  plan mode halt (no git / no PR)
    ▼
SQLite / Postgres  +  OpenTelemetry  +  conductor CLI
```

---

## What this is not

| This repo is not… | Why that matters |
|---|---|
| **Devin** | Devin is a closed product that *is* the engineer. Conductor is a kernel you embed and govern. It will not autonomously explore a repo, write a feature, and ship a PR unless *you* write those agents and flip execute mode. |
| **MetaGPT** | MetaGPT simulates a software company (PM → architect → engineer → QA) from a one-line PRD. Conductor does not generate products from a sentence. It runs a **declared pipeline** over inbound work items. |
| **CrewAI / AutoGen group chat** | Those tools optimize for role crews and shared-thread debate. Conductor’s review gate fires agents **in parallel with no shared transcript** so they cannot anchor each other (see [ADR-005](ai-agents/docs/adr/ADR-005-parallel-runners-not-group-chat.md)). |
| **LangGraph** | LangGraph is a strong fit for ReAct tool loops and dynamic graphs. Conductor chose a custom YAML pipeline to keep `conductor-core` light and make topology a config file ([ADR-008](ai-agents/docs/adr/ADR-008-custom-orchestration-vs-langgraph.md)). |
| **Production SaaS** | Security layers (token scrubbing, mTLS, schema validation) are **experimental controls in a PoC**. They are not a certified control set. |

A longer comparison, including what those systems still do better, is in [docs/LINKEDIN_PRESENTATION.md](docs/LINKEDIN_PRESENTATION.md#how-it-compares).

---

## Why the design looks this way

These are the bets encoded in the ADRs — useful if you are deciding whether to read the code:

1. **Topology is YAML, not Python.** Security teams should reorder stages, add a reviewer, or halt before git without a deploy. ([ADR-002](ai-agents/docs/adr/ADR-002-yaml-driven-workflow-graph.md))
2. **Confidence is first-class.** `BaseAgent` loops: call LLM → parse JSON → if confidence is low, enrich and retry → else escalate. That is not a LangGraph default.
3. **Plan vs execute is a flag, not a rewrite.** `stop_before: true` on a stage is how plan mode refuses to push a branch. ([ADR-006](ai-agents/docs/adr/ADR-006-plan-execute-mode-stop-before.md))
4. **Reviewers must not groupthink.** Parallel runners use `asyncio.gather`; merge strategy is in YAML. Group-chat debate is explicitly *not* the review-gate model.
5. **No shared chat memory across agents.** Each LLM call is a fresh session ([ADR-004](ai-agents/docs/adr/ADR-004-per-call-session-isolation.md)).
6. **Mock first.** `StubLLM` + fixture JSON means CI and first-run demos need **no tokens** ([ADR-007](ai-agents/docs/adr/ADR-007-stub-llm-mock-first-development.md)).
7. **Every decision is replayable.** Prompts and raw responses are stored verbatim. `conductor trace <run_id> --prompts --raw` is the audit UI.

---

## Repository layout

The GitHub repo root is thin. **Runnable code lives under `ai-agents/`.**

```
AgenticConductor/
├── README.md                          ← you are here (developer overview)
├── docs/LINKEDIN_PRESENTATION.md      ← narrative + comparison for sharing
└── ai-agents/                         ← the framework
    ├── conductor-core/                # Layer 1: BaseAgent, Orchestrator, Graph, Store
    ├── conductor-agents/              # Layer 2: 10 domain agents + SKILL.md + prompts
    ├── conductor-integrations/        # Layer 2: Snyk / Sonar / ADO / git / notify clients
    ├── conductor-cli/                 # Layer 3: conductor runs | plan | trace | check
    ├── consumer-showcase/             # Layer 3: reference security-remediation app
    ├── samples/                       # hello-world, security-remediation, grafana-rca, …
    ├── docs/                          # architecture, YAML spec, ADRs, security notes
    ├── Makefile                       # make setup | test | demo
    └── dev.sh                         # preferred local driver (manages the venv)
```

Packages are independently installable (`pip install -e`). `conductor-core` has no Snyk/ADO knowledge.

---

## Quick start (no LLM tokens)

Requires **Python 3.11+**. Mock mode needs nothing else.

```bash
git clone https://github.com/sheshi-sheri/AgenticConductor.git
cd AgenticConductor/ai-agents

make setup          # .venv + editable install of all packages
make test           # unit tests, StubLLM, no tokens
make demo-snyk      # one mock scenario: CVE in requests 2.18.0
```

Inspect the run:

```bash
source .venv/bin/activate
conductor runs  --store /tmp/runs.db        # path may differ; see demo output
conductor trace SNYK-001-demo --store /tmp/runs.db --prompts --raw
```

Day-to-day, prefer `./dev.sh` over remembering the venv:

```bash
./dev.sh demo snyk              # mock (default)
./dev.sh sample snyk            # real Copilot LLM, fixture data, fake git URLs
```

Provider modes (`CONDUCTOR_PROVIDER_MODE`):

| Mode | LLM | Scanner data | Git / PRs | Tokens |
|---|---|---|---|---|
| `mock` | StubLLM | fixtures | stubbed | none |
| `sample` | Copilot | fixtures | stubbed | GitHub token for Copilot |
| `integration` | Copilot | fixtures | real test-org PRs | token + `GITHUB_ORG` |
| `live` | Copilot | real APIs | real PRs | token + scanner tokens |

Copy `ai-agents/.env.example` → `ai-agents/.env`. Full variable list: [ai-agents/README.md](ai-agents/README.md).

---

## Minimal consumer (reuse agents)

```python
import asyncio
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.graph import WorkflowGraph
from conductor_core.context import WorkflowContext
from conductor_core.stores.sqlite_store import SQLiteResultStore
from conductor_agents import TriageAgent, PlannerAgent

async def main(llm):
    graph = WorkflowGraph.from_yaml("config/workflow.yaml")
    orch = WorkflowOrchestrator(
        agents={"triage": TriageAgent(llm), "planner": PlannerAgent(llm)},
        graph=graph,
        result_store=SQLiteResultStore("runs.db"),
    )
    ctx = WorkflowContext(run_id="MY-001", payload={"work_item": {"id": "X", "severity": "HIGH"}})
    result = await orch.run(ctx)
    print(result.decisions[-1].recommendation, result.telemetry.total_tokens)

asyncio.run(main(llm))
```

Custom agent: subclass `BaseAgent`, drop Markdown prompts next to the class, register the stage key in YAML **and** in `conductor.json`. Walkthrough: [ai-agents/docs/consumer-guide.md](ai-agents/docs/consumer-guide.md).

---

## Built-in agents (security consumer)

| Agent | Role |
|---|---|
| Triage | Classify, route, skip noise |
| Security analyst / gatekeeper | CVSS, exploitability, adversarial gate |
| Resolver | Map finding → fix strategy |
| Planner | Ordered file-level plan |
| Code | Diff / patch |
| Reviewer | Second-model adversarial review |
| Scribe | PR body / ticket comment |
| Git | Branch, commit, PR (**execute** mode only) |
| Notify / Feedback | Slack/ADO + human feedback |

Prompts are Markdown under each agent’s `prompts/` folder. Editing a prompt does not require a Python change. Specs live in each agent’s `SKILL.md`.

---

## Comparison snapshot (developer view)

Honest, not a bake-off scorecard. Categories differ.

| Capability | Devin | MetaGPT | CrewAI / AutoGen | LangGraph | **Conductor (this PoC)** |
|---|---|---|---|---|---|
| What you buy / clone | SaaS coding agent | Multi-agent “software company” | Role crews / chat | Stateful graph lib | YAML orchestration kernel |
| You own the graph? | No | Partial (roles/SOPs) | Partial | Yes (Python) | **Yes (YAML)** |
| Plan then refuse side effects | Product-defined | Not the model | Not first-class | DIY checkpoints | **`stop_before` / plan mode** |
| Independent parallel review | N/A | Sequential roles | Shared thread by default | DIY | **`asyncio.gather` + merge strategy** |
| Pre-LLM filters | N/A | N/A | Uncommon | DIY | **Declarative, zero tokens** |
| Prompt-level audit store | Vendor UI | Varies | Varies | DIY | **SQLite/Postgres + CLI** |
| Mock-first CI | N/A | Limited | Limited | DIY | **StubLLM + fixtures** |
| Open-ended repo coding | **Strength** | Generates projects from PRD | Possible | Possible | **Only if you build those agents** |
| Certified production | Product | Research / OSS | OSS | OSS | **No — experiment** |

---

## Honesty about maturity

Implemented enough to run demos, unit tests, and a security-remediation showcase:

- YAML graphs, filters, routers, sequential + parallel runners
- `BaseAgent` confidence loop, Copilot provider + StubLLM
- Result store, `conductor` CLI (`runs`, `plan`, `trace`, `check`, …)
- Experimental security: Pydantic `@validated_agent`, log token scrubbing, optional A2A HTTP + mTLS, dependency hashing

**Not done / not claimed:**

- No PyPI release, no versioned support contract
- Token budgets, input size caps, rate limits called out in ADR-013 are **not** fully implemented
- Group-chat “debate” runner is explicitly deferred
- Full ACP editor integration is design-only in places
- YAML typos still fail at **runtime**, not at a schema gate
- Checkpoint markdown in the repo root overstates “production-ready” — treat those as sprint notes, not a launch announcement

---

## Documentation map

| Doc | Audience |
|---|---|
| [docs/LINKEDIN_PRESENTATION.md](docs/LINKEDIN_PRESENTATION.md) | Sharing: story, slides, comparison, ready-to-post copy |
| [ai-agents/README.md](ai-agents/README.md) | Package-level setup, env vars, test ladder, CLI |
| [ai-agents/docs/QUICKSTART.md](ai-agents/docs/QUICKSTART.md) | First 15 minutes |
| [ai-agents/docs/architecture.md](ai-agents/docs/architecture.md) | Runtime pipeline + persistence schema |
| [ai-agents/docs/workflow-yaml.md](ai-agents/docs/workflow-yaml.md) | YAML reference |
| [ai-agents/docs/consumer-guide.md](ai-agents/docs/consumer-guide.md) | Build your own consumer |
| [ai-agents/docs/adr/](ai-agents/docs/adr/) | Why not LangGraph, why not group chat, etc. |
| [ai-agents/docs/THREAT_MODEL.md](ai-agents/docs/THREAT_MODEL.md) | Threats the PoC *tries* to address |

---

## License and affiliation

No `LICENSE` file is published in this clone. Treat the code as **all rights reserved / unpublished experiment** until the owner adds a license. Not affiliated with Cognition (Devin), MetaGPT authors, LangChain, CrewAI, Microsoft, or GitHub.
