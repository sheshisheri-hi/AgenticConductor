# Scripts Reference

Operational commands are provided by two entry points:

- **`dev.sh`** — one-stop developer script; handles setup, demos, and result viewing **without ever needing `source .venv/bin/activate`**
- **`conductor` CLI** — installed into `.venv` by `make setup`; provides `runs`, `plan`, `trace`, `all`, `logs`, `clean`, `check`

---

## Quick Reference — dev.sh (recommended)

```bash
cd NewFramework/ai-agents

# First-time setup (creates .venv, installs all packages including github-copilot-sdk)
./dev.sh setup

# Verify GitHub Copilot token + SDK access
./dev.sh check

# Run mock demo (no token needed — instant, hardcoded responses)
./dev.sh demo snyk
./dev.sh demo-all              # all 5 scenarios

# Run sample demo (real LLM via GitHub Copilot SDK)
./dev.sh sample snyk
./dev.sh sample-all            # all 5 scenarios

# View results
./dev.sh runs                  # list mock runs
./dev.sh runs sample           # list sample (real LLM) runs
./dev.sh plan SNYK-001-demo
./dev.sh plan SNYK-001-demo sample   # from sample DB
./dev.sh trace SNYK-001-demo

# Run tests
./dev.sh test

# Clean
./dev.sh clean                 # remove venv + build artifacts (keeps DBs)
./dev.sh clean db              # remove SQLite databases only (/tmp/runs*.db)
./dev.sh clean all             # everything
```

## Quick Reference — conductor CLI (manual / scripting)

```bash
# No source needed — use full venv path
.venv/bin/conductor runs --store /tmp/runs.db
.venv/bin/conductor plan SNYK-001-demo --store /tmp/runs.db
.venv/bin/conductor trace SNYK-001-demo --store /tmp/runs.db
.venv/bin/conductor all --store /tmp/runs.db
.venv/bin/conductor check
```

Or activate the venv first:
```bash
source .venv/bin/activate
conductor runs --store /tmp/runs.db
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
| `--mode` | LLM mode: `mock`, `sample`, `live` | `mock` |
| `--store PATH` | SQLite database path | `conductor_runs.db` |
| `--workflow PATH` | Override workflow YAML | scenario-default |
| `--log-file PATH` | Write structured JSON logs to file | none |

**LLM Modes:**

| Mode | LLM | Token Required | Speed | Use Case |
|---|---|---|---|---|
| `mock` | StubLLM (hardcoded) | No | Instant | CI, demos, dev iteration |
| `sample` | GitHub Copilot SDK (`gpt-4.1`) | Yes (`GITHUB_COPILOT_TOKEN`) | ~3–6s/agent | Real LLM testing with fixtures |
| `live` | GitHub Copilot SDK + live APIs | Yes | Variable | Full production run |

**Examples:**
```bash
# Mock mode (default) — no token needed
python consumer-showcase/main.py --scenario snyk --store /tmp/runs.db

# Sample mode — real GitHub Copilot LLM
python consumer-showcase/main.py --scenario snyk --mode sample --store /tmp/runs_sample.db

# All scenarios with logs
python consumer-showcase/main.py --all --store /tmp/runs.db --log-file /tmp/conductor.log

# Custom workflow YAML
python consumer-showcase/main.py --scenario snyk --workflow config/workflow_adversarial.yaml --store /tmp/runs.db
```

> **Tip:** Use `./dev.sh demo snyk` (mock) or `./dev.sh sample snyk` (real LLM) — they verify the token and handle the DB path automatically.

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

## conductor check — Verify Token + Copilot Access

```
conductor check
```

Verifies:
- GitHub token found in env (`CONDUCTOR_GITHUB_TOKEN`, `GITHUB_COPILOT_TOKEN`, `COPILOT_GITHUB_TOKEN`, or `GITHUB_TOKEN`)
- `github-copilot-sdk` installed
- Copilot SDK can authenticate and start

```bash
conductor check
# or via dev.sh:
./dev.sh check
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
make test               # run all unit tests
make test-unit          # unit tests only
make test-integration   # integration tests only

make demo               # run all 5 mock demo scenarios
make demo-snyk          # run Snyk CVE scenario (mock)
make demo-sonar         # run SonarQube scenario (mock)
make demo-blackduck     # run BlackDuck scenario (mock)
make demo-ado-defect    # run ADO defect scenario (mock)
make demo-ado-story     # run ADO story scenario (mock)

make demo-sample        # run all 5 scenarios with real LLM (needs token)
make demo-sample-snyk   # run Snyk with real LLM
make demo-sample-sonar  # run SonarQube with real LLM

make lint               # run ruff linter
make clean              # remove .venv, __pycache__, *.egg-info, dist/
make clean-db           # remove SQLite databases (/tmp/runs.db, /tmp/runs_sample.db)
make clean-all          # clean + clean-db (everything)
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
