# Scripts Reference

All operational scripts are in `consumer-showcase/scripts/`. They work with any SQLite result store database.

---

## Quick Reference

```bash
# From ai-agents/ with .venv active
cd NewFramework/ai-agents && source .venv/bin/activate

# Run all 5 demo scenarios
python consumer-showcase/main.py --all --store /tmp/runs.db

# List all runs
python consumer-showcase/scripts/show_runs.py --store /tmp/runs.db

# Show fix plan
python consumer-showcase/scripts/show_plan.py --store /tmp/runs.db --run SNYK-001-demo

# Full trace (reasoning + prompts + model)
python consumer-showcase/scripts/show_trace.py --store /tmp/runs.db --run SNYK-001-demo

# Everything (all runs + traces + plans)
python consumer-showcase/scripts/show_all.py --store /tmp/runs.db

# View structured logs
python consumer-showcase/scripts/show_logs.py --log /tmp/conductor.log --events

# Clean / delete a run
python consumer-showcase/scripts/clean_run.py --store /tmp/runs.db --run SNYK-001-demo
```

---

## main.py — Run Scenarios

```
python consumer-showcase/main.py [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--scenario` | One scenario: `snyk`, `sonar`, `blackduck`, `ado-defect`, `ado-story` | — |
| `--all` | Run all 5 scenarios | — |
| `--store PATH` | SQLite database path | `conductor_runs.db` |
| `--workflow PATH` | Override workflow YAML | scenario-default |
| `--log-file PATH` | Write structured JSON logs to file | none |

**Examples:**
```bash
# Single scenario
python consumer-showcase/main.py --scenario snyk --store /tmp/runs.db

# All scenarios with logs
python consumer-showcase/main.py --all --store /tmp/runs.db --log-file /tmp/conductor.log

# Custom workflow YAML
python consumer-showcase/main.py --scenario snyk --workflow config/workflow_adversarial.yaml --store /tmp/runs.db

# Via environment variable
DEMO_SCENARIO=sonar python consumer-showcase/main.py --store /tmp/runs.db
```

---

## show_runs.py — List All Runs

