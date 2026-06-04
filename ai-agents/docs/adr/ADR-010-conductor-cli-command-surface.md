# ADR-010: Conductor CLI Command Surface Expansion

**Status:** Pending  
**Date:** 2026-06-03  

---

## Context

The [GitHub Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference) documents a mature CLI with a rich command surface covering session management, environment inspection, parallel execution, diagnostics, code review, sharing/export, model switching, and shell completion.

Conductor CLI currently has 7 commands:

| Command | Purpose |
|---|---|
| `conductor runs` | List pipeline runs from SQLite |
| `conductor plan` | Show stored fix plan for a run |
| `conductor trace` | Show full reasoning trace for a run |
| `conductor all` | Combined trace + plan for recent runs |
| `conductor clean` | Delete runs from the store |
| `conductor logs` | Inspect structured JSON log file |
| `conductor check` | Verify token, Copilot access, packages |
| `conductor version` | Show version |

The Copilot CLI reference reveals several well-designed patterns that map directly onto Conductor's needs. This ADR records which commands are worth adding, what each would do in Conductor's context, and what implementation work is required.

---

## Decision

**Pending** — expand `conductor-cli` with a new set of subcommands inspired by the Copilot CLI command reference. Prioritized into three tiers: **high value** (implement first), **medium value** (implement when manifest ADR-009 lands), and **low value / future** (track but defer).

---

## Borrowed Ideas by Tier

### Tier 1 — High Value (implement independently of ADR-009)

#### `conductor init`
*Inspired by `copilot init`*

Initializes Conductor in an **existing** project (vs. `conductor new` which scaffolds from scratch). Detects existing agent files, YAML configs, and generates a `conductor.json` manifest pre-filled with discovered paths. Writes `.conductor/` directory with default hooks and instructions.

```bash
cd my-existing-project
conductor init
# → Detected 3 agents in agents/
# → Detected workflow.yaml, filters.yaml
# → Generated conductor.json
# → Ready: conductor run
```

---

#### `conductor env`
*Inspired by `/env` slash command — shows loaded environment details*

Prints a summary of everything Conductor has loaded for the current project: manifest path, agents registered, workflow graph stages, integrations enabled, filters active, hooks configured, LLM provider in use.

```bash
conductor env
# ┌─ CONDUCTOR ENVIRONMENT ──────────────────────────┐
# │ Manifest:     conductor.json (strict=true)        │
# │ Agents:       triage, security, planner, coder... │
# │ Disabled:     notify_agent                        │
# │ Workflow:     config/workflow.yaml (9 stages)     │
# │ Integrations: snyk, ado, github                   │
# │ LLM:          github-copilot (gpt-4o)             │
# │ Hooks:        config/hooks.json (3 hooks)         │
# └──────────────────────────────────────────────────┘
```

---

#### `conductor validate`
*Inspired by strict mode in plugin spec + `/diagnose` slash command*

Loads `conductor.json` (or specified path), validates the manifest schema, all referenced YAML files (workflow, filters, routes), and verifies every declared agent class can be imported. Reports errors with file + line number. Exits non-zero on failure for CI use.

```bash
conductor validate
conductor validate --manifest path/to/conductor.json
conductor validate --ci   # machine-readable JSON output
```

---

#### `conductor diagnose <RUN_ID>`
*Inspired by `/diagnose` slash command — analyze session log*

Analyzes a specific run's trace for failure patterns: blocked stages, low-confidence decisions, timeout agents, repeated enrichment rounds. Produces a human-readable diagnosis with suggested fixes.

```bash
conductor diagnose abc-123
# ⚠ Run abc-123 BLOCKED at stage=code_agent
# → CodeAgent confidence 0.31 (threshold 0.60) after 3 enrichment rounds
# → Likely cause: insufficient fix_plan context from PlannerAgent
# → Suggestion: increase planner confidence threshold or add --verbose to planner prompt
```

---

#### `conductor export <RUN_ID>`
*Inspired by `/share [file|html|gist]` slash command*

Exports a run's full report (trace + plan + decisions + telemetry) to a Markdown file, HTML file, or GitHub Gist. Useful for sharing pipeline results with non-technical stakeholders or attaching to work items.

