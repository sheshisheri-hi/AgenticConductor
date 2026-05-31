# Conductor — Multi-Agent Workflow Orchestration Framework
## Architecture Plan (Extracted from Aspen-Sentinel)

---

## Vision

Build **Conductor** — a generic, reusable multi-agent workflow orchestration framework.
Aspen-Sentinel becomes the first consumer and reference implementation.
Any team in any company can scaffold a new project with `conductor new my-project`
and get a fully working agent pipeline in minutes.

---

## Three Packages

| Package | Purpose | Who uses it |
|---|---|---|
| `conductor-core` | Orchestration engine, runners, context, interfaces | Everyone |
| `conductor-integrations` | ADO, Snyk, Sonar, BlackDuck, Jira, GitHub, Slack, Teams, Git providers | Anyone needing these sources |
| `conductor-cli` | `conductor new my-project` scaffolding CLI | Developers starting a new project |

Aspen-Sentinel = consumer app that uses `conductor-core` + `conductor-integrations`.

---

## Problem with Aspen-Sentinel's Current Design

| Issue | Evidence |
|---|---|
| `PipelineContext` has domain fields baked in | `work_item`, `fix_plan`, `threat_context`, `branch_map` |
| Orchestrator has 12 hardcoded agent slots | `self._triage`, `self._security`, etc. in `pipeline.py` |
| Routing is imperative Python | `handler_map` with hardcoded stage names |
| No parallelism | Security + Reviewer run sequentially on same code |
| No observability | `len//4` token estimate, no cost/latency/confidence tracking |
| Hand-rolled state machine | `pipeline.py` + `transitions.py` + `stages.py` = ~700 lines |
| Not reusable | Another team must fork the entire repo |
| Group chat missing | No multi-agent collaborative reasoning panel |
| No scaffolding | No way to start a new project from a template |

---

## Target Architecture — Three Layers

```
┌──────────────────────────────────────────────────────────┐
│           LAYER 1: conductor-core                        │
│           pip install conductor-core                     │
│                                                          │
│  core/context.py          WorkflowContext(               │
│                             run_id, stage,               │
│                             payload: dict,               │
│                             decisions, blocked,          │
│                             human_notes, telemetry,      │
│                             mode                         │
│                           )                              │
│                                                          │
│  core/base_agent.py       BaseAgent                      │
│                           — confidence gating            │
│                           — multi-round enrichment       │
│                           — token + latency tracking     │
│                                                          │
│  core/functional_agent.py FunctionalAgent                │
│                           — no LLM, pure side-effects    │
│                           — Git, Notify, Feedback        │
│                                                          │
│  core/graph.py            WorkflowGraph.from_yaml()      │
│                           — stages, transitions          │
│                           — parallel_groups              │
│                           — group_chats                  │
│                           — human_gates                  │
│                           — modes (plan / execute)       │
│                           — filters, routes              │
│                                                          │
│  core/orchestrator.py     WorkflowOrchestrator(          │
│                             agents: dict[str, IAgent],   │
│                             graph: WorkflowGraph,        │
│                             db, telemetry                │
│                           )                              │
│                           LangGraph as execution engine  │
│                                                          │
│  core/runners/            SequentialRunner               │
│                           ParallelRunner (asyncio.gather)│
│                           GroupChatRunner (MAF pattern)  │
│                                                          │
│  core/filters.py          FilterEngine                   │
│                           — reject_if_in                 │
│                           — reject_if_null               │
│                           — reject_if_matches (regex)    │
│                           — deduplication                │
│                                                          │
│  core/router.py           RouterEngine                   │
│                           — payload fields → graph       │
│                                                          │
│  core/telemetry.py        TelemetryData                  │
│                           — tokens_used (actual)         │
│                           — latency_ms per agent         │
│                           — confidence_trend             │
│                           — recode_count                 │
│                           — cost report per run          │
│                                                          │
│  core/interfaces.py       IAgent, ILLMProvider,          │
│                           IFunctionalAgent, INotifier,   │
│                           IGitProvider, IIngestClient,   │
│                           IEnrichmentTool                │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│           LAYER 2: conductor-integrations                │
│           pip install conductor-integrations             │
│           (optional — use what you need)                 │
│                                                          │
│  Work Item Sources:                                      │
│    AdoIngestClient        — Azure DevOps work items      │
│    JiraIngestClient       — Jira issues                  │
│    GitHubIngestClient     — GitHub Issues / GHAS alerts  │
│    ServiceNowClient       — ServiceNow incidents         │
│                                                          │
│  Security Scanners:                                      │
│    SnykIngestClient       — Snyk vulnerabilities         │
│    SonarIngestClient      — SonarQube findings           │
│    BlackDuckClient        — Black Duck license/vulns     │
│    TrivyClient            — Trivy container scans        │
│    BanditClient           — Bandit Python SAST           │
│                                                          │
│  Notifications:                                          │
│    SlackNotifier          — Slack channels               │
│    TeamsNotifier          — Microsoft Teams              │
│    EmailNotifier          — SMTP email                   │
│                                                          │
│  Git Providers:                                          │
│    GitHubProvider         — GitHub branches + PRs        │
│    AzureReposProvider     — Azure Repos                  │
│    GitLabProvider         — GitLab MRs                   │
│                                                          │
│  All implement conductor-core interfaces.                │
│  Consumers extend any client for custom behavior.        │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│           LAYER 3: conductor-cli                         │
│           pip install conductor-cli                      │
│                                                          │
│  conductor new my-project                                │
│  conductor new my-project --template security-remediation│
│  conductor new my-project --template incident-response   │
│  conductor new my-project --template hr-workflow         │
│                                                          │
│  Scaffolds:                                              │
│    agents/triage_agent.py      — starter template       │
│    agents/reviewer_agent.py    — starter template       │
│    workflow.yaml               — pipeline config        │
│    filters.yaml                — filter rules           │
│    routes.yaml                 — routing rules          │
│    main.py                     — wired and ready        │
│    requirements.txt            — conductor deps         │
│    README.md                   — how to customize       │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│           CONSUMER: aspen-sentinel                       │
│           (reference implementation)                     │
│                                                          │
│  agents/     TriageAgent, SecurityAgent, PlannerAgent,   │
│              CodeAgent, ReviewerAgent, ScribeAgent,      │
│              ResolverAgent, GitAgent, FeedbackAgent,     │
│              NotifyAgent, DeliveryAgent                  │
│                                                          │
│  schemas/    DefectRecord, WorkItem                      │
│              (lives inside payload: dict)                │
│                                                          │
│  config/     filters.yaml, routes.yaml, workflow.yaml,   │
│              repo_registry.yaml, ingest_filters.yaml,    │
│              git rules                                   │
│                                                          │
│  ingest/     Uses conductor-integrations clients         │
│              (Snyk, Sonar, BlackDuck, ADO)               │
│              Extends where Aspen-specific behavior needed│
│                                                          │
│  main.py     Builds agents, loads YAML,                  │
│              hands to WorkflowOrchestrator               │
└──────────────────────────────────────────────────────────┘
```

