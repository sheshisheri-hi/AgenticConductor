# Conductor — Architecture

## Overview

Conductor is a **three-layer** multi-agent workflow framework. Layers are independently versioned Python packages — consumers pick and choose what they need.

```
┌───────────────────────────────────────────────────────────────┐
│  Layer 3: Consumer (your app)                                 │
│  consumer-showcase / my-consumer                              │
│  • workflow YAML   • StubLLM / real LLM   • main.py          │
│  • thin wiring — just imports agents + passes to orchestrator │
├───────────────────────────────────────────────────────────────┤
│  Layer 2: conductor-agents                                    │
│  10 domain agents with prompts + SKILL.md                    │
│  TriageAgent, PlannerAgent, ReviewerAgent, CodeAgent, ...    │
├───────────────────────────────────────────────────────────────┤
│  Layer 1: conductor-core                                      │
│  Pure framework — zero domain knowledge                       │
│  BaseAgent, WorkflowOrchestrator, WorkflowGraph, Filters,    │
│  Router, SQLiteResultStore, OTEL tracing                      │
└───────────────────────────────────────────────────────────────┘
```

---

## Runtime Pipeline

```
  Input (work_item payload)
        │
        ▼
  FilterEngine          ← declarative YAML rules, zero LLM cost
  (reject_if_in,           reject info/low severity, null repos
   reject_if_null,         deduplication patterns
   dedup)
        │
        ▼
  RouterEngine          ← match payload fields → route tag
  (match_field/             snyk/sonar/blackduck → security_remediation
   match_values)            ado              → ado_remediation
        │
        ▼
  WorkflowOrchestrator  ← reads WorkflowGraph (loaded from YAML)
  ┌─────────────────────────────────────────────────────────────┐
  │  for each stage in graph:                                   │
  │    set agent._runtime_model = stage.model  (if set)        │
  │    decision = await runner.run(agent, context)              │
  │    append decision to context.decisions                     │
  │    if decision.blocked → halt (blocked_reason set)          │
  │    if stop_before AND mode==plan → halt here               │
  │    transition to next stage via on_proceed/on_block         │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  SQLiteResultStore.save_run(context)
  → runs table:     run_id, workflow, source, mode, blocked, tokens, cost
  → decisions table: agent, stage, round, confidence, model_used,
                     prompt_system, prompt_user, raw_llm_response,
                     reasoning, evidence, tokens, latency, cost
```

---

## BaseAgent Reasoning Loop

Each LLM agent runs a **multi-round confidence loop**:

```
  round 1:
    system_prompt = load("agent_system.md", **variables)
    user_prompt   = load("agent_user.md",   **variables)
    (response, model) = _call_llm(system_prompt, user_prompt)
    decision = _parse_decision(response)        ← JSON parse
    decision.model_used = model
    decision.prompt_system = system_prompt      ← saved verbatim
    decision.prompt_user   = user_prompt        ← saved verbatim
    decision.raw_llm_response = response        ← saved verbatim

    if confidence >= CONFIDENCE_THRESHOLD:
        return decision  ✓

    if decision.wants_more_rounds():
        enrichment = await _enrich(ctx, decision.concerns)
        merge enrichment into context
        continue to round 2

  round MAX_ROUNDS:
    if still not confident:
        decision.requires_human = True
        return decision  (escalate)
```

---

## Model Resolution

Each agent resolves its LLM model at call time with this priority:

```
1. YAML stage model:  field          (set per-stage in workflow.yaml)
   ↓ if not set
2. Agent.MODEL_OVERRIDE               (class-level, e.g. ReviewerAgent)
   ↓ if not set
3. settings.llm_model                 (CONDUCTOR_LLM_MODEL env var)
```

This means the Reviewer can use `gpt-4-turbo` while the Planner uses `gpt-4o`, and a specific adversarial stage can override both with `o1-preview` — all via config.

---

## Persistence Schema

### `runs` table

| Column | Type | Description |
|---|---|---|
| `run_id` | TEXT PK | e.g. `SNYK-001-demo` |
| `source` | TEXT | `snyk` / `sonar` / `ado` / `blackduck` |
| `workflow` | TEXT | Workflow YAML name |
| `mode` | TEXT | `plan` or `execute` |
| `blocked` | INTEGER | 1 if pipeline was halted |
| `blocked_reason` | TEXT | Why it halted |
| `decision_count` | INTEGER | Total agent decisions |
| `total_tokens` | INTEGER | Sum across all decisions |
| `total_latency_ms` | REAL | Sum across all decisions |
| `estimated_cost_usd` | REAL | Computed from token counts |
| `plan_markdown` | TEXT | Rendered fix plan (planner output) |
| `scribe_output_json` | TEXT | PR body / ticket comment |
| `payload_json` | TEXT | Full serialized WorkflowContext |
| `created_at` | TEXT | ISO-8601 timestamp |

