# ADR-002: YAML-Driven Workflow Graph

**Status:** Accepted  
**Date:** 2026-05-10  

---

## Context

The original Coding-Agent pipeline (ADR-004 in the root `docs/decisions/`) used a hardcoded Python `match` state machine. Every stage transition was a method call in `pipeline.py`. Adding a new stage, changing a route, or creating a variant (e.g. ADO-only pipeline, adversarial review) required Python changes and a new deployment.

The Conductor rewrite identified this as the primary maintainability problem: **routing logic should be configuration, not code**.

---

## Decision

All pipeline topology is defined in YAML and loaded at runtime via `WorkflowGraph.from_yaml()`. The YAML defines:

- **filters** — pre-LLM rejection rules (zero cost, applied before any agent runs)
- **routes** — which graph handles which source (snyk vs ado vs mock)
- **stages** — ordered stage list with `on_proceed` / `on_block` transitions
- **parallel_groups** — parallel agent bundles triggered at a named stage with a merge strategy
- **mode** — `plan` (halt at `stop_before` stages) or `execute` (run all stages)

```yaml
stages:
  - name: triage
    agent: triage
    on_proceed: security_analysis
    on_block: terminal

parallel_groups:
  - trigger_stage: review_gate
    agents: [security_gatekeeper, reviewer]
    merge_strategy: all_must_pass
    next_stage_on_pass: document
```

Five workflow variants ship in `consumer-showcase/config/` and are selected at runtime via `--workflow`.

---

## Consequences

**Positive:**
- New workflow variant = new YAML file, zero Python changes
- All 5 variants (`default`, `security`, `adversarial`, `ado`, `execute`) differ only in YAML
- `stop_before: true` on the `code` stage is what enforces plan mode — removing it enables full execution without code change
- Routing, filtering, and parallel groups are all visible in one file — no reading Python to understand the pipeline
- Directly implements the intent of the original ADR-004 (transition graph) in a declarative form

**Negative:**
- YAML schema is not yet validated with a JSON Schema — typos in stage names fail at runtime
- Stage names in YAML must match agent registry keys — a mismatch is a runtime error, not a build error
- Complex conditional routing (e.g. "re-plan if confidence < 0.7") is not expressible in pure YAML today

**Future:**
- Add JSON Schema validation at `WorkflowGraph.from_yaml()` load time
- Consider adding `on_low_confidence: re_plan` transition support per stage
