# Scripts Reference

Operational commands are provided by the **`conductor` CLI** (`conductor-cli` package).

Install it once with `make setup` or `pip install -e "conductor-cli"`, then use:

---

## Quick Reference

```bash
# From ai-agents/ with .venv active
cd NewFramework/ai-agents && source .venv/bin/activate

# Run all 5 demo scenarios
python consumer-showcase/main.py --all --store /tmp/runs.db

# List all runs
conductor runs --store /tmp/runs.db

# Show fix plan
conductor plan SNYK-001-demo --store /tmp/runs.db

# Full trace (reasoning + prompts + model)
conductor trace SNYK-001-demo --store /tmp/runs.db

# Everything (all runs + traces + plans)
conductor all --store /tmp/runs.db

# View structured logs
conductor logs --events
conductor logs --run SNYK-001-demo

# Clean / delete a run
conductor clean SNYK-001-demo --store /tmp/runs.db
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

## conductor runs — List All Runs

```
conductor runs [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |
| `--source` | Filter by source (snyk, sonar, ado, blackduck) | all |
| `--last N` | Show last N runs | 20 |

**Output columns:** RUN ID, SOURCE, WORKFLOW, MODE, BLK (blocked), DEC (decisions), TOKENS, COST $, UPDATED

```bash
conductor runs --store /tmp/runs.db --source snyk --last 5
```

---

## conductor plan — Show Fix Plan

```
conductor plan [RUN_ID | --run RUN_ID] [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `RUN_ID` | Positional run ID | — |
| `--run RUN_ID` | Named alias | — |
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |

**Output:** Rendered Markdown fix plan (steps, files, PR description, effort estimate)

```bash
conductor plan SNYK-001-demo --store /tmp/runs.db
```

---

## conductor trace — Full Reasoning Trace

```
conductor trace [RUN_ID | --run RUN_ID] [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `RUN_ID` | Positional run ID | — |
| `--run RUN_ID` | Named alias | — |
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |
| `--prompts` | Show system + user prompt for each decision | off |
| `--raw` | Show raw LLM response for each decision | off |

**Output per decision:** agent, stage, round, confidence, recommendation, model_used, tokens, cost, latency, reasoning bullets, evidence, (optionally: prompts, raw response)

```bash
# Basic trace
conductor trace SONAR-001-demo --store /tmp/runs.db

# Full LLM audit (with prompts + raw responses)
conductor trace SONAR-001-demo --store /tmp/runs.db --prompts --raw
```

---

## conductor all — Everything

```
conductor all [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |
| `--source` | Filter by source | all |
| `--last N` | Show last N runs | 10 |
| `--no-plans` | Skip fix plan section | off |
| `--no-trace` | Skip reasoning trace section | off |

```bash
conductor all --store /tmp/runs.db --last 5
conductor all --store /tmp/runs.db --no-trace   # plans only
```

---

## conductor logs — Structured Log Viewer

```
conductor logs [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `--log PATH` | JSON log file | `conductor.log` |
| `--run RUN_ID` | Filter to specific run | all |
| `--event NAME` | Filter by event name (exact match) | all |
| `--last N` | Show last N entries | all |
| `--events` | List all unique event types in the file | — |
| `--verbose` | Show full JSON per entry | off |

```bash
# First run with logging:
python consumer-showcase/main.py --scenario snyk --store /tmp/runs.db --log-file /tmp/conductor.log

# See what events are in the log
conductor logs --log /tmp/conductor.log --events

# Filter to one run
conductor logs --log /tmp/conductor.log --run SNYK-001-demo

# Only LLM call events
conductor logs --log /tmp/conductor.log --event llm_call_complete
```

---

## conductor clean — Delete a Run

```
conductor clean [RUN_ID] [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `RUN_ID` | Positional run ID | — |
| `--store` / `--db PATH` | SQLite database path | `conductor_runs.db` |
| `--yes` | Skip confirmation prompt | off |
| `--list` | List all runs in DB (don't delete) | — |
| `--all` | Delete all runs | — |

```bash
# List what's in the DB
conductor clean --list --store /tmp/runs.db

# Delete one run (with confirmation)
conductor clean SNYK-001-demo --store /tmp/runs.db

# Delete without confirmation
conductor clean SNYK-001-demo --store /tmp/runs.db --yes

# Wipe entire DB
conductor clean --all --yes --store /tmp/runs.db
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
- Are excluded by `.gitignore`
- Are safe to delete (`make clean` removes them; `make setup` recreates them)

```bash
make clean   # remove all build artifacts
make setup   # recreate them
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