---

## Framework Primitives

### 1. WorkflowContext (replaces PipelineContext)
```python
class WorkflowContext(BaseModel):
    run_id: str
    stage: str = "created"
    payload: dict                    # consumer's domain data — any shape
    decisions: list[AgentDecision] = []
    blocked: bool = False
    blocked_reason: str | None = None
    human_notes: list[str] = []
    telemetry: TelemetryData = ...   # auto-filled by framework
    mode: str = "plan"               # "plan" or "execute"
```

### 2. WorkflowGraph YAML schema
```yaml
name: security_remediation

modes:
  plan:
    stop_before: [branch_created]
    output: plan_document
  execute:
    output: pull_request
    requires_human_gates: [reviewed]

stages:
  - created
  - triaged
  - resolved
  - analyzed
  - planned
  - branch_created
  - coded
  - reviewed
  - documented
  - delivered
  - closed

transitions:
  - {from: created,   on: proceed, to: triaged}
  - {from: triaged,   on: proceed, to: resolved}
  - {from: "*",       on: block,   to: blocked_human_required}

parallel_groups:
  - trigger: coded
    agents: [security_gatekeeper, reviewer]
    merge: all_must_pass

group_chats:
  - name: code_fix_panel
    trigger_stage: coded
    participants:
      - {role: architect,   agent: ArchitectAgent}
      - {role: coder,       agent: CodeAgent}
      - {role: security,    agent: SecurityAgent}
      - {role: adversarial, agent: AdversarialAgent}
      - {role: qa,          agent: QAAgent}
      - {role: reviewer,    agent: ReviewerAgent}
    moderator: reviewer
    consensus_required: [security, reviewer]
    max_rounds: 5

human_gates:
  - reviewed

filters:
  - {field: payload.severity,  reject_if_in: [low, info]}
  - {field: payload.repo_name, reject_if_null: true}
  - {check: existing_run_open, action: suppress}

routes:
  - {match: {payload.source: [snyk]}, graph: security_remediation.yaml}
  - {match: {payload.type: ["*"]},    graph: escalate_human.yaml}
```

### 3. Three Agent Types
```python
# Type 1 — LLM reasoning (existing BaseAgent, enhanced)
class BaseAgent(IAgent):
    # confidence gating, multi-round enrichment
    # token + latency tracking built-in

# Type 2 — Functional (new — no LLM)
class FunctionalAgent(IAgent):
    # pure logic / side-effects
    # Git, Notify, Feedback, Delivery

# Type 3 — Group Chat Participant (new)
class GroupChatAgent(BaseAgent):
    # receives full chat thread history in prompt
    # responds to other agents' reasoning
    # moderator role: decides consensus
```

### 4. Three Execution Runners
```python
class SequentialRunner:
    async def run(self, agent, context) -> AgentDecision

class ParallelRunner:
    async def run(self, agents: list, context) -> list[AgentDecision]
    # asyncio.gather, merge_strategy: all_must_pass | majority_vote | first_pass

class GroupChatRunner:
    async def run(self, participants, moderator, context) -> AgentDecision
    # rounds until consensus or max_rounds
    # full thread appended to context.decisions (append-only audit trail)
```

### 5. Filter + Router Engine
```python
class FilterEngine:
    # reject_if_in, reject_if_null, reject_if_matches, deduplication
    # runs before first agent — zero LLM cost for obvious rejects
    def evaluate(self, context: WorkflowContext, rules: list) -> FilterResult

class RouterEngine:
    # payload field matching → workflow graph selection
    def route(self, context: WorkflowContext, rules: list) -> str
```

### 6. Integration Extension Pattern
```python
# Use as-is
from conductor_integrations.sources import SnykIngestClient
client = SnykIngestClient(api_token=os.getenv("SNYK_TOKEN"))

# Extend for custom behavior
from conductor_integrations.sources import SnykIngestClient
class AcmeSnykClient(SnykIngestClient):
    async def fetch_new_findings(self, since_cursor=None):
        findings = await super().fetch_new_findings(since_cursor)
        return [self._remap_severity(f) for f in findings]

# Build from scratch
from conductor_core.interfaces import IIngestClient
class SalesforceIngestClient(IIngestClient):
    async def fetch_new_findings(self, since_cursor=None): ...
    async def get_current_cursor(self) -> str | None: ...
```

