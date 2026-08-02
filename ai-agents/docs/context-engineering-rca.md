# Context Engineering for Defect RCA on Conductor

**Status:** Implemented (educational Grafana vertical slice)  
**Sample:** [`samples/projects/grafana-rca/`](../samples/projects/grafana-rca/)  
**Workflow:** [`consumer-showcase/config/workflow_rca.yaml`](../consumer-showcase/config/workflow_rca.yaml)

This document captures the design decisions and ownership model from the RCA / context-engineering effort so teams can reference it later without relying on chat or Cursor plan files.

---

## Goal

Engineer the **context** coding agents see when fixing defects — not only the prompt text:

- Product terminology (NL ↔ canonical terms ↔ repos)
- Historical defect patterns (symptom → root cause → resolution)
- Ownership / component → repo maps
- Dynamic assembly into triage/planner prompts

**Stand-in product for education:** public Grafana concepts + sample triples (no employer product data).

---

## Locked decisions

| Decision | Choice |
|---|---|
| Orchestrator | **Extend Conductor** — do not build a second RCA framework |
| Agent model | Enrich **existing** triage/planner (optional dedicated RCA stage later) |
| Memory storage (v1) | SQLite + hybrid keyword/embedding (vector DB later, same tool APIs) |
| Code search | IDE/Copilot repo index — not rebuilt in Conductor v1 |
| IDE org memory | Copilot **Spaces** + optional Memory — configure, don’t reimplement |
| LLM | `ILLMProvider`: stub, Copilot SDK, or **Cursor SDK** |

---

## Two surfaces, one content pack

```text
PRODUCT MEMORY PACK (docs + indexes)
        │
        ├──────────────────┐
        ▼                  ▼
 CONDUCTOR (headless)   IDE (Copilot/Cursor)
 triage → planner       Space + repo semantic index
```

---

## Offline vs runtime

### Offline (consumer / CI)

| Asset | How created | Output |
|---|---|---|
| Glossary, architecture, ownership | **Manual** Markdown/YAML | `docs/` |
| Closed defects export | **Script:** `export_issues` (GitHub) / ADO normalize | `issues_raw.json` |
| Triples | **Script:** heuristic `extract_triples` (+ human edit) | `triples.json` |
| Term index | **Script:** `build_term_index` | `term_index.sqlite` |
| Defect index | **Script:** `build_defect_index` | `defect_index.sqlite` |
| Copilot Space / Memory / code index | **Manual / automatic GitHub** | IDE only |

### Runtime (each defect)

1. Ingest `work_item` + `payload.rca_memory` paths  
2. `maybe_enrich_rca` → `term_hits`, `similar_defects`, `candidate_repos`, `owners`  
3. Triage → Planner (cited fix plan)  
4. `stop_before` code in plan mode  

How repos are chosen: ticket NL → `resolve_terms` → glossary `repos[]` → ownership map → `candidate_repos` (allowlist for planning).

---

## Layer ownership

| Layer | Package | Responsibility |
|---|---|---|
| Core | `conductor-core` | Orchestrator, YAML graph, filters/routes, context, BaseAgent loop |
| Agents | `conductor-agents` | Triage, planner, prompts, fix_plan normalize |
| Integrations | `conductor-integrations` | Memory indexes/builders/export, CursorLLM/CopilotLLM, ADO ingest |
| Consumer | Your app + memory pack | Docs, triples, workflow YAML, `rca_memory` paths, LLM choice, optional Space |

**Consumer does not rebuild:** orchestrator, stock agents (unless customizing prompts), index query logic, Copilot code indexing.

---

## Grafana sample workflow YAML

File: `consumer-showcase/config/workflow_rca.yaml`

- `mode: plan`
- Stages: `triage` → `plan` → `code` with **`stop_before: true`** on code  
- Filters reject `info` severity  
- Showcase `main.py --scenario grafana-rca` attaches pack indexes via `rca_memory`

Full consumer porting steps: [grafana-rca README](../samples/projects/grafana-rca/README.md).

---

## Module map

| Capability | Location |
|---|---|
| Term index | `conductor_integrations.memory.term_index` |
| Defect memory | `conductor_integrations.memory.defect_index` |
| Enrichment | `conductor_integrations.memory.enrich.maybe_enrich_rca` |
| Builders | `python -m conductor_integrations.memory.builders` |
| GitHub/ADO export helpers | `conductor_integrations.memory.export_issues` |
| Triple extract | `conductor_integrations.memory.extract_triples` |
| Cursor LLM | `conductor_integrations.llm.cursor.CursorLLM` |
| Provider factory | `conductor_integrations.llm.create_llm_provider` |

---

## Explicit non-goals (v1)

- Neo4j / Apache AGE  
- Conductor-owned multi-repo code embedding platform  
- Real-time streaming knowledge graph  
- New standalone RCA orchestrator  
- Employer/Aspen product data in this repo  

---

## Related docs

- Sample how-to: [`samples/projects/grafana-rca/README.md`](../samples/projects/grafana-rca/README.md)  
- Workflow YAML reference: [`workflow-yaml.md`](workflow-yaml.md)  
- Consumer onboarding: [`consumer-guide.md`](consumer-guide.md)  
- Plan/execute halt: [ADR-006](adr/ADR-006-plan-execute-mode-stop-before.md)  