```
python consumer-showcase/scripts/show_runs.py [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |
| `--source` | Filter by source (snyk, sonar, ado, blackduck) | all |
| `--last N` | Show last N runs | 20 |

**Output columns:** RUN ID, SOURCE, WORKFLOW, MODE, BLK (blocked), DEC (decisions), TOKENS, COST $, UPDATED

**Example:**
```bash
python consumer-showcase/scripts/show_runs.py --store /tmp/runs.db --source snyk --last 5
```

---

## show_plan.py — Show Fix Plan

```
python consumer-showcase/scripts/show_plan.py [run_id | --run RUN_ID] [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `run_id` | Positional run ID | — |
| `--run RUN_ID` | Named alias for run_id | — |
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |

**Output:** Rendered Markdown fix plan (steps, files, PR description, effort estimate)

**Example:**
```bash
python consumer-showcase/scripts/show_plan.py --store /tmp/runs.db --run SNYK-001-demo
# or positional:
python consumer-showcase/scripts/show_plan.py SNYK-001-demo --store /tmp/runs.db
```

---

## show_trace.py — Full Reasoning Trace

```
python consumer-showcase/scripts/show_trace.py [run_id | --run RUN_ID] [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `run_id` | Positional run ID | — |
| `--run RUN_ID` | Named alias for run_id | — |
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |
| `--prompts` | Also show system + user prompt for each decision | off |
| `--raw` | Also show raw LLM response for each decision | off |

**Output per decision:** agent, stage, round, confidence, recommendation, model_used, tokens, cost, latency, reasoning bullets, evidence list, (optionally: prompts, raw response)

**Example:**
```bash
# Basic trace
python consumer-showcase/scripts/show_trace.py --store /tmp/runs.db --run SONAR-001-demo

# With prompts and raw responses (full LLM audit)
python consumer-showcase/scripts/show_trace.py --store /tmp/runs.db --run SONAR-001-demo --prompts --raw
```

---

## show_all.py — Everything

```
python consumer-showcase/scripts/show_all.py [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |
| `--source` | Filter by source | all |
| `--last N` | Show last N runs | 10 |
| `--no-plans` | Skip fix plan section | off |
| `--no-trace` | Skip reasoning trace section | off |

**Output:** For each run: header summary + reasoning trace + fix plan

**Example:**
```bash
python consumer-showcase/scripts/show_all.py --store /tmp/runs.db --last 5
python consumer-showcase/scripts/show_all.py --store /tmp/runs.db --no-trace  # plans only
```

---

## show_logs.py — Structured Log Viewer

```
python consumer-showcase/scripts/show_logs.py [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--log PATH` | JSON log file (from `--log-file`) | required |
| `--run RUN_ID` | Filter to specific run | all |
| `--event NAME` | Filter by event name (exact match) | all |
| `--level` | Filter by level: `debug`, `info`, `warning`, `error` | all |
| `--last N` | Show last N entries | all |
| `--events` | List all unique event types in the file | — |
| `--verbose` | Show full JSON per entry | off |
| `--json` | Output as JSON array | off |

**Examples:**
```bash
# First run with logging:
python consumer-showcase/main.py --scenario snyk --store /tmp/runs.db --log-file /tmp/conductor.log

# See what events are in the log
python consumer-showcase/scripts/show_logs.py --log /tmp/conductor.log --events

# Filter to one run
python consumer-showcase/scripts/show_logs.py --log /tmp/conductor.log --run SNYK-001-demo

# Only LLM call events
python consumer-showcase/scripts/show_logs.py --log /tmp/conductor.log --event llm_call_complete

# Only errors
python consumer-showcase/scripts/show_logs.py --log /tmp/conductor.log --level error

# Last 20 entries
python consumer-showcase/scripts/show_logs.py --log /tmp/conductor.log --last 20
```

---

## clean_run.py — Delete a Run

```
python consumer-showcase/scripts/clean_run.py [run_id | --run RUN_ID] [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `run_id` | Positional run ID | — |
| `--run RUN_ID` | Named alias | — |
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |
| `--yes` | Skip confirmation prompt | off |
| `--list` | List all runs in DB (don't delete) | — |
| `--all` | Delete all runs (requires `--yes`) | — |

**Examples:**
```bash
# List what's in the DB
python consumer-showcase/scripts/clean_run.py --list --store /tmp/runs.db

# Delete one run (with confirmation)
python consumer-showcase/scripts/clean_run.py --store /tmp/runs.db --run SNYK-001-demo

# Delete without confirmation
python consumer-showcase/scripts/clean_run.py --store /tmp/runs.db --run SNYK-001-demo --yes

# Wipe entire DB
python consumer-showcase/scripts/clean_run.py --all --yes --store /tmp/runs.db
```

---

## Makefile Targets

From `ai-agents/` root:

```bash
make setup              # create .venv, install all packages (run once)
make test               # run all 116 tests
make test-unit          # unit tests only
make test-integration   # integration tests only
make demo               # run all 5 demo scenarios
make demo-snyk          # run Snyk CVE scenario only
make demo-sonar         # run SonarQube scenario only
make demo-blackduck     # run BlackDuck scenario only
make demo-ado-defect    # run ADO defect scenario only
make demo-ado-story     # run ADO story scenario only
make lint               # run ruff linter
make clean              # remove .venv, __pycache__, *.egg-info, dist/
```

---

## What are *.egg-info directories?

`*.egg-info` folders (e.g. `conductor_core.egg-info/`) are **build artifacts** created automatically by `pip install -e .` (editable installs). They:

- Are created by pip to register the package in your venv
- Are NOT source code — they are generated
- Should be in `.gitignore` and committed with your source
- Are safe to delete (`make clean` removes them; `make setup` recreates them)
- Contain: package name, version, dependencies list, file index

```bash
# Clean all build artifacts (egg-info, __pycache__, .pytest_cache, dist)
make clean

# Recreate them
make setup
```