### 7. CLI Scaffolding
```bash
# Install
pip install conductor-cli

# Scaffold new project (replaces project name everywhere)
conductor new my-security-bot

# Scaffold from template
conductor new my-security-bot --template security-remediation
conductor new my-hr-bot       --template hr-workflow
conductor new my-ops-bot      --template incident-response

# List available templates
conductor templates
```

---

## What Aspen-Sentinel Keeps (Unchanged)

| Component | Status | Notes |
|---|---|---|
| All agent prompts (`.md` files) | ✅ Unchanged | Domain logic stays in consumer |
| `filters.yaml` | ✅ Unchanged | Moved to sentinel/config/ |
| `routes.yaml` | ✅ Unchanged | Moved to sentinel/config/ |
| `repo_registry.yaml` | ✅ Unchanged | Sentinel-specific |
| `ingest_filters.yaml` | ✅ Unchanged | Sentinel-specific |
| Git rules YAML | ✅ Unchanged | Sentinel-specific |
| `DefectRecord`, `WorkItem` schemas | ✅ Unchanged | Move into `payload: dict` |
| Plan mode / Execute mode behavior | ✅ Preserved | Becomes `mode:` in YAML |
| Regression guard | ✅ Preserved | Stays in CodeAgent logic |
| Confidence gating | ✅ Preserved | Stays in BaseAgent |
| Human escalation | ✅ Preserved | `human_gates:` in YAML |
| Append-only reasoning chain | ✅ Preserved | `context.decisions` |

---

## What Changes

| Component | Change |
|---|---|
| `PipelineContext` | → `WorkflowContext` with generic `payload: dict` |
| `pipeline.py` | → `WorkflowOrchestrator` with agent registry dict |
| `stages.py` | → `sentinel/workflow.yaml` stages section |
| `transitions.py` | → `sentinel/workflow.yaml` transitions section |
| `providers.py` | → cleaner `main.py` wiring |
| `GitAgent` | → extends `FunctionalAgent` |
| `FeedbackAgent` | → extends `FunctionalAgent` |
| `NotifyAgent` | → extends `FunctionalAgent` |
| `DeliveryAgent` | → extends `FunctionalAgent` |
| Ingest clients (Snyk/Sonar/ADO/BlackDuck) | → extend `conductor-integrations` base clients |
| SecurityAgent (post-code) | → different LLM injected (adversarial split) |
| Review loop | → `ParallelRunner` for Security + Reviewer |
| `run_live()` findings loop | → `ParallelRunner` with semaphore (max 5 concurrent) |
| Token estimate (`len//4`) | → actual token tracking via `TelemetryData` |

---

## Repository Layout

```
conductor/                          ← monorepo root
  conductor-core/                   ← Layer 1: orchestration engine
  conductor-integrations/           ← Layer 2: ADO, Snyk, Sonar, BlackDuck, Git, Notify
  conductor-cli/                    ← Layer 3: scaffolding CLI
  samples/                          ← real code with baked-in issues (for mock scenarios)
  mocks/                            ← pre-baked JSON scan results pointing at samples/
  consumer-showcase/                ← full end-to-end demo (Aspen-Sentinel pattern)
  scripts/                          ← setup, run, and test automation
  docs/                             ← ADRs, system design, consumer guide
  README.md                         ← getting started — points to each package
  Makefile                          ← single entry point for all developer tasks
```

---

## Configuration & Environment

### Design Principle
> **No agent, runner, or client reads `os.environ` directly. All config flows through a typed settings module.**
> This is already true in Aspen-Sentinel (`settings.py`) — the framework preserves and formalizes it.

---

### conductor-core: `ConductorSettings`
The framework ships a base settings class. Consumer extends it to add their own vars.

```python
# conductor_core/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class ConductorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_", env_file=".env", extra="ignore")

    # Provider mode
    provider_mode: str = "mock"           # CONDUCTOR_PROVIDER_MODE=mock|live

    # LLM
    llm_model: str = "gpt-4o"            # CONDUCTOR_LLM_MODEL
    max_llm_retries: int = 3             # CONDUCTOR_MAX_LLM_RETRIES

    # Agent behavior
    confidence_threshold: float = 0.80   # CONDUCTOR_CONFIDENCE_THRESHOLD
    max_enrichment_rounds: int = 3       # CONDUCTOR_MAX_ENRICHMENT_ROUNDS

    # Execution gate (plan vs execute)
    code_execution_enabled: bool = False # CONDUCTOR_CODE_EXECUTION_ENABLED

    # Observability
    langsmith_api_key: str | None = None # CONDUCTOR_LANGSMITH_API_KEY
    log_level: str = "INFO"              # CONDUCTOR_LOG_LEVEL
    log_json: bool = True                # CONDUCTOR_LOG_JSON
    log_file: str | None = None          # CONDUCTOR_LOG_FILE

    # Workspace (for git clone/checkout in execute mode)
    workspace_dir: str = "~/conductor-workspace"  # CONDUCTOR_WORKSPACE_DIR

settings = ConductorSettings()
```