```bash
conductor export abc-123                    # → conductor-run-abc-123.md
conductor export abc-123 --format html      # → conductor-run-abc-123.html
conductor export abc-123 --format gist      # → https://gist.github.com/...
```

---

#### `conductor completion SHELL`
*Directly from `copilot completion SHELL`*

Outputs a shell completion script for `bash`, `zsh`, or `fish`. Enables tab-completion for all subcommands, `--store` paths, `--run` IDs, and `--source` values. Typer supports this natively via `shellingham` + `click`.

```bash
source <(conductor completion zsh)
conductor completion bash | sudo tee /etc/bash_completion.d/conductor
conductor completion fish > ~/.config/fish/completions/conductor.fish
```

---

### Tier 2 — Medium Value (implement after ADR-009 manifest lands)

#### `conductor run`
*Inspired by the overall `copilot` launch command — make Conductor runnable from the CLI*

Currently Conductor has no `conductor run` command — runs are triggered only from Python scripts. This command executes the full pipeline from the CLI using the manifest.

```bash
conductor run                            # uses conductor.json in cwd
conductor run --manifest path/to/conductor.json
conductor run --mode plan                # plan-only, no code changes
conductor run --mode execute             # full execution
conductor run --source snyk              # specific ingest source
conductor run --dry-run                  # validate + show what would run
```

---

#### `conductor model [MODEL]`
*Inspired by `/model` slash command*

Lists available LLM providers/models configured in the manifest or switches the active model for subsequent runs. Useful for cost/quality trade-off testing.

```bash
conductor model                          # list available models
conductor model gpt-4o-mini              # switch to cheaper model
conductor model --show                   # show current model + cost rate
```

---

#### `conductor resume <RUN_ID>`
*Inspired by `/resume [SESSION-ID]` slash command*

Resumes a blocked or human-gated run from its last checkpoint. Blocked runs have a `blocked_reason` in the store; `resume` clears the gate and re-enters the pipeline at the blocked stage.

```bash
conductor resume abc-123
conductor resume abc-123 --override-gate "approved by @lead"
conductor resume                         # picker: list blocked runs
```

---

#### `conductor diff <RUN_ID>`
*Inspired by `/diff` slash command — review proposed changes*

Shows a unified diff of code changes proposed or applied by a run's CodeAgent. Supports switching between "proposed" (plan mode) and "applied" (execute mode) diffs.

```bash
conductor diff abc-123
conductor diff abc-123 --mode proposed
conductor diff abc-123 --mode applied
```

---

#### `conductor fleet [--parallel-groups N]`
*Inspired by `/fleet` command — parallel subagent execution*

Launches multiple pipeline runs in parallel against a batch of work items (e.g., all critical Snyk findings at once). Maps directly onto `ParallelRunner` in `conductor-core`.

```bash
conductor fleet --source snyk --severity critical
conductor fleet --input items.json --parallel 4
```

---

### Tier 3 — Future / Low Priority

| Command | Copilot inspiration | Conductor equivalent |
|---|---|---|
| `conductor update` | `copilot update` | Download + install latest conductor-core/cli from PyPI |
| `conductor changelog [summarize]` | `/changelog [summarize]` | Show CHANGELOG.md with optional LLM summary of recent changes |
| `conductor review <RUN_ID>` | `/review` | Run code review agent on changes proposed in a run |
| `conductor compact <RUN_ID>` | `/compact` | Summarize and compress run history to reduce storage |
| `conductor permissions` | `/permissions [show\|reset]` | Show which integrations/tools are enabled for current project |
| `conductor research TOPIC` | `/research TOPIC` | Deep investigation across codebase + linked issues |

---

## Current vs. Target Command Surface

