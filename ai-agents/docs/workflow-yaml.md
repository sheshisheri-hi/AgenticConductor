# Workflow YAML Reference

Every pipeline is defined entirely in YAML. No Python changes needed to add stages, change routing, apply filters, or switch models.

---

## File Location

```
consumer-showcase/config/
├── workflow.yaml              # default (security: snyk/sonar/blackduck)
├── workflow_security.yaml     # plan-only: halts before code execution
├── workflow_ado.yaml          # ADO defect/story: skips CVE analysis
├── workflow_execute.yaml      # full 11-stage pipeline: code + git + notify
└── workflow_adversarial.yaml  # adversarial gate: uses different LLM model
```

Pass via CLI:
```bash
python main.py --scenario snyk --workflow config/workflow_adversarial.yaml
```

Or hard-wire in orchestrator:
```python
graph = WorkflowGraph.from_yaml("config/workflow_adversarial.yaml")
```

---

## Full Schema

```yaml
workflow:
  name: my_pipeline          # string — stored in runs.workflow column
  mode: plan                 # plan | execute

filters:                     # applied BEFORE any LLM call (zero cost)
  - field: work_item.severity
    reject_if_in: [info, low]            # drop if field value matches list
  - field: work_item.repo_name
    reject_if_null: true                 # drop if field is null/missing
  - field: work_item.id
    dedup: true                          # drop if run_id already in store

routes:                      # tag the context with a route for reporting
  - match_field: work_item.source
    match_values: [snyk, sonar, blackduck]
    route: security_remediation
  - match_field: work_item.source
    match_values: [ado]
    route: ado_remediation
  - match_field: "*"          # catch-all
    route: escalate_human

stages:
  - name: triage              # unique stage name (used in transitions)
    agent: triage             # key in the agents dict passed to orchestrator
    model: gpt-4o             # (optional) overrides CONDUCTOR_LLM_MODEL for this stage
    on_proceed: security_analysis    # next stage when recommendation=proceed
    on_block: terminal               # next stage when recommendation=block
    on_escalate: terminal            # next stage when recommendation=escalate

  - name: security_analysis
    agent: security_analyst
    on_proceed: resolve
    on_block: terminal
    filter:                   # (optional) only run this stage if route matches
      route: security_remediation

  - name: resolve
    agent: resolver
    on_proceed: plan
    on_block: terminal

  - name: plan
    agent: planner
    on_proceed: review
    on_block: terminal
    stop_before: true         # plan mode: pipeline halts before this stage
                              # execute mode: stage runs normally

  - name: review
    agent: reviewer
    model: gpt-4-turbo        # use a different model for adversarial review
    on_proceed: scribe
    on_block: terminal

  - name: scribe
    agent: scribe
    on_proceed: git
    on_block: terminal

  - name: git
    agent: git
    on_proceed: notify
    on_block: terminal

  - name: notify
    agent: notify
    on_proceed: terminal
    on_block: terminal

  - name: terminal            # required: the final stage name
```

---

## Filters

Filters run **before any LLM call**. If a filter rejects, the run is marked blocked with a reason and saved — no tokens consumed.

| Directive | Description | Example |
|---|---|---|
| `reject_if_in` | Drop if field value is in the list | Reject `severity: info` |
| `reject_if_null` | Drop if field is missing/null | Reject items with no `repo_name` |
| `dedup` | Drop if run with same ID already exists in the result store | Prevent duplicate campaigns |

```yaml
filters:
  - field: work_item.severity
    reject_if_in: [info, low]
  - field: work_item.repo_name
    reject_if_null: true
```

---

## Routes

Routes tag the context with a string used for reporting and (optionally) stage filtering. The first matching rule wins.

```yaml
routes:
  - match_field: work_item.source
    match_values: [snyk, sonar, blackduck]
    route: security_remediation
  - match_field: "*"          # wildcard — always matches
    route: escalate_human
```

---

## Stages

### Transitions

```yaml
stages:
  - name: triage
    agent: triage
    on_proceed:  security_analysis    # AgentDecision.recommendation == "proceed"
    on_block:    terminal             # AgentDecision.recommendation == "block"
    on_escalate: terminal             # AgentDecision.recommendation == "escalate"
                                      # (if omitted, falls back to on_block)
```

### Route Filter (per-stage)

Only run this stage if the context has a specific route:

```yaml
  - name: security_analysis
    agent: security_analyst
    filter:
      route: security_remediation     # skipped entirely for ado_remediation runs
    on_proceed: resolve
    on_block: terminal
```

### stop_before

Halts the pipeline **before** entering this stage when `mode=plan`:

```yaml
  - name: code
    agent: code_writer
    stop_before: true    # in plan mode: pipeline stops here, code is never written
                         # in execute mode: runs normally
```

Useful for showing the plan without applying any code changes.

### model (per-stage override)

```yaml
  - name: adversarial_gate
    agent: reviewer
    model: o1-preview    # only this stage uses o1-preview
    on_proceed: scribe
    on_block: terminal
```

---

## Plan Mode vs Execute Mode

| Aspect | `mode: plan` | `mode: execute` |
|---|---|---|
| What runs | Triage → Analysis → Plan | Full 11 stages including code, git, notify |
| `stop_before: true` stages | Pipeline halts before that stage | Stage runs normally |
| Real side effects | None | Git branch/commit/PR, Slack post |
| Typical use | PR review, cost estimate, human approval | Fully automated remediation |

Switch globally:
```yaml
workflow:
  mode: execute
```

Or override at runtime (CLI not yet exposed — pass `mode` arg to `orch.run(ctx, mode="execute")`).

---

## The 4 Showcase Configurations

### `workflow_security.yaml` — Plan-only for Snyk/Sonar/BlackDuck

```
triage → security_analysis → resolve → plan → [HALT]
```
- Filters: reject info/low + null repos
- Routes: security findings → `security_remediation`
- Halts before `code` stage
- Use for: reviewing what the fix would be without applying it

### `workflow_ado.yaml` — ADO defects and stories

```
triage → resolve → plan → [HALT]
```
- Skips `security_analysis` (no CVE scoring for ADO items)
- Routes: ADO → `ado_remediation`
- Use for: feature work and defect triaging

### `workflow_execute.yaml` — Full automated pipeline

```
triage → security_analysis → resolve → plan → code → review → scribe → git → notify → feedback → [terminal]
```
- No `stop_before` — all stages run
- Use for: fully automated remediation with real git operations

### `workflow_adversarial.yaml` — Adversarial review showcase

```
triage → security_analysis → resolve → plan → adversarial_gate (reviewer, model=gpt-4-turbo) → scribe → [HALT]
```
- Per-stage model override on `adversarial_gate`
- Use for: demonstrating multi-model reasoning

---

## Adding a New Workflow Configuration

1. Copy an existing YAML: `cp config/workflow_security.yaml config/workflow_custom.yaml`
2. Edit stages, filters, routes as needed
3. Run with: `python main.py --scenario snyk --workflow config/workflow_custom.yaml`

No Python changes needed.