### consumer-showcase: `SentinelSettings`
Consumer extends with domain-specific vars:
```python
# consumer_showcase/config/settings.py
from conductor_core.config.settings import ConductorSettings
from pydantic_settings import SettingsConfigDict

class SentinelSettings(ConductorSettings):
    model_config = SettingsConfigDict(env_prefix="SENTINEL_", env_file=".env", extra="ignore")

    # Scanner tokens (only needed in live mode)
    snyk_token: str | None = None           # SENTINEL_SNYK_TOKEN
    sonar_token: str | None = None          # SENTINEL_SONAR_TOKEN
    blackduck_token: str | None = None      # SENTINEL_BLACKDUCK_TOKEN
    ado_pat: str | None = None              # SENTINEL_ADO_PAT
    ado_org: str | None = None              # SENTINEL_ADO_ORG
    ado_project: str | None = None          # SENTINEL_ADO_PROJECT

    # GitHub LLM auth (required)
    github_token: str | None = None         # SENTINEL_GITHUB_TOKEN (or GITHUB_TOKEN)

    # Safety limits
    ingest_max_items: int = 10              # SENTINEL_INGEST_MAX_ITEMS
    ingest_min_severity: str = "HIGH"       # SENTINEL_INGEST_MIN_SEVERITY

    # Paths
    repo_registry_path: str = "config/repo_registry.yaml"
    workspace_dir: str = "~/sentinel-workspace"

    # Allowed orgs
    allowed_orgs: list[str] = ["github.com/myorg"]

settings = SentinelSettings()
```

---

### Config Loading — How it works
```
.env file (never committed)
    ↓
pydantic-settings (type-coerces, validates, applies defaults)
    ↓
settings singleton (imported once at startup)
    ↓
All agents, runners, clients consume settings.X (never os.getenv)
```

- **`pydantic-settings`** handles `.env` loading, type coercion, and validation — replaces raw `dotenv` + manual `os.getenv`
- **Default = safe for mock mode** — new clone runs immediately, nothing breaks without tokens
- **Consumer extends** `ConductorSettings` — they add vars, don't fork the base class
- **`extra="ignore"`** — unknown env vars silently ignored (no crash on unrelated system vars)

---

### `.env.example` (shipped with every project)
```bash
# =============================================================================
# Conductor — Environment Configuration
# Copy to .env and fill in required values
# =============================================================================

# --- LLM (required — we call real LLM) ---
GITHUB_TOKEN=                         # GitHub Copilot SDK token

# --- Provider mode ---
CONDUCTOR_PROVIDER_MODE=mock          # mock (default) | live

# --- LLM behavior ---
CONDUCTOR_LLM_MODEL=gpt-4o
CONDUCTOR_MAX_LLM_RETRIES=3
CONDUCTOR_CONFIDENCE_THRESHOLD=0.80
CONDUCTOR_MAX_ENRICHMENT_ROUNDS=3

# --- Execution gate ---
CONDUCTOR_CODE_EXECUTION_ENABLED=false   # false = plan mode only (safe default)

# --- Logging ---
CONDUCTOR_LOG_LEVEL=INFO
CONDUCTOR_LOG_JSON=false              # false = colored console output for dev
CONDUCTOR_LOG_FILE=                   # optional: logs/conductor.log

# --- Workspace ---
CONDUCTOR_WORKSPACE_DIR=~/conductor-workspace

# --- Demo scenario (consumer-showcase only) ---
DEMO_SCENARIO=snyk                    # snyk | sonar | blackduck | ado-defect | ado-story

# =============================================================================
# Scanner tokens — only needed when CONDUCTOR_PROVIDER_MODE=live
# =============================================================================
# SENTINEL_SNYK_TOKEN=
# SENTINEL_SONAR_TOKEN=
# SENTINEL_BLACKDUCK_TOKEN=
# SENTINEL_ADO_PAT=
# SENTINEL_ADO_ORG=
# SENTINEL_ADO_PROJECT=

# --- Observability (optional) ---
# CONDUCTOR_LANGSMITH_API_KEY=
```

---

### Structured Logging
Migrated from Aspen-Sentinel's `logging_config.py` (structlog) — promoted to `conductor-core`.

```python
# conductor_core/config/logging_config.py
# Identical to aspen_sentinel/config/logging_config.py — structlog JSON/console
# configure_logging() called once in main.py, never in agents

from conductor_core.config.logging_config import configure_logging, get_logger

# In any agent or client:
logger = get_logger(__name__)
logger.info("agent_started", agent="triage", run_id=ctx.run_id)
```

Log output in dev (JSON=false):
```
INFO  [triage]  agent_started  run_id=SNK-001
INFO  [triage]  llm_called     model=gpt-4o  tokens=847  latency_ms=1240
INFO  [mock_git]  git_checkout  branch=fix/snk-001-requests-cve  [MOCK]
```

Log output in prod (JSON=true):
```json
{"level": "info", "logger": "triage", "event": "llm_called", "model": "gpt-4o", "tokens": 847, "run_id": "SNK-001", "timestamp": "2026-05-30T20:55:08Z"}
```

---

### Config Tests
```
conductor-core/tests/unit/
  test_settings.py          # defaults correct, env override works, type coercion
  test_logging_config.py    # configure_logging sets correct level, JSON vs console

consumer-showcase/tests/unit/
  test_sentinel_settings.py # SentinelSettings extends correctly, mock mode default
```

Example:
```python
# test_settings.py
def test_defaults_to_mock_mode(monkeypatch):
    monkeypatch.delenv("CONDUCTOR_PROVIDER_MODE", raising=False)
    s = ConductorSettings()
    assert s.provider_mode == "mock"

def test_code_execution_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CONDUCTOR_CODE_EXECUTION_ENABLED", raising=False)
    s = ConductorSettings()
    assert s.code_execution_enabled is False

def test_env_override(monkeypatch):
    monkeypatch.setenv("CONDUCTOR_LOG_LEVEL", "DEBUG")
    s = ConductorSettings()
    assert s.log_level == "DEBUG"
```