### `agent_decisions` table

| Column | Type | Description |
|---|---|---|
| `run_id` | TEXT | FK to runs |
| `agent_name` | TEXT | e.g. `triage`, `planner` |
| `stage_name` | TEXT | Stage key from YAML |
| `round_number` | INTEGER | Which reasoning round |
| `recommendation` | TEXT | `proceed` / `block` / `escalate` |
| `confidence` | REAL | 0.0–1.0 |
| `model_used` | TEXT | Actual model called |
| `prompt_system` | TEXT | System prompt verbatim |
| `prompt_user` | TEXT | User prompt verbatim |
| `raw_llm_response` | TEXT | Raw LLM response verbatim |
| `reasoning_json` | TEXT | Parsed reasoning bullets |
| `evidence_json` | TEXT | Parsed evidence list |
| `tokens_used` | INTEGER | Tokens for this call |
| `latency_ms` | REAL | Latency for this call |
| `estimated_cost_usd` | REAL | Cost for this call |

---

## OTEL Tracing

```
workflow:security_remediation                 ← root span
  ├── stage:triage                            ← per-stage span
  │     agent=triage, tokens=577, conf=0.92
  ├── stage:security_analysis
  │     agent=security_analyst, tokens=874
  ├── stage:resolve
  │     agent=resolver, tokens=350
  └── stage:plan
        agent=planner, tokens=441
```

Span attributes: `run_id`, `workflow`, `mode`, `route`, `agent`, `recommendation`, `confidence`, `blocked`, `decision_count`, `total_tokens`.

Enable with:
```bash
CONDUCTOR_OTEL_ENDPOINT=http://localhost:4317   # Jaeger / Honeycomb / Datadog
CONDUCTOR_OTEL_SERVICE_NAME=conductor
```

---

## Package Dependency Graph

```
consumer-showcase
    └── conductor-agents
            └── conductor-core

conductor-integrations
    └── conductor-core
```

`conductor-agents` and `conductor-integrations` are independent at Layer 2 — a consumer can use both, one, or neither.

---

## Directory Map

```
ai-agents/
├── conductor-core/              # Layer 1: pure framework
│   └── conductor_core/
│       ├── base_agent.py        # LLM loop, prompt loading, telemetry
│       ├── orchestrator.py      # pipeline driver
│       ├── graph.py             # YAML → WorkflowGraph
│       ├── context.py           # WorkflowContext, TelemetryData
│       ├── decisions.py         # AgentDecision schema
│       ├── filter_engine.py     # declarative pre-filter
│       ├── router_engine.py     # payload-field routing
│       ├── config/settings.py   # env-driven config
│       ├── runners/             # SequentialRunner, (future: ParallelRunner)
│       └── stores/              # SQLiteResultStore
│
├── conductor-agents/            # Layer 2: domain agents
│   └── conductor_agents/agents/
│       ├── triage/   security/  resolver/  planner/
│       ├── code/     reviewer/  scribe/    git/
│       └── notify/   feedback/
│       (each: agent.py + SKILL.md + prompts/)
│
├── conductor-integrations/      # Layer 2b: source/git/notify clients
│   └── conductor_integrations/
│       ├── sources/  (snyk, sonar, blackduck, ado)
│       ├── git/      (mock + github)
│       └── notify/   (mock)
│
├── conductor-cli/               # Layer 3: planned CLI (not yet implemented)
│
├── consumer-showcase/           # Layer 3: reference consumer
│   ├── main.py                  # CLI entry point, StubLLM, scenario wiring
│   ├── config/                  # workflow YAMLs (4 configurations)
│   ├── scripts/                 # 7 operational scripts
│   └── tests/                   # 116 tests
│
├── docs/                        # Documentation
├── samples/                     # Real code files with baked-in issues
├── mocks/                       # Pre-baked JSON fixtures
├── Makefile                     # make setup | test | demo
└── scripts/                     # CI/CD shell scripts
```
