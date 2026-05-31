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
| What runs | Triage → Analysis → Plan, then halt | All stages including code, review, scribe, git, notify |
| `stop_before: true` stages | Pipeline halts before that stage | Stage runs normally |
| Side effects (showcase) | None | LLM generates code changes + commit messages in-memory (see note) |
| Typical use | Cost estimate, human approval before commit | Full end-to-end pipeline demo |

> **Important — showcase vs production:** In the consumer-showcase, `execute` mode is a
> **simulation**. The agents run real LLM calls and produce real reasoning, but:
> - **CodeAgent** generates `code_changes` JSON in the context payload — it does **not** write files to disk
> - **ScribeAgent** generates commit messages and PR descriptions — it does **not** create git commits
> - **GitAgent** is a functional stub — it sets a `branch_name` and `pr_url` in the context but makes **no real GitHub API calls**
> - **NotifyAgent** logs a notification decision — no Slack/email sent
>
> In a production integration you would swap these stubs with real implementations
> (e.g. a `GitAgent` that calls `gh pr create`, a `NotifyAgent` that posts to Slack).

Switch globally:
```yaml
workflow:
  mode: execute
```

Or override at runtime (pass `mode` arg to `orch.run(ctx, mode="execute")`).

---

## The 5 Showcase Configurations

### `workflow.yaml` — Default full pipeline

```
triage → security_analysis → resolve → plan → [HALT]
         ↳ parallel review_gate: security_gatekeeper + reviewer (all_must_pass)
         ↳ parallel notify_feedback: notify + feedback (first_pass)
```
- Sources: snyk, sonar, blackduck, ado, mock — widest coverage
- Halts before `code` in plan mode
- `dev.sh` shortname: `default`

### `workflow_security.yaml` — Security sources only

```
triage → security_analysis → resolve → plan → [HALT]
```
- Same pipeline as default but **routes only** snyk/sonar/blackduck (no ado/mock)
- Use for: enforcing security-source-only routing in shared environments
- `dev.sh` shortname: `security`

### `workflow_adversarial.yaml` — Adversarial review gate

```
triage → security_analysis → resolve → plan → [HALT]
         ↳ parallel adversarial_gate: security_gatekeeper + reviewer (all_must_pass, uses CONDUCTOR_REVIEWER_MODEL)
```
- **Stricter filter**: rejects `info` AND `low` severity (adversarial review is expensive)
- The reviewer agent uses `CONDUCTOR_REVIEWER_MODEL` — a **different model** from the planner — to independently critique the fix plan
- No `notify_feedback` stage — focused on adversarial critique only
- Use for: demonstrating multi-model independent review
- `dev.sh` shortname: `adversarial`

### `workflow_ado.yaml` — ADO defects and stories

```
triage → plan → [HALT]
         ↳ parallel review_gate: security_gatekeeper + reviewer (all_must_pass)
         ↳ parallel notify_feedback: notify + feedback (first_pass)
```
- **Skips `security_analysis` and `resolve`** — no CVE scoring for ADO items
- Routes: ado/mock sources only
- **2 decisions** vs 4 for security workflows — ~50% faster and cheaper
- `dev.sh` shortname: `ado`

### `workflow_execute.yaml` — Full execution (all 11 stages)

```
triage → security_analysis → resolve → plan → code → [parallel review_gate] → document → deliver → [parallel notify_feedback] → terminal
```
- **Only YAML with `mode: execute`** — no `stop_before`, all stages run
- Runs `code` (LLM generates code changes), `scribe` (LLM writes commit messages/PR descriptions), `git` (creates branch + PR stub), `notify`+`feedback` in parallel
- **13 decisions**, ~7000+ tokens — the highest-cost workflow
- See note above: code/git/notify are showcase stubs in this repo
- `dev.sh` shortname: `execute`

---

## Running Each Workflow

```bash
# Mock (no token needed) — instant, zero cost
./dev.sh demo snyk default       # default pipeline
./dev.sh demo snyk security      # security-only routing
./dev.sh demo snyk adversarial   # adversarial review gate
./dev.sh demo ado-defect ado     # ADO 2-stage pipeline
./dev.sh demo snyk execute       # full 11-stage execution

# Real LLM (needs CONDUCTOR_GITHUB_TOKEN / GITHUB_COPILOT_TOKEN)
./dev.sh sample snyk default
./dev.sh sample snyk adversarial
./dev.sh sample snyk execute     # ~13 LLM calls, ~22 seconds
```

Or via Makefile:
```bash
make demo-adversarial      # snyk + adversarial workflow (mock)
make demo-security         # snyk + security workflow (mock)
make demo-ado-workflow     # ado-defect + ado workflow (mock)
make demo-sample-adversarial   # real LLM
```

---

## Adding a New Workflow Configuration

1. Copy an existing YAML: `cp config/workflow_security.yaml config/workflow_custom.yaml`
2. Edit stages, filters, routes as needed
3. Run with: `python main.py --scenario snyk --workflow config/workflow_custom.yaml`

No Python changes needed.
