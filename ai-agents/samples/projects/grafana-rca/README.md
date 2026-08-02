# Grafana RCA educational showcase

**What this is:** A complete, copyable example of **context-engineered defect RCA** on Conductor — using public Grafana as a stand-in product (no employer data).

**Design reference (framework docs):** [`docs/context-engineering-rca.md`](../../../docs/context-engineering-rca.md) — decisions, ownership matrix, offline vs runtime.

**What you’ll see when you run it:** A natural-language bug (“charts freeze after changing time range”) is enriched with product terms, similar past defects, candidate repos, and owners; triage + planner (Cursor or stub LLM) produce a cited fix plan, then halt before code.

---

## What this sample showcases

| Concept | How it appears here |
|---|---|
| **Context engineering** | Agents don’t rely on the ticket alone — offline product memory is retrieved into the prompt |
| **Product terminology bridge** | Business/NL language → canonical terms → component → repos (`glossary.yaml` + hybrid term index) |
| **Historical defect memory** | Past bugs as symptom / root_cause / resolution triples → similar-defect search |
| **Ownership / multi-repo map** | Component → repo → owners (`ownership.yaml`) without scanning the whole org |
| **Offline builders vs runtime tools** | Scripts build SQLite indexes; agents only *read* them at run time |
| **Existing agents, not a new orchestrator** | Same Conductor workflow graph; triage/planner call `maybe_enrich_rca` |
| **Plan-mode halt** | Stops after planner so humans review the RCA-backed plan |
| **Pluggable LLM** | Stub, GitHub Copilot, or Cursor SDK (`--mode cursor`) via `ILLMProvider` |
| **IDE complement (optional)** | Same docs can feed Copilot Spaces; code search stays with the IDE |

This is **not** an AI-SRE telemetry product (no Datadog/PagerDuty). It is **dev defect RCA**: ticket → similar history + product map → plan.

---

## Sample inputs → what runs → where to see results

**This demo does not fetch live GitHub issues.** Everything is curated under this pack.

| Piece | File | What it is |
|---|---|---|
| Incoming defect (1) | [`data/work_item.json`](data/work_item.json) | Synthetic ticket `GF-DEMO-42` (“charts freeze…”); `source: github` only for routing |
| Past defects (6) | [`data/triples.json`](data/triples.json) | Curated triples `GF-1001`…`GF-1006` (fake issue URLs; educational) |
| Product map | [`docs/glossary.yaml`](docs/glossary.yaml), [`docs/ownership.yaml`](docs/ownership.yaml) | Terms + component → repo → owners |
| Workflow | [`../../consumer-showcase/config/workflow_rca.yaml`](../../consumer-showcase/config/workflow_rca.yaml) | triage → plan → halt before code |
| Wiring | [`../../consumer-showcase/main.py`](../../consumer-showcase/main.py) (`--scenario grafana-rca`) | Builds SQLite if needed, sets `payload.rca_memory`, prints results |

**What the sample is doing:** load that one ticket → retrieve top terms + up to 3 similar triples + owners → triage → planner Fix Plan → **stop** (no code edits).

**Where results appear:** stdout from the showcase run only (unless you pass `--store`). There is no `results/` folder in this pack. Look for these blocks in the console:

```text
=== Conductor Showcase Result ===
  [triage]  … → proceed
    • … reasoning citing dashboard / time-range terms …
  [planner] … → proceed
    • …

Fix Plan : …
Effort   : …
  → step …
Files    : …

RCA enrichment:
  terms   : ['…', …]          # from glossary match
  similar : ['GF-100x', …]    # from triples (k_defects=3)
  repos   : ['…']
  owners  : […]
```

**Success criteria:** enrichment lines are non-empty; Fix Plan has summary + steps; run ends without a code-agent patch. With `--mode mock`, text is stubbed but the same blocks print. With `--mode cursor`, wording is live LLM.

**Inspect the sample itself (no run needed):** open `data/work_item.json` + `data/triples.json` + `docs/`. Indexes `data/*.sqlite` appear after first run (gitignored).

---

## Technical concepts (architecture)

```text
OFFLINE (consumer / CI)                         RUNTIME (Conductor)
─────────────────────────                       ─────────────────────────
glossary.yaml  ──► build_term_index ──► term_index.sqlite
                                         │
triples.json   ──► build_defect_index ─► defect_index.sqlite
                                         │
ownership.yaml ──────────────────────────┼──► maybe_enrich_rca()
architecture.md / failure-modes.md ──────┘         │
                                                   ▼
work_item ──► triage ──► planner ──► fix_plan (halt)
              └─ payload: term_hits, similar_defects,
                 candidate_repos, owners, rca_context
```

