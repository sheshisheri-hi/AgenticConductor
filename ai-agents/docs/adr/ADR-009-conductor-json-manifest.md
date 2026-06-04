# ADR-009: conductor.json Project Manifest

**Status:** Pending  
**Date:** 2026-06-03  

---

## Context

The [GitHub Copilot CLI plugin spec](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference#pluginjson) introduces a `plugin.json` manifest that acts as a single source of truth for a plugin's identity, component paths, and runtime configuration. It declaratively maps where agents, skills, hooks, and MCP/LSP servers live — eliminating manual wiring code.

Conductor currently has no equivalent. Consumers (e.g., `aspen-sentinel`) must wire everything manually in `main.py`:

```python
# current consumer main.py — fully manual
agents = {
    "triage": TriageAgent(llm, context),
    "security": SecurityAgent(llm, context),
    ...
}
graph = WorkflowGraph.from_yaml("config/workflow.yaml")
filters = FilterEngine.from_yaml("config/filters.yaml")
router = RouterEngine.from_yaml("config/routes.yaml")
orchestrator = WorkflowOrchestrator(agents=agents, graph=graph, ...)
```

This is verbose, error-prone, and not scaffoldable. The `conductor new` CLI command cannot produce a truly zero-wiring project without some declarative manifest to read at startup.

The Copilot CLI plugin spec was reviewed as a reference. Several of its patterns map directly onto Conductor's needs and are worth adopting.

---

## Decision

**Pending** — implement a `conductor.json` manifest at the root of each Conductor consumer project. `conductor-core` will auto-discover and load all components declared in this file. `conductor-cli` scaffolding will generate it automatically on `conductor new`.

---

## Proposed `conductor.json` Schema

```json
{
  "name": "aspen-sentinel",
  "description": "Security remediation multi-agent pipeline",
  "version": "1.0.0",
  "author": {
    "name": "Aspen Engineering",
    "email": "aspen@example.com"
  },
  "license": "MIT",

  "agents": "agents/",
  "workflow": "config/workflow.yaml",
  "filters": "config/filters.yaml",
  "routes": "config/routes.yaml",
  "hooks": "config/hooks.json",
  "integrations": ["snyk", "ado", "github"],

  "disabled_agents": [],
  "strict": true
}
```

Fields borrowed from the Copilot CLI plugin spec are marked below.

---

## Ideas Borrowed from Copilot CLI `plugin.json`

| Copilot CLI concept | Conductor equivalent | Notes |
|---|---|---|
| `name`, `version`, `author`, `description`, `license` | Identity metadata in `conductor.json` | Standard fields; enable future registry/marketplace |
| `agents: string \| string[]` | `"agents": "agents/"` or `["agents/", "extra-agents/"]` | Multi-path so consumers can split domain vs utility agents |
| `skills: string \| string[]` | `"integrations": ["snyk", "ado"]` | Closest analog; integrations are Conductor's "skills" |
| `hooks: string \| object` | `"hooks": "config/hooks.json"` | Pre/post-stage lifecycle hooks path |
| Plugin `enable`/`disable` commands | `"disabled_agents": ["NotifyAgent"]` | Toggle agents without code changes |
| `strict: boolean` | `"strict": true` | Full YAML schema validation on startup; default `true` |
| `marketplace.json` template registry | `conductor new --template security-remediation@conductor-templates` | A GitHub-hosted `marketplace.json` listing official templates |

---

## Benefits

### 1. Eliminate `main.py` wiring boilerplate
`WorkflowOrchestrator.from_manifest("conductor.json")` reads the file and auto-discovers agents, graphs, filters, and routers. Consumers go from ~60 lines of wiring to ~5.

### 2. Enable true zero-config scaffolding
`conductor new my-project` generates a working `conductor.json` + stubs. The project runs immediately with no edits required.

### 3. Toggle agents without code changes
`"disabled_agents": ["NotifyAgent"]` lets ops/SRE teams disable an agent in production config without touching Python. Mirrors `copilot plugin disable NAME`.

### 4. Strict validation at startup
`"strict": true` triggers full YAML schema validation when the orchestrator boots, catching misconfigured workflow graphs, missing agent keys, and broken filter rules before the first run.

### 5. Multi-path agent directories
`"agents": ["agents/", "extra-agents/"]` lets large projects split agent modules without restructuring. Mirrors Copilot CLI's multi-path support for agents and skills.

### 6. Foundation for a template marketplace
The `marketplace.json` pattern enables a `conductor-templates` GitHub repo where teams publish reusable workflow templates. Future `conductor new --template incident-response@my-org` would pull from that registry.

### 7. Machine-readable project identity
`name`, `version`, `author` fields make projects identifiable in telemetry dashboards, log aggregators, and future registries — without adding them as env vars or hardcoded strings.

---

## Changes Required

### `conductor-core`

| File | Change |
|---|---|
| `core/manifest.py` (new) | `ConductorManifest` dataclass + `load_manifest(path)` parser with JSON schema validation |
| `core/orchestrator.py` | Add `WorkflowOrchestrator.from_manifest(path)` class method that reads manifest and wires components |
| `core/agent_registry.py` (new) | `AgentRegistry.discover(paths)` — scans agent directories, imports classes, respects `disabled_agents` |
| `core/validators.py` (new) | Strict mode validator: validates `workflow.yaml`, `filters.yaml`, `routes.yaml` against their JSON schemas on startup |
| `core/interfaces.py` | Add `IManifestLoader` interface |

### `conductor-cli`

| File | Change |
|---|---|
| `cli/new.py` | Generate `conductor.json` as part of `conductor new` scaffolding |
| `cli/validate.py` (new) | `conductor validate` command — loads manifest, runs strict validation, reports errors |
| `cli/templates/` | Add `conductor.json.j2` Jinja template per scaffold template |

### `conductor-integrations`

| File | Change |
|---|---|
| `integrations/registry.py` (new) | `IntegrationRegistry` — maps integration name strings (e.g., `"snyk"`) to client classes for manifest-driven loading |

### Consumer (`aspen-sentinel`)

| File | Change |
|---|---|
| `conductor.json` (new) | Add manifest at project root |
| `main.py` | Replace ~60 lines of wiring with `WorkflowOrchestrator.from_manifest("conductor.json")` |

### Schema & Docs

| Item | Change |
|---|---|
| `docs/conductor-json-schema.json` (new) | JSON Schema for `conductor.json` — enables IDE validation |
| `docs/adr/` | This ADR |
| `README.md` | Add manifest quickstart section |

---

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Keep manual wiring in `main.py` | Verbose, not scaffoldable, no toggle/disable, no validation |
| Use env vars for config paths | Not structured, no schema, no multi-path support, hard to validate |
| Use `pyproject.toml` `[tool.conductor]` section | Ties manifest to Python packaging; non-Python consumers excluded; no runtime path |
| Inline everything in `workflow.yaml` | YAML conflates orchestration config with project identity; harder to parse at CLI level |

---

## Consequences

**Positive:**
- Consumer `main.py` collapses from ~60 lines to ~5
- `conductor new` produces a runnable project with zero edits
- Ops teams can toggle agents via config, not code
- Startup validation catches errors before the first LLM call
- Foundation for a public template marketplace

**Negative / Trade-offs:**
- One more config file format to document and version
- `AgentRegistry.discover()` uses dynamic imports — must handle import errors gracefully
- `strict: true` adds ~100–200 ms startup time for YAML validation (acceptable; can be disabled)
- Template marketplace requires a separate repo and governance process

---

## References

- [GitHub Copilot CLI Plugin Reference — plugin.json](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference#pluginjson)
- [ADR-001: Monorepo Multi-Package Structure](ADR-001-monorepo-package-structure.md)
- [ADR-002: YAML-Driven Workflow Graph](ADR-002-yaml-driven-workflow-graph.md)
- [PLAN.md — conductor-cli scaffolding section](../../PLAN.md)