---

## Automation Scripts

> **Rule: No developer types more than one command to get running.**

### `Makefile` — single entry point
```makefile
# One-time setup (creates venv, installs all packages in dev mode)
make setup

# Run all tests
make test

# Run only unit tests (fast — no LLM calls)
make test-unit

# Run integration tests (requires GITHUB_TOKEN)
make test-integration

# Run the full consumer-showcase demo (mock mode — no scanner tokens)
make demo

# Run the showcase for a specific scenario
make demo-snyk
make demo-sonar
make demo-blackduck
make demo-ado-defect
make demo-ado-story

# Lint + format
make lint

# Clean generated artifacts
make clean
```

### `scripts/setup.sh` — environment bootstrap
```bash
#!/usr/bin/env bash
# Creates .venv, installs all packages in editable mode, copies .env.example
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e conductor-core[dev]
pip install -e conductor-integrations[dev]
pip install -e conductor-cli[dev]
pip install -e consumer-showcase[dev]
cp -n .env.example .env || true
echo "✅ Setup complete. Edit .env to add GITHUB_TOKEN, then: make demo"
```

### `scripts/run_demo.sh` — run a scenario end-to-end
```bash
#!/usr/bin/env bash
# Usage: ./scripts/run_demo.sh [snyk|sonar|blackduck|ado-defect|ado-story]
SCENARIO=${1:-snyk}
source .venv/bin/activate
cd consumer-showcase
CONDUCTOR_PROVIDER_MODE=mock DEMO_SCENARIO=$SCENARIO python main.py
```

### `scripts/run_tests.sh` — run full test suite
```bash
#!/usr/bin/env bash
source .venv/bin/activate
pytest conductor-core/tests       -v --tb=short
pytest conductor-integrations/tests -v --tb=short
pytest consumer-showcase/tests    -v --tb=short
```

---

## Test Strategy

### Testing Layers
| Layer | Test Type | LLM calls? | What it proves |
|---|---|---|---|
| `conductor-core` | Unit | ❌ No | Interfaces, FilterEngine, RouterEngine, runners, YAML loader |
| `conductor-integrations` | Unit | ❌ No | Mock clients return correct schemas, extension points work |
| `consumer-showcase` | Integration | ✅ Yes (real LLM) | Full pipeline runs end-to-end on real code problems |
| `consumer-showcase` | Scenario test | ✅ Yes | Each of the 5 mock scenarios completes with `proceed` decision |

### Test File Layout Per Package
```
conductor-core/
  tests/
    unit/
      test_workflow_context.py      # WorkflowContext creation, payload access
      test_workflow_graph.py        # YAML loading, validation, bad schema errors
      test_filter_engine.py         # reject_if_null, reject_if_in, regex, dedup rules
      test_router_engine.py         # route matching, fallback, no-match behavior
      test_sequential_runner.py     # agent called, decision returned, context updated
      test_parallel_runner.py       # asyncio.gather, merge strategies
      test_group_chat_runner.py     # rounds, consensus, max_rounds bailout
      test_telemetry.py             # token tracking, latency, cost calculation
    conftest.py                     # shared fixtures: WorkflowContext, FakeAgent

conductor-integrations/
  tests/
    unit/
      test_mock_snyk_client.py      # reads mocks/snyk_findings.json → DefectRecord list
      test_mock_sonar_client.py     # reads mocks/sonar_findings.json → DefectRecord list
      test_mock_blackduck_client.py # reads mocks/blackduck_findings.json → DefectRecord list
      test_mock_ado_client.py       # reads ado_defect.json + ado_user_story.json
      test_mock_git_agent.py        # git commands logged, pr_url set in context
      test_filter_engine_rules.py   # severity filter, dedup filter, regex filter
    conftest.py

consumer-showcase/
  tests/
    integration/
      test_snyk_scenario.py         # full pipeline: mock Snyk → agents → mock git
      test_sonar_scenario.py        # full pipeline: mock Sonar → agents → mock git
      test_blackduck_scenario.py    # full pipeline: mock BlackDuck → agents → mock git
      test_ado_defect_scenario.py   # full pipeline: mock ADO defect → agents → mock git
      test_ado_story_scenario.py    # full pipeline: mock ADO user story → agents → mock git
    unit/
      test_sentinel_agents.py       # SentinelTriageAgent, SentinelPlanAgent prompts/decisions
      test_workflow_yaml.py         # sentinel/workflow.yaml parses and validates correctly
    conftest.py                     # real LLM setup, mock clients wired
```

### What Each Test Asserts

**Unit tests (no LLM):**
```python
# test_filter_engine.py — example
def test_rejects_low_severity():
    engine = FilterEngine()
    ctx = WorkflowContext(payload={"severity": "low"})
    rules = [{"type": "reject_if_in", "field": "severity", "values": ["low", "info"]}]
    result = engine.evaluate(ctx, rules)
    assert result.rejected is True
    assert result.reason == "severity is in reject list"

# test_parallel_runner.py — example
async def test_parallel_agents_run_concurrently():
    runner = ParallelRunner(merge_strategy="all_must_pass")
    results = await runner.run([SlowFakeAgent(0.1), SlowFakeAgent(0.1)], ctx)
    assert len(results) == 2  # both ran
    # total time < 0.15s not 0.20s (they ran in parallel, not serial)
```