| Piece | Tech |
|---|---|
| Term resolve | Hybrid: alias/keyword boost + hashed bag-of-words embeddings in SQLite |
| Similar defects | Cosine similarity over embedded symptom+root_cause strings in SQLite |
| Enrichment | `conductor_integrations.memory.enrich.maybe_enrich_rca` |
| Workflow | `consumer-showcase/config/workflow_rca.yaml` |
| LLM | `CursorLLM` / `CopilotLLM` / stub — `create_llm_provider()` |

**Deferred on purpose:** Neo4j, Conductor-owned full-repo code embeddings, live streaming KG updates.

---

## Orchestration workflow (Grafana case)

Demo wiring lives in the **consumer-showcase**, not inside the `grafana-rca/` pack folder:

[`consumer-showcase/config/workflow_rca.yaml`](../../consumer-showcase/config/workflow_rca.yaml)

```yaml
workflow:
  name: grafana_rca
  mode: plan          # plan-first; do not auto-execute code

filters:
  - type: reject_if_in
    field: work_item.severity
    values: [info]

routes:
  - match:
      source: [ado, mock, github, grafana]
    graph: ado_remediation
  - match:
      source: ["*"]
    graph: escalate_human

stages:
  - name: triage
    agent: triage          # framework agent
    on_proceed: plan

  - name: plan
    agent: planner         # framework agent
    on_proceed: code

  - name: code
    agent: code
    stop_before: true      # HALT here in plan mode — human reviews Fix Plan
```

### Runtime path for this YAML (step by step)

Start command:

```bash
python main.py --scenario grafana-rca [--mode cursor|mock]
```

| Step | Where | What happens |
|---|---|---|
| **0. Entry** | `consumer-showcase/main.py` | `--scenario grafana-rca` selects `config/workflow_rca.yaml` and the Grafana pack path |
| **1. Offline ensure** | `_prepare_grafana_rca_pack()` in `main.py` | Builds `term_index.sqlite` / `defect_index.sqlite` if missing; loads `data/work_item.json` |
| **2. Context create** | `main.py` → `WorkflowContext` | Sets `payload.work_item` + `payload.rca_memory` = paths to term DB, defect DB, `ownership.yaml` |
| **3. LLM choose** | `main.py` | `mock` → stub; `cursor` → `CursorLLM`; else Copilot via factory |
| **4. Orchestrator start** | `conductor-core` `WorkflowOrchestrator` | Loads YAML graph; `mode: plan` |
| **5. Filter** | YAML `filters` | Drops work items with severity `info` (demo item is HIGH → passes) |
| **6. Route** | YAML `routes` | Matches `work_item.source` (`github` in demo) → continues on remediation stages |
| **7. Stage `triage`** | YAML → `TriageAgent` | See detail below |
| **8. Stage `plan`** | YAML → `PlannerAgent` | See detail below |
| **9. Stage `code` + halt** | YAML `stop_before: true` | Orchestrator **stops before** CodeAgent runs — you only get a plan |

#### Stage 7 — triage (detail)

```text
TriageAgent.run()
  1. maybe_enrich_rca(context)     # only if payload.rca_memory is set
       resolve_terms(ticket text)     → payload.term_hits
       search_similar_defects(...)    → payload.similar_defects
       ownership lookup               → payload.owners, candidate_repos
       format                          → payload.rca_context (prompt text)
  2. Load triage_system.md + triage_user.md
       user prompt includes $rca_context
  3. LLM call → AgentDecision (proceed/block, reasoning, confidence)
  4. on_proceed: plan  (from YAML)
```

#### Stage 8 — planner (detail)

```text
PlannerAgent.run()
  1. maybe_enrich_rca again (no-op if already rca_enriched)
  2. Load planner prompts; $rca_context + prior triage decision
  3. LLM call → JSON with fix_plan
  4. normalize_fix_plan() → payload.fix_plan
       (summary, steps, estimated_effort, files_to_change, …)
  5. on_proceed: code  (from YAML)
```

#### Stage 9 — halt (detail)

```text
Orchestrator sees next stage = code with stop_before: true and mode=plan
  → plan_mode_halt
  → run ends
  → main.py prints triage/planner reasoning + Fix Plan + RCA enrichment lines
```

#### What you should see in the console when it worked

1. Triage `proceed` with reasoning that cites terms / GF-* defects  
2. Planner `proceed` with a **Fix Plan** block (summary, steps, files)  
3. **RCA enrichment:** terms · similar · repos · owners  
4. **No** code-agent edits (halted)

#### Mental model (one line)

**Consumer prepares memory + YAML + payload paths → core runs the graph → agents enrich then call LLM → stop before code.**

`showcase/main.py --scenario grafana-rca` is the reference for steps 0–3. Consumers typically **copy** `workflow_rca.yaml` and the `rca_memory` payload pattern into their own entrypoint.

---

