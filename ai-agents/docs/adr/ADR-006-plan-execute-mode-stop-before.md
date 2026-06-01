# ADR-006: Plan vs Execute Mode via stop_before Flag

**Status:** Accepted  
**Date:** 2026-05-05  
**Evolves:** Original Coding-Agent `docs/decisions/ADR-002-plan-first-execution-flag.md`

---

## Context

The original Coding-Agent enforced plan-first behavior via a Python env flag `ASPEN_CODE_EXECUTION_ENABLED`. Setting it to `false` halted the pipeline before any code-modifying stage. This was a binary global flag — no way to stop at a different stage or have multiple execution profiles.

The Conductor rewrite needed a more expressive mechanism:
- **Plan mode**: run analysis, security review, planning — stop before code changes
- **Execute mode**: run full pipeline including code generation, git operations, PR creation
- Future: **Dry-run** mode, **partial execute** (run through code but not git), etc.

---

## Decision

`stop_before: true` is a per-stage YAML flag. When the orchestrator reaches a stage with `stop_before: true` and mode is `plan`, it emits a `plan_mode_halt` event and exits cleanly with the decisions made so far.

```yaml
# workflow.yaml — default (plan mode)
stages:
  - name: plan
    agent: planner
    on_proceed: code
  - name: code
    agent: code_agent
    stop_before: true          # halt here in plan mode
    on_proceed: review_gate
```

```yaml
# workflow_execute.yaml — full pipeline (no stop_before)
stages:
  - name: code
    agent: code_agent
    on_proceed: review_gate    # no stop_before — runs through
```

Mode is passed at runtime via `--mode plan` or `--mode execute` (or `CONDUCTOR_MODE` env var).

---

## Consequences

**Positive:**
- Plan mode is the default — no accidental side effects on first run
- `stop_before: true` is visible in the YAML — any reader can see exactly where the pipeline pauses
- Multiple execution profiles are just different YAML files (or stage flags) — no new Python code needed
- The `plan_mode_halt` structured log event provides an auditable boundary between analysis and action

**Negative:**
- `stop_before: true` only halts in `plan` mode — there is no equivalent `skip_in_execute` flag yet
- No per-agent dry-run: if a stage has side effects (git push), there is no intermediate "simulate effects" option in the framework today

**Current execute mode disclaimer:**
The `consumer-showcase` execute workflow agents (`CodeAgent`, `ScribeAgent`, `GitAgent`, `NotifyAgent`) are **showcase simulations** — they generate their outputs in memory only, no real git operations or GitHub API calls. Production deployments must implement real side effects behind the `FunctionalAgent` interface.

See `docs/workflow-yaml.md` → "Plan Mode vs Execute Mode" for the full list of what each agent does and does not do in the showcase.

---

## References

- `consumer-showcase/config/workflow.yaml` — `stop_before: true` at `code` stage
- `consumer-showcase/config/workflow_execute.yaml` — no `stop_before`
- `conductor-core/conductor_core/orchestrator.py` — `plan_mode_halt` event
- `docs/workflow-yaml.md` — running guide with showcase disclaimer