**Integration tests (real LLM):**
```python
# test_snyk_scenario.py — example
async def test_snyk_cve_scenario_reaches_plan():
    """Full pipeline: mock Snyk CVE → real LLM reasoning → mock git."""
    orchestrator = build_showcase_orchestrator(scenario="snyk")
    result = await orchestrator.run(mode="plan")
    
    assert result.final_decision in ("proceed", "escalate")
    assert result.context.payload.get("fix_plan") is not None
    assert "requests" in result.context.payload["fix_plan"].lower()  # LLM found the dep
    assert len(result.context.decisions) >= 3  # triage + plan + review
```

---

## Implementation Phases (Build Order: Core → Integrations → Consumer)

> Each phase ends with: tests pass ✅ + README updated ✅ + `make test` green ✅

### Phase A — conductor-core (Foundation)
**Deliverables: working engine with full unit test coverage**

1. Create monorepo structure + `Makefile` + `scripts/setup.sh` + `scripts/run_tests.sh`
2. Create `conductor-core/` package with `pyproject.toml` (deps: `pydantic-settings`, `structlog`, `pyyaml`)
3. Define interfaces: `WorkflowContext`, `IAgent`, `FunctionalAgent`, `GroupChatAgent`, `IIngestClient`
4. Implement `ConductorSettings` (pydantic-settings, `CONDUCTOR_` prefix, typed defaults)
5. Migrate `logging_config.py` (structlog) from Aspen-Sentinel → conductor-core
6. Implement `WorkflowGraph` YAML loader + schema validator
7. Implement `FilterEngine` + `RouterEngine`
8. Implement `SequentialRunner`
9. Implement `TelemetryData` schema + token/latency tracking
10. Write all `conductor-core/tests/unit/` tests including `test_settings.py` + `test_logging_config.py`
11. Write `conductor-core/README.md` — interfaces, YAML schema reference, env vars table, quick-start
12. **Gate: `make test` green, 100% unit test pass**

### Phase B — conductor-integrations (Data + Infrastructure)
**Deliverables: all mock clients, mock git agent, sample code, mock JSON**

1. Create `conductor-integrations/` package with `pyproject.toml`
2. Create `samples/` — real Python files with baked-in issues per scanner type
3. Create `mocks/` — pre-baked JSON for all 5 scenarios
4. Implement `MockSnykClient`, `MockSonarClient`, `MockBlackDuckClient`, `MockADOClient`
5. Implement `MockGitAgent` (logs commands, sets pr_url in context)
6. Implement live stubs: `SnykIngestClient`, `SonarIngestClient`, `ADOIngestClient`, `BlackDuckIngestClient` (interface + docstring + NotImplementedError for live methods)
7. Implement `SlackNotifier`, `TeamsNotifier` stubs
8. Wire `CONDUCTOR_PROVIDER_MODE` factory: `mock` → mock clients, `live` → live clients
9. Write all `conductor-integrations/tests/unit/` tests
10. Write `conductor-integrations/README.md` — which clients exist, mock vs live, extension guide
11. **Gate: `make test` green, mock clients tested, sample code verified**

### Phase C — consumer-showcase (Full Demo)
**Deliverables: end-to-end working demo all 5 scenarios, real LLM, mock infra**

1. Create `consumer-showcase/` — Aspen-Sentinel pattern as consumer
2. Create `SentinelSettings` extending `ConductorSettings` (all scanner tokens + ADO config)
3. Write `.env.example` with all vars documented
2. Write `sentinel/workflow.yaml` — full pipeline translated from stages.py + transitions.py
3. Wire `WorkflowOrchestrator` with agent registry (replaces providers.py)
4. Implement consumer agents: `SentinelTriageAgent`, `SentinelPlanAgent`, `SentinelCodeAgent`, `SentinelReviewerAgent`, `SentinelSecurityAgent`
5. Wire mock clients via `CONDUCTOR_PROVIDER_MODE=mock`
6. Wire all 5 demo scenarios via `DEMO_SCENARIO` env var
7. Write `consumer-showcase/tests/unit/` + `tests/integration/` (all 5 scenarios)
8. Write `consumer-showcase/README.md` — how to run each scenario
9. Write root `README.md` — overview, quick-start (`make setup && make demo`), links to each package
10. **Gate: `make demo` runs all 5 scenarios, integration tests pass with real LLM**

### Phase D — Parallel Execution (Performance)
1. Implement `ParallelRunner` with `asyncio.gather` + merge strategies
2. Add `parallel_group:` to YAML schema + loader
3. Wire Security + Reviewer as parallel group in consumer `workflow.yaml`
4. Wire FeedbackAgent + NotifyAgent as parallel at delivery
5. Wire bounded parallel pool for multi-finding (semaphore=5)
6. Add `test_parallel_runner.py` unit tests (concurrency timing assertions)
7. **Gate: parallel tests pass, `make demo` still green**

### Phase E — Group Chat Panel
1. Implement `GroupChatRunner` (conversation loop, rounds, consensus)
2. Add `group_chat:` YAML schema
3. Add `code_fix_panel` in consumer `workflow.yaml` (Architect, Coder, Security, Adversarial, QA, Reviewer)
4. Add `AdversarialAgent`
5. Wire adversarial model split (different LLM for post-code SecurityAgent)
6. Add `test_group_chat_runner.py` unit tests
7. Add `test_ado_story_group_chat_scenario.py` integration test (group chat on feature implementation)
8. **Gate: group chat tests pass, 6-agent panel runs end-to-end**

### Phase F — Observability
1. Actual token counting in `BaseAgent._call_llm` (replace `len//4`)
2. Per-agent latency tracking
3. Confidence trend per campaign
4. Recode loop counter
5. Campaign cost report
6. LangSmith integration (optional — gated behind `LANGSMITH_API_KEY`)
7. Add `test_telemetry.py` assertions for tracking accuracy
8. **Gate: cost report prints correctly after `make demo`**