## Who owns what: core vs agents vs integrations vs consumer

| Layer | Package | Provides (you do **not** rewrite) | Grafana demo uses |
|---|---|---|---|
| **Framework core** | `conductor-core` | `WorkflowOrchestrator`, `WorkflowGraph` (YAML), filters/routes, `WorkflowContext`, `BaseAgent` enrich loop, result store | Loads `workflow_rca.yaml`, runs stages, plan halt |
| **Domain agents** | `conductor-agents` | `TriageAgent`, `PlannerAgent`, prompts/SKILL, `fix_plan` normalize | Triage → planner; calls enrich when `rca_memory` set |
| **Integrations** | `conductor-integrations` | Memory indexes/builders/export, `CursorLLM`/`CopilotLLM`, ADO/GitHub ingest helpers | Term/defect SQLite, `maybe_enrich_rca`, Cursor provider |
| **Consumer / sample** | **You** (here: `grafana-rca` pack + showcase wiring) | Product docs, triples, ownership, workflow YAML copy, `payload.rca_memory` paths, LLM choice, optional Copilot Space | This folder’s docs/data + showcase scenario |

### Consumer must do (summary)

1. **Content:** glossary, architecture, ownership, defect history → triples  
2. **Offline:** run builders → SQLite paths  
3. **Config:** workflow YAML (copy `workflow_rca.yaml`) + inject `rca_memory` in your `main`/manifest  
4. **Runtime choice:** which LLM provider  
5. **Optional:** Copilot Space for IDE humans  

### Consumer should **not** rebuild

- Orchestrator / YAML engine  
- Triage/planner agents (unless customizing prompts)  
- Index query logic (`resolve_terms` / `search_similar_defects`)  
- Copilot’s per-repo code index  

---

## Layout

```text
grafana-rca/
  docs/
    glossary.yaml      # machine glossary (canonical + aliases + repos)
    glossary.md        # human pointer
    architecture.md    # component map
    ownership.yaml     # component → repo → owners
    ownership-map.md
    failure-modes.md   # human rollup of patterns
  data/
    work_item.json     # NL demo defect
    triples.json       # curated historical triples
    *.sqlite           # built indexes (gitignored; auto-built on run)
  README.md            # this file
```

---

## Prerequisites and how to run

### One-time setup

From the monorepo `ai-agents/` root (or follow [`docs/installation.md`](../../../docs/installation.md) / `make setup`):

```bash
cd ai-agents
python -m venv .venv && source .venv/bin/activate   # if you do not already have .venv
pip install -e conductor-core/
pip install -e conductor-agents/
pip install -e "conductor-integrations[dev]"        # includes cursor-sdk + copilot extras used in tests
# optional: only the LLM you need
#   pip install -e "conductor-integrations[copilot]"
#   pip install -e "conductor-integrations[cursor]"
```

Use the venv Python for the commands below (paths assume cwd = `ai-agents/conductor-integrations`).

### What is expected (all modes)

Console prints triage + planner decisions, a **Fix Plan** (summary / steps / files), and **RCA enrichment** (terms, `GF-*` similar IDs, repos, owners). The run **halts before code** — no repo edits. Details: **Sample inputs → what runs → where to see results** above.

| Mode | API key / host tooling | Install extra | Live LLM? |
|---|---|---|---|
| Stub (default) | none | none | No — canned text, same console shape |
| Copilot | GitHub token + **GitHub Copilot CLI** ([install](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)) | `[copilot]` | Yes |
| Cursor | `CURSOR_API_KEY` | `[cursor]` | Yes |

---

## Run the demo

```bash
cd ai-agents/conductor-integrations
```

### A) Stub — no key (smoke test)

```bash
.venv/bin/python ../consumer-showcase/main.py --scenario grafana-rca
# same as --mode mock
```

### B) GitHub Copilot

`github-copilot-sdk` drives a local **GitHub Copilot CLI** subprocess — that is **not** the `gh` CLI / `gh-copilot` extension.

Install Copilot CLI (once). Official guide: [Install Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli). Framework notes: [ADR-003](../../../docs/adr/ADR-003-copilot-sdk-over-openai-api.md), [docs/scripts.md](../../../docs/scripts.md).

```bash
# Requires Node.js 22+ (see GitHub install docs for Homebrew / WinGet / script options)
npm install -g @github/copilot
copilot   # authenticate with your GitHub account when prompted
```

Set **one** of these (first match wins):

```bash
export CONDUCTOR_GITHUB_TOKEN=ghp_...   # preferred
# or: export GITHUB_COPILOT_TOKEN=ghp_...
# or: export COPILOT_GITHUB_TOKEN=ghp_...
# or: export GITHUB_TOKEN=ghp_...
```

