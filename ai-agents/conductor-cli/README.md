# conductor-cli

The `conductor` command-line interface for interacting with Conductor pipelines without writing Python code.

---

## Install

```bash
# From repo root (development)
pip install -e "ai-agents/conductor-cli[dev]"

# From GitHub
pip install "git+https://github.com/sheshisheri-hi/AgenticConductor.git#subdirectory=ai-agents/conductor-cli"
```

See [docs/installation.md](../docs/installation.md) for all install options including Artifactory.

---

## Commands

```
conductor runs     List all pipeline runs
conductor plan     Show fix plan for a run
conductor trace    Show full reasoning trace for a run
conductor all      Show runs with trace + plan summary
conductor clean    Delete a run from the result store
conductor logs     Inspect structured JSON log file
conductor version  Show CLI version
```

---

## Usage Examples

```bash
# List all runs
conductor runs --store /tmp/runs.db

# Filter by source, show last 5
conductor runs --store /tmp/runs.db --source snyk --last 5

# Show fix plan
conductor plan SNYK-001-demo --store /tmp/runs.db

# Full reasoning trace
conductor trace SNYK-001-demo --store /tmp/runs.db

# Trace with prompts and raw LLM response
conductor trace SNYK-001-demo --store /tmp/runs.db --prompts --raw

# All runs with trace + plan (compact view)
conductor all --store /tmp/runs.db --last 5 --no-trace

# Delete a run (with confirmation)
conductor clean SNYK-001-demo --store /tmp/runs.db

# Delete without confirmation
conductor clean SNYK-001-demo --store /tmp/runs.db --yes

# Wipe all runs
conductor clean --all --store /tmp/runs.db --yes

# Inspect log file
conductor logs --run SNYK-001-demo
conductor logs --events                         # list unique event types
conductor logs --event agent_decision --last 20
```

---

## Help for any command

```bash
conductor --help
conductor runs --help
conductor trace --help
```

---

## Implementation

- **Framework**: [`typer`](https://typer.tiangolo.com/) + [`rich`](https://rich.readthedocs.io/)
- **Entry point**: `conductor_cli/main.py` → `app`
- **Registered as**: `conductor` command via `pyproject.toml [project.scripts]`

The CLI is a thin, rich-formatted wrapper over `conductor-core`'s `SQLiteResultStore`. It mirrors the `consumer-showcase/scripts/` scripts but with better formatting and a unified entry point.

---

## Planned (not yet implemented)

```bash
conductor run --scenario snyk --workflow config/workflow.yaml --store runs.db
conductor init my-consumer --template security
```