### Phase G — conductor-cli Scaffolding
1. Create `conductor-cli/` package with `pyproject.toml`
2. Implement `conductor new <name>` command (copies template, replaces project name everywhere)
3. Build starter templates: `security-remediation`, `incident-response`, `hr-workflow`
4. `conductor templates` — lists available templates
5. Template ships with `Makefile`, `scripts/`, `.env.example`, mock mode default
6. Test: scaffold a project, run `make setup && make demo` in the scaffolded project
7. Write `conductor-cli/README.md`
8. **Gate: `conductor new test-project && cd test-project && make setup && make demo` works**

### Phase H — ADR + Final Documentation
1. `docs/adr/ADR-005-conductor-extraction.md`
2. `docs/adr/ADR-006-langgraph-engine.md`
3. `docs/adr/ADR-007-group-chat-pattern.md`
4. `conductor-core/docs/CONSUMER_GUIDE.md` — how any team uses it
5. `conductor-cli/docs/TEMPLATES.md` — how to create new templates
6. Update root `README.md` with final architecture diagram
7. **Gate: `make demo` runs all 5 scenarios from a fresh clone with no existing venv**

---

## How Any Developer Uses It (End State)

```bash
# Day 1 — scaffold a new project
pip install conductor-cli
conductor new my-security-bot --template security-remediation

# Day 1 — run it immediately in mock mode
cd my-security-bot
pip install -r requirements.txt
python main.py
```

```python
# What they customize — their agents extend BaseAgent
class MyTriageAgent(BaseAgent):
    AGENT_NAME = "triage"
    def _get_prompt_variables(self, ctx, round_num):
        item = ctx.payload["item"]
        return {"title": item["title"], "severity": item["severity"]}

# Their workflow.yaml — declare the pipeline
# filters, routes, stages, transitions, parallel_groups, human_gates

# main.py — wire and run (generated by CLI, rarely edited)
orchestrator = WorkflowOrchestrator(
    agents={"triage": MyTriageAgent(llm), "reviewer": ReviewerAgent(llm)},
    graph=WorkflowGraph.from_yaml("workflow.yaml"),
)
result = await orchestrator.run(
    WorkflowContext(run_id="X-001", payload={"item": {...}}, mode="plan")
)
```

Gets for free:
- Confidence gating + human escalation
- Parallel execution + group chat
- Filter engine + router engine
- Observability (tokens, latency, cost)
- Append-only audit trail
- Plan mode + execute mode
- Pre-built integrations (Snyk, ADO, Jira, GitHub, Slack, Teams)

---

## Mock Strategy

### The Principle
> **Real LLM reasoning on real code problems. Mock infrastructure, not intelligence.**

| Component | Mode | Rationale |
|---|---|---|
| LLM calls (Copilot SDK / OpenAI) | ✅ **Real** | Agents must reason against actual code issues |
| ADO work items (user stories + defects) | 🔲 **Mock** | Pre-baked JSON — no ADO token needed |
| Snyk findings | 🔲 **Mock** | Pre-baked scan results pointing at sample code |
| Sonar findings | 🔲 **Mock** | Pre-baked quality + SAST issues pointing at sample code |
| BlackDuck findings | 🔲 **Mock** | Pre-baked OSS license + vulnerability findings |
| Git clone / checkout / commit / branch / PR | 🔲 **Mock** | Log the git commands, never execute them |
| Sample code | ✅ **Real code with baked-in issues** | Agents analyze and fix actual broken code |

---

### Sample Code Repository (`samples/`)
Create a folder `samples/` containing real code files with deliberate, known vulnerabilities and issues. Each file is the target for a specific scanner mock.

```
samples/
  snyk/
    requirements_vulnerable.txt    # known CVE in requests==2.18.0, flask==0.12
    app_with_dep_vuln.py           # uses the vulnerable deps
  sonar/
    auth_handler.py                # SQL injection, hardcoded credential, dead code
    data_processor.py              # null dereference, unchecked input
  blackduck/
    package_copyleft.py            # imports GPL-licensed library into proprietary code
    oss_outdated.txt               # dependency manifest with EOL packages
  ado/
    feature_stub.py                # incomplete feature — matches ADO user story
    buggy_calculator.py            # off-by-one error — matches ADO defect
```

These files are **the ground truth** — they have the real problems the mock ingest data claims exist.

---

### Mock Ingest Data (`mocks/`)
```
mocks/
  snyk_findings.json          # CVE-2023-XXXX in requests, points to samples/snyk/
  sonar_findings.json         # SQL injection at auth_handler.py:47, hardcoded cred at :23
  blackduck_findings.json     # GPL violation in package_copyleft.py
  ado_defect.json             # Bug: calculator returns wrong result — points to buggy_calculator.py
  ado_user_story.json         # Feature: add user profile endpoint — points to feature_stub.py
```

Each mock file matches the real shape of the actual API response so mock clients are drop-in replacements.

---

### Mock Client Pattern
```python
# conductor-integrations provides this base pattern
class MockSnykIngestClient(IIngestClient):
    """Reads from mocks/snyk_findings.json instead of calling Snyk API."""
    def __init__(self, mock_file: str = "mocks/snyk_findings.json"):
        self._mock_file = mock_file

    async def fetch_new_findings(self, since_cursor=None) -> list[DefectRecord]:
        with open(self._mock_file) as f:
            raw = json.load(f)
        return [DefectRecord.from_snyk(item) for item in raw["vulnerabilities"]]

# Same pattern for MockSonarClient, MockBlackDuckClient, MockADOClient
```

