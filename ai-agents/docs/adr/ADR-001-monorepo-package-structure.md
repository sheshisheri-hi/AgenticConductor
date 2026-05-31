# ADR-001: Monorepo Multi-Package Structure

**Status:** Accepted  
**Date:** 2026-05-01  

---

## Context

Conductor needs to be usable both as a framework (other teams consume it) and as a runnable demo (consumer-showcase). These two concerns have different dependency footprints, different release cadences, and different audiences:

- Framework core (`conductor-core`) — zero optional dependencies, stable API
- Agents (`conductor-agents`) — depends on core only
- Integrations (`conductor-integrations`) — depends on core + optional: `github-copilot-sdk`, `opentelemetry-*`
- Consumer showcase (`consumer-showcase`) — depends on all of the above + demo fixtures
- CLI tool (`conductor-cli`) — depends on core + integrations for `conductor check`, `conductor runs`

Two alternatives were considered:

| Option | Description |
|--------|-------------|
| A | Single flat package: everything in one `conductor/` namespace |
| B | Monorepo with separate installable packages (chosen) |
| C | Separate git repos with versioned releases |

---

## Decision

**Option B — monorepo with separate `pyproject.toml` packages**, each independently installable via `pip install -e "package[extras]"`.

```
ai-agents/
├── conductor-core/           # pip install -e conductor-core[dev]
├── conductor-agents/         # pip install -e conductor-agents[dev]
├── conductor-integrations/   # pip install -e conductor-integrations[dev,copilot]
├── consumer-showcase/        # pip install -e consumer-showcase[dev]
└── conductor-cli/            # pip install -e conductor-cli[dev]
```

---

## Consequences

**Positive:**
- `conductor-core` can be released independently with zero LLM provider dependencies
- Teams can install only what they need (e.g. `conductor-core` + `conductor-agents` without `copilot` extras)
- Each package has isolated unit tests — `conductor-core` tests never need a GitHub token
- `dev.sh setup` installs all 5 packages once via editable installs — no version coordination needed during development

**Negative:**
- `dev.sh setup` must install in dependency order (core → agents → integrations → showcase → cli)
- Circular imports are possible if package boundaries are violated — enforced by convention, not tooling
- Each package needs its own `pyproject.toml`, `tests/` directory, and CI step

**Accepted risk:**
- No cross-package version pinning during development (all editable) — handled at release time
