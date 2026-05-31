# conductor-cli

> **Status: Planned — not yet implemented.**

This package will provide a command-line interface for interacting with Conductor pipelines without writing Python code.

---

## Planned Commands

```bash
# Run a pipeline
conductor run --scenario snyk --workflow config/workflow_security.yaml --store runs.db

# Show results
conductor runs --store runs.db
conductor plan --store runs.db --run SNYK-001
conductor trace --store runs.db --run SNYK-001 --prompts
conductor logs --log conductor.log --events

# Manage runs
conductor clean --store runs.db --run SNYK-001

# Initialize a new consumer project
conductor init my-consumer --template security
conductor init my-consumer --template custom
```

---

## Current Workaround

Until this package is implemented, use the scripts in `consumer-showcase/scripts/`:

```bash
python consumer-showcase/main.py --all --store /tmp/runs.db
python consumer-showcase/scripts/show_runs.py --store /tmp/runs.db
python consumer-showcase/scripts/show_plan.py --store /tmp/runs.db --run SNYK-001-demo
python consumer-showcase/scripts/show_trace.py --store /tmp/runs.db --run SNYK-001-demo
```

See [docs/scripts.md](../docs/scripts.md) for the full scripts reference.

---

## Contributing

If you want to implement the CLI, this folder is the right place. Suggested tech stack:
- [`typer`](https://typer.tiangolo.com/) for CLI framework
- [`rich`](https://rich.readthedocs.io/) for terminal output (already used in scripts)
- Install via `pip install -e ".[dev]"` once `pyproject.toml` is added