---

### Mock Git Agent Pattern
```python
class MockGitAgent(FunctionalAgent):
    """Logs all git operations instead of executing them."""
    AGENT_NAME = "git"

    async def run(self, context: WorkflowContext) -> AgentDecision:
        item = context.payload["work_item"]
        branch = f"fix/{item['id']}-{item['slug']}"
        
        logger.info(f"[MOCK GIT] git checkout -b {branch}")
        logger.info(f"[MOCK GIT] git add -A")
        logger.info(f"[MOCK GIT] git commit -m 'fix: {item['title'][:60]}'")
        logger.info(f"[MOCK GIT] git push origin {branch}")
        logger.info(f"[MOCK GIT] gh pr create --title '{item['title']}'")
        
        context.payload["branch"] = branch
        context.payload["pr_url"] = f"https://mock-git/pr/{item['id']}"
        
        return AgentDecision(recommendation="proceed", confidence=1.0,
                             reasoning="Mock git operations logged successfully")
```

---

### Running the Demo (No Tokens Required)

```bash
# Scaffold from CLI
conductor new my-security-bot --template security-remediation

# Run immediately — mock mode is default for new projects
cd my-security-bot
pip install -r requirements.txt

# Set only the LLM token (required — we call real LLM)
export GITHUB_TOKEN=ghp_your_token    # or OPENAI_API_KEY

# Run — mock ingest, real LLM reasoning, mock git
python main.py

# What you see:
# [INGEST]  Loaded 3 findings from mocks/snyk_findings.json
# [TRIAGE]  Reasoning: CVE-2023-XXXX in requests is high severity... (real LLM)
# [PLAN]    Fix: upgrade requests to 2.31.0... (real LLM, analyzing sample code)
# [MOCK GIT] git checkout -b fix/snyk-001-requests-cve
# [MOCK GIT] git commit -m 'fix: upgrade requests to 2.31.0'
```

---

### Mock Coverage Matrix

| Scanner | Mock File | Sample Code | ADO Work Item Type |
|---|---|---|---|
| Snyk | `mocks/snyk_findings.json` | `samples/snyk/` | Defect (CVE) |
| Sonar | `mocks/sonar_findings.json` | `samples/sonar/` | Defect (SAST) |
| BlackDuck | `mocks/blackduck_findings.json` | `samples/blackduck/` | Defect (License) |
| ADO Defect | `mocks/ado_defect.json` | `samples/ado/buggy_calculator.py` | Defect |
| ADO User Story | `mocks/ado_user_story.json` | `samples/ado/feature_stub.py` | Feature |

All 5 scenarios run end-to-end with a single `python main.py` command.

---

### Environment Variables
```bash
# .env.example (shipped in every template)
# --- LLM (required — we call real LLM) ---
GITHUB_TOKEN=                     # GitHub Copilot SDK
# OPENAI_API_KEY=                 # or OpenAI

# --- Provider mode (default: mock) ---
CONDUCTOR_PROVIDER_MODE=mock      # mock | live

# --- Only needed in live mode ---
# SNYK_TOKEN=
# SONAR_TOKEN=
# BLACKDUCK_TOKEN=
# ADO_PAT=
# ADO_ORG=
# ADO_PROJECT=
```

New projects scaffold with `CONDUCTOR_PROVIDER_MODE=mock` so they work immediately.
Switch to `live` when tokens are available.

---

## Success Criteria

### Automation (Zero Manual Steps)
- [ ] `make setup` creates venv + installs all packages from a fresh clone
- [ ] `make demo` runs all 5 scenarios end-to-end (mock infra, real LLM)
- [ ] `make test` runs all unit + integration tests with a single command
- [ ] `make test-unit` runs with no LLM token required (pure logic tests)
- [ ] `.env.example` ships with every project — copy, set GITHUB_TOKEN, run

### Tests
- [ ] `conductor-core` has 100% unit test coverage on all interfaces and runners
- [ ] `conductor-integrations` unit tests prove mock clients return correct schemas
- [ ] `consumer-showcase` has integration test for each of the 5 scenarios
- [ ] `make test` is green after every phase before moving to the next

### Functionality
- [ ] `conductor new my-project` scaffolds a working project in < 1 minute
- [ ] Aspen-Sentinel behavior 100% identical after migration (all tests pass)
- [ ] `PipelineContext` is gone — replaced by `WorkflowContext`
- [ ] `pipeline.py` handler_map is gone — replaced by YAML + runners
- [ ] A second team onboards with only agents + YAML (no framework changes)
- [ ] Post-code Security + Reviewer run in parallel
- [ ] Token cost tracked per agent per campaign
- [ ] Group chat panel works with 4+ participants
- [ ] Plan mode and execute mode work identically to today
- [ ] Snyk, ADO, Sonar, BlackDuck clients live in `conductor-integrations`

### Documentation
- [ ] Every package has its own `README.md`
- [ ] Root `README.md` is the single entry point (`make setup && make demo`)
- [ ] `conductor-core/docs/CONSUMER_GUIDE.md` explains how any team adopts it
- [ ] New project template exists for security-remediation, incident-response, hr-workflow

### Mock Strategy
- [ ] `python main.py` (or `make demo`) runs with zero API tokens except LLM
- [ ] All 5 mock scenarios pass: Snyk CVE, Sonar SAST, BlackDuck license, ADO defect, ADO user story
- [ ] Mock git agent logs all git commands (checkout, commit, push, PR) without executing
- [ ] Sample code in `samples/` has real, analyzable issues for each scanner type
- [ ] Switching to live mode requires only setting scanner tokens in `.env` — no code change