Token / account needs an active **Copilot subscription**. Optional model: `export CONDUCTOR_LLM_MODEL=gpt-4.1`.

```bash
pip install -e ".[copilot]"   # once — installs github-copilot-sdk
# optional sanity check from ai-agents/:
#   ./dev.sh check
.venv/bin/python ../consumer-showcase/main.py --scenario grafana-rca --mode sample
```

`--mode sample` uses Copilot by default (or whatever `CONDUCTOR_LLM_PROVIDER` is set to).### C) Cursor SDK

```bash
export CURSOR_API_KEY=cursor_...   # from Cursor Dashboard (user or service key)
# optional: export CONDUCTOR_LLM_MODEL=composer-2.5
```

```bash
pip install -e ".[cursor]"   # once, from conductor-integrations
.venv/bin/python ../consumer-showcase/main.py --scenario grafana-rca --mode cursor
```

Results print in that terminal. Optional persistence: showcase `--store` for DB-backed run history.

Rebuild indexes only if you change glossary/triples:

```bash
python -m conductor_integrations.memory.builders all \
  --pack-dir ../samples/projects/grafana-rca
```

---

## What a consumer must do to implement this on their product

Copy the **pattern**, replace Grafana content with your product. Conductor already provides the tools.

### 1. Create your product memory pack (manual)

In your consumer repo (or a docs repo), author:

| File | You fill in |
|---|---|
| `glossary.yaml` | Domain terms, NL aliases, component, `repos[]`, optional `code_hints` |
| `architecture.md` | Components, boundaries, data flows (mermaid is enough) |
| `ownership.yaml` | component → team → repos → owners |
| `failure-modes.md` | Optional human summary of known patterns |

### 2. Build historical defect memory (scripts we provide)

```bash
# GitHub example
python -m conductor_integrations.memory.export_issues github \
  --owner YOUR_ORG --repo YOUR_REPO \
  --out data/issues_raw.json

# Or ADO: fetch via ADOClient, map each item with normalize_ado_work_item(), write issues_raw.json

python -m conductor_integrations.memory.builders from-export \
  --issues-raw data/issues_raw.json \
  --triples-out data/triples.json \
  --defect-index-out data/defect_index.sqlite

python -m conductor_integrations.memory.builders terms \
  --glossary docs/glossary.yaml \
  --out data/term_index.sqlite
```

Review/edit `triples.json` for quality (heuristic extract is a bootstrap; improve over time).

### 3. Wire Conductor (config, not a new framework)

1. **Copy** [`workflow_rca.yaml`](../../consumer-showcase/config/workflow_rca.yaml) (or equivalent): stages `triage → plan → code(stop_before)`.
2. Register it in your consumer `conductor.json` / `main.py` the same way showcase maps `--scenario grafana-rca`.
3. On each run, put into `WorkflowContext.payload`:

```python
payload["work_item"] = {...}  # your defect
payload["rca_memory"] = {
    "term_index": "data/term_index.sqlite",
    "defect_index": "data/defect_index.sqlite",
    "ownership": "docs/ownership.yaml",
}
```

4. Instantiate stock agents from `conductor-agents` and an `ILLMProvider` from `conductor-integrations` — do not fork the orchestrator.
5. Choose LLM: stub / Copilot / Cursor (`CONDUCTOR_LLM_PROVIDER` or `--mode cursor`).

### 4. Optional IDE path (human implementers)

- Create a **Copilot Space** with the same docs + key code repos.
- Copilot **Memory** / per-repo semantic index: configure in GitHub/Copilot — do not rebuild in Conductor.
- Engineers open `candidate_repos` from the plan and implement with IDE agents grounded in the Space.

### 5. Consumer checklist

- [ ] Glossary covers how users *describe* failures (not only official jargon)
- [ ] Ownership maps every component you care about to at least one repo
- [ ] Closed defects exported and tripled (start curated, then automate)
- [ ] Indexes rebuilt in CI when docs/triples change
- [ ] Workflow injects `rca_memory` paths
- [ ] Plan mode reviewed by humans before code agents run
- [ ] (Optional) Copilot Space mirrors the same docs pack

---

## IDE path: Copilot Spaces (optional detail)

Conductor does **not** create Spaces. For VS Code / Copilot Enterprise:

1. Open [Copilot Spaces](https://docs.github.com/en/copilot/concepts/context/spaces) (enable in org if required).
2. Create e.g. `Product RCA Context`.
3. Attach: your `docs/` pack, key repos, sample issues/PRs.
4. IDE Agent mode + GitHub MCP Spaces tools (`list_copilot_spaces` / `get_copilot_space`).
5. Implement using the Conductor-produced plan + Space.

```text
Same docs pack ──► Conductor SQLite indexes ──► headless RCA workflow
              └──► Copilot Space            ──► IDE agent (human)
```