| Command | Current | Tier 1 | Tier 2 | Tier 3 |
|---|:---:|:---:|:---:|:---:|
| `conductor runs` | ✅ | | | |
| `conductor plan` | ✅ | | | |
| `conductor trace` | ✅ | | | |
| `conductor all` | ✅ | | | |
| `conductor clean` | ✅ | | | |
| `conductor logs` | ✅ | | | |
| `conductor check` | ✅ | | | |
| `conductor version` | ✅ | | | |
| `conductor init` | | ✅ | | |
| `conductor env` | | ✅ | | |
| `conductor validate` | | ✅ | | |
| `conductor diagnose` | | ✅ | | |
| `conductor export` | | ✅ | | |
| `conductor completion` | | ✅ | | |
| `conductor run` | | | ✅ | |
| `conductor model` | | | ✅ | |
| `conductor resume` | | | ✅ | |
| `conductor diff` | | | ✅ | |
| `conductor fleet` | | | ✅ | |
| `conductor update` | | | | ✅ |
| `conductor changelog` | | | | ✅ |
| `conductor review` | | | | ✅ |
| `conductor compact` | | | | ✅ |
| `conductor permissions` | | | | ✅ |
| `conductor research` | | | | ✅ |

---

## Changes Required

### `conductor-cli/conductor_cli/main.py`
- Add `conductor init` — detect agents/yaml, generate manifest
- Add `conductor env` — load manifest + print summary table
- Add `conductor validate` — manifest + YAML schema validation, CI-safe exit codes
- Add `conductor diagnose` — query store, analyze patterns, print structured report
- Add `conductor export` — render run to Markdown/HTML/Gist
- Add `conductor completion` — delegate to Typer's `shellingham` completion support
- Add `conductor run` (Tier 2) — load manifest, build orchestrator, execute pipeline
- Add `conductor model` (Tier 2) — read/write active model in manifest or env
- Add `conductor resume` (Tier 2) — query blocked runs, clear gate, re-enter pipeline
- Add `conductor diff` (Tier 2) — query run store for proposed file changes, render diff

### `conductor-cli/conductor_cli/formatters/` (new)
- `markdown.py` — run → Markdown report renderer
- `html.py` — run → standalone HTML report renderer
- `gist.py` — upload report to GitHub Gist via API

### `conductor-cli/conductor_cli/init_wizard.py` (new)
- Agent directory scanner
- YAML config detector
- Manifest generator with discovered values pre-filled

### `conductor-core/conductor_core/`
- `validators.py` (new, also required by ADR-009) — YAML + manifest schema validation
- `stores/sqlite_store.py` — add `get_blocked_runs()` and `checkpoint_run()` for `resume` support

### Dependencies to add (`pyproject.toml`)
- `shellingham` — for `conductor completion` (Typer shell detection)
- `jinja2` — for HTML export template rendering
- `httpx` — already present; used for Gist API upload

---

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Keep CLI minimal, use Python API | Ops/SRE teams cannot use Python scripts in CI pipelines easily; CLI is the correct interface for automation |
| Use Click instead of Typer | Typer is already in use; switching adds churn with no benefit |
| One mega-command with sub-options | Violates Unix principle of small focused commands; harder to tab-complete and document |
| Build a TUI (like Copilot's interactive mode) | Significant complexity; terminal rendering is out of scope for v1; `conductor run` headless mode covers the core use case |

---

## Consequences

**Positive:**
- Conductor becomes operable from shell/CI with no Python scripting
- `conductor validate` catches misconfig in CI before a run is ever attempted
- `conductor diagnose` reduces time-to-debug from hours to seconds
- `conductor export` makes pipeline results shareable without DB access
- `conductor env` eliminates "why isn't my agent loading?" questions
- Shell completion dramatically improves developer ergonomics

**Negative / Trade-offs:**
- Each new command adds surface area to maintain and document
- `conductor export --format gist` requires a GitHub token with gist scope
- `conductor run` (Tier 2) requires ADR-009 manifest to be implemented first
- `conductor fleet` requires ParallelRunner to be stable in conductor-core

---

## References

- [GitHub Copilot CLI Command Reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
- [ADR-009: conductor.json Project Manifest](ADR-009-conductor-json-manifest.md)
- [ADR-001: Monorepo Multi-Package Structure](ADR-001-monorepo-package-structure.md)
- [ADR-005: Parallel Runners](ADR-005-parallel-runners-not-group-chat.md)
- [PLAN.md — conductor-cli section](../../PLAN.md)
