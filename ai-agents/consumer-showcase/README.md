# consumer-showcase

**Production-grade reference implementation** demonstrating a full security-remediation pipeline with Conductor Framework. This is Layer 3 — a fully wired, runnable application showcasing all 5 security layers in action.

**What it demonstrates:**
- ✅ Multi-agent orchestration (triage → analysis → remediation → planning)
- ✅ 5-layer security stack (validation, mTLS, secret scrubbing, output validation, supply chain)
- ✅ Token scrubbing to prevent secret leaks
- ✅ Output validation with @validated_agent
- ✅ Supply chain verification with DependencyVerifier
- ✅ A2A HTTP server for external framework integration
- ✅ mTLS for agent-to-agent communication

**Handles findings from:** Snyk, SonarQube, Black Duck, and Azure DevOps through intelligent routing and filtering.

---

## ✨ Phase 4 Features (NEW)

### conductor.json - Project Manifest
Declares agents, integrations, and security settings in one place:
```json
{
  "name": "security-remediation",
  "agents": [
    {"name": "snyk_triage", "capabilities": ["triage"]},
    {"name": "code_analyzer", "capabilities": ["analyze"]},
    {"name": "remediation_planner", "capabilities": ["plan"]}
  ],
  "integrations": ["snyk", "github", "sonarqube"],
  "settings": {
    "token_scrubber": true,
    "output_validator": true,
    "dependency_check": true,
    "a2a_server": {"enabled": false, "port": 8001, "use_mtls": true}
  }
}
```

### A2A HTTP Server - External Integration
Expose agents as HTTP endpoints for external frameworks:
```bash
# Start HTTP server with mTLS
python main.py --a2a-server --port 8001 --mtls

# Or standalone
python a2a_server.py --port 8001 --mtls

# Endpoints available:
# GET  /health          — Health check
# GET  /a2a/info        — Server info
# GET  /a2a/agents      — List agents
# POST /a2a/call        — Call agent
# GET  /a2a/stats       — Server stats
```

### Security Features (All Active)

**Layer 1: Input Validation (@validated_agent)**
- All agent outputs validated against Pydantic schemas
- Prevents invalid data from flowing between agents

**Layer 2: Execution Security (mTLS)**
- Agent-to-agent communication encrypted
- Client certificates verify agent identity
- Auto-generated CA and per-agent certificates

**Layer 3: Secret Management (TokenScrubber)**
- GitHub tokens, AWS keys, API keys automatically redacted from logs
- 10+ secret patterns (GitHub, AWS, JWT, Snyk, database, etc.)
- Zero secrets in logs guarantee

**Layer 4: Output Validation (SchemaCatalog)**
- Agent outputs validated against schemas
- Invalid outputs fail fast with clear errors

**Layer 5: Supply Chain (DependencyVerifier)**
- Dependencies checked for known vulnerabilities on startup
- SHA256 hashing detects compromised packages
- Pre-flight verification prevents surprises

---

## Install

```bash
pip install -e .           # installs consumer-showcase + all dependencies
```

Depends on `conductor-core` (includes all security layers).

---

## Quick Start

### 1. Run a Scenario (with security features active)

```bash
cd /path/to/consumer-showcase

# TokenScrubber will redact secrets from logs
# DependencyVerifier will check dependencies
python main.py --scenario snyk --store /tmp/runs.db
```

### 2. Try All Scenarios

```bash
python main.py --all --store /tmp/runs.db
```

### 3. Start as A2A HTTP Server (for external integrations)

```bash
# With mTLS (recommended for production)
python main.py --a2a-server --port 8001 --mtls

# External frameworks can now call agents via HTTP
curl -X POST http://localhost:8001/a2a/call \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "snyk_triage", "context": {"run_id": "demo"}, "kwargs": {}}'
```

### 4. Check Security Features

```bash
# See what's in conductor.json
cat conductor.json

# Verify TokenScrubber (try logging a secret)
python -c "
import logging
from conductor_core.secrets.token_scrubber import ScrubFilter

logging.basicConfig(level=logging.INFO)
logging.getLogger().addFilter(ScrubFilter())
log = logging.getLogger()
log.info('GitHub token: gh_abc123def456789')  # ✅ Output: 'GitHub token: <REDACTED>'
"

# Verify DependencyVerifier
python -c "
from conductor_core.supply_chain.dependencies import DependencyVerifier
import asyncio

async def check():
    verifier = DependencyVerifier()
    result = await verifier.verify('requirements.txt')
    print('✅ Dependencies verified' if not result['has_risks'] else '⚠️ Risks found')

asyncio.run(check())
"
```

---

## ⚠️ Important: conductor.json Must Match All Workflow Agents

Each workflow.yaml file can use different agents, but **all agents must be declared in conductor.json FIRST**.

### Current Setup:

**conductor.json declares 4 agents:**
```json
"agents": [
  {"name": "snyk_triage", ...},
  {"name": "code_analyzer", ...},
  {"name": "remediation_planner", ...},
  {"name": "github_reporter", ...}
]
```

**Available workflows:**
- `workflow_security.yaml` — uses 3 agents (triage → analysis → plan) ✅
- `workflow_ado.yaml` — uses 3 agents (triage → resolve → plan) ✅
- `workflow_execute.yaml` — uses 9+ agents (triage → code → review → git → notify → feedback) ⚠️
- `workflow_adversarial.yaml` — uses agents with model override ✅
- `workflow.yaml` — default workflow ✅

### If You See This Error:

```
❌ agent_not_found
   stage: "code"
   agent_key: "code_agent"
   registered: ["snyk_triage", "code_analyzer", "remediation_planner", "github_reporter"]

❌ context.mark_blocked("No agent registered for: 'code_agent'")
```

**Fix:** Add the missing agent to conductor.json:

```json
{
  "agents": [
    {"name": "snyk_triage", ...},
    {"name": "code_analyzer", ...},
    {"name": "remediation_planner", ...},
    {"name": "code_agent", ...},           // ← ADD THIS
    {"name": "review_agent", ...},         // ← ADD THIS
    {"name": "github_reporter", ...}
  ]
}
```

### Validation Checklist:

Before running a workflow, verify all agents exist:

```bash
# Extract agents from workflow
grep "agent:" config/workflow_execute.yaml | awk '{print $NF}' | sort -u

# Extract agents from conductor.json
jq -r '.agents[].name' conductor.json | sort -u

# They should match — if not, update conductor.json!
```

---

## Demo Scenarios

Each scenario uses a real code file in `samples/` and a pre-baked mock JSON in `mocks/`. The `StubLLM` returns realistic per-scenario reasoning without any API calls.

| Scenario | `--scenario` | Source file | Issue |
|---|---|---|---|
| Snyk CVE | `snyk` | `samples/snyk/requirements_vulnerable.txt` | CVE-2023-32681 in `requests 2.18.0` |
| SonarQube | `sonar` | `samples/sonar/auth_handler.py` | SQL injection + hardcoded credential |
| Black Duck | `blackduck` | `samples/blackduck/package_copyleft.py` | GPL-3.0 license violation |
| ADO Defect | `ado-defect` | `samples/ado/buggy_calculator.py` | Off-by-one + division-by-zero |
| ADO Story | `ado-story` | `samples/ado/feature_stub.py` | Unimplemented `paginate()` method |

### Security During Execution

When you run scenarios, all 5 security layers are active:

```bash
python main.py --scenario snyk

# What happens:
# 1. conductor.json loaded → Security settings read
# 2. TokenScrubber initialized → All logs will redact secrets
# 3. DependencyVerifier runs → Dependencies checked for vulnerabilities
# 4. Workflow selected → workflow_security.yaml loaded
# 5. Agents executed → @validated_agent validates all outputs
# 6. Results saved → SQLite store (encrypted in production)

# Output shows:
# ✅ TokenScrubber initialized - secrets will be redacted from logs
# 🔍 Running supply chain verification...
# ✅ Supply chain check passed
```

---

## Pipeline Architecture

```
main.py  →  WorkflowContext(run_id, payload)
                   │
                   ▼
         WorkflowOrchestrator
              │
    ┌─────────┴─────────┐
    ▼                   ▼
FilterEngine        RouterEngine
(reject info/       (snyk/sonar/blackduck → security_remediation
 null repos)         ado              → ado_remediation)
    │
    ▼
 Stage: triage          →  TriageAgent         (severity, risk, route)
    ▼
 Stage: security_analysis →  SecurityAnalystAgent (CVE/SAST analysis)
    ▼                        [skipped for ADO workflow]
 Stage: resolve          →  ResolverAgent      (fix strategy)
    ▼
 Stage: plan             →  PlannerAgent       (ordered steps + PR desc)
    ▼  [HALT in plan mode]
 Stage: code             →  CodeAgent          (diff/patch)
    ▼  [execute mode only]
 Stage: review           →  ReviewerAgent      (adversarial review, diff model)
    ▼
 Stage: scribe           →  ScribeAgent        (PR body, changelog)
    ▼
 Stage: git              →  GitAgent           (branch, commit, PR)
    ▼
 Stage: notify           →  NotifyAgent        (Slack/ADO comment)
    ▼
 Stage: feedback         →  FeedbackAgent      (capture reviewer feedback)
    ▼
 terminal
    │
    ▼
SQLiteResultStore.save_run(context)
  → runs table:      run_id, workflow, source, mode, blocked, tokens, cost
  → decisions table: agent, stage, round, confidence, model_used,
                     prompt_system, prompt_user, raw_llm_response,
                     reasoning, evidence, tokens, latency, cost
```

All 10 agents are imported from **`conductor-agents`** — this consumer is purely wiring.

---

## Module Map

```
consumer-showcase/                    ← PROJECT ROOT
├── main.py                           ← Orchestration entry point (run with --scenario or --a2a-server)
├── a2a_server.py ✨                 ← A2A HTTP server (NEW Phase 4)
├── conductor.json ✨                ← Project manifest (NEW Phase 4)
├── config/
│   ├── workflow_security.yaml        ← Snyk/Sonar/BlackDuck flow
│   ├── workflow_ado.yaml             ← Azure DevOps flow
│   ├── workflow_execute.yaml         ← Full pipeline
│   └── workflow_adversarial.yaml     ← Adversarial review demo
│
├── consumer_showcase/                ← PYTHON PACKAGE
│   ├── __init__.py
│   ├── config/
│   │   └── settings.py               ← Python configuration
│   ├── agents/                       ← Agent implementations
│   │   ├── __init__.py
│   │   ├── triage_agent.py
│   │   └── ... (other agents)
│   └── prompts/                      ← LLM prompts
│
└── tests/
    ├── unit/                         ← Unit tests
    └── integration/                  ← End-to-end tests
```

---

---

## Architecture - 5-Layer Security Stack

```
┌──────────────────────────────────────────────────────────────┐
│ External Framework (via HTTP)                                │
└─────────────────────┬──────────────────────────────────────┘
                      │ mTLS (encrypted)
┌─────────────────────▼──────────────────────────────────────┐
│ Layer 5: A2A HTTP Server (a2a_server.py)                   │
├────────────────────────────────────────────────────────────┤
│ /a2a/call → routes to orchestrator                          │
│ /a2a/agents → list available agents                         │
│ mTLS certificate verification                              │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ Layer 4: Supply Chain (DependencyVerifier)                  │
├────────────────────────────────────────────────────────────┤
│ SHA256 verification of dependencies                         │
│ CVE checking on startup                                     │
│ Blocks deployment if vulnerabilities found                  │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ Layer 3: Secret Management (TokenScrubber)                  │
├────────────────────────────────────────────────────────────┤
│ 10+ secret patterns redacted (GitHub, AWS, JWT, etc)        │
│ Applied globally to all logs                                │
│ Zero secrets in output guarantee                            │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ Layer 2: Execution Security (mTLS + @validated_agent)       │
├────────────────────────────────────────────────────────────┤
│ Agent-to-agent encryption                                   │
│ Pydantic schema validation on all outputs                   │
│ Agent identity verification via client certificates         │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│ Layer 1: Input Validation (Pydantic Schemas)                │
├────────────────────────────────────────────────────────────┤
│ All agent inputs validated before execution                 │
│ Rejects malformed data                                      │
│ Clear error messages on validation failure                  │
└────────────────────────────────────────────────────────────┘
```

---

## API Reference

All public APIs are documented in `/docs/API_REFERENCE.md`. Key classes:

### WorkflowOrchestrator
```python
from conductor_core.orchestration import WorkflowOrchestrator

orchestrator = WorkflowOrchestrator(workflow_path="config/workflow_security.yaml")
context = await orchestrator.run_scenario("snyk", store_path="/tmp/runs.db")

# Returns WorkflowContext with:
# - run_id: unique execution ID
# - findings: list of findings
# - recommendations: remediation steps
```

### @validated_agent
```python
from conductor_core.decorators import validated_agent
from pydantic import BaseModel

class TriageOutput(BaseModel):
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    cves: list[str]
    recommendation: str

@validated_agent(output_schema=TriageOutput)
async def my_agent(context: WorkflowContext, **kwargs) -> TriageOutput:
    return TriageOutput(severity="HIGH", cves=["CVE-2023-32681"], recommendation="Update package")
```

### TokenScrubber (Active on Startup)
```python
# Already active — all logs automatically have secrets redacted
# Patterns covered: GitHub tokens, AWS keys, API keys, JWT, Snyk keys, database passwords, etc.

# Example:
log.info("Connecting with token: gh_abc123def456789")
# Output: "Connecting with token: <REDACTED>"
```

### DependencyVerifier (Active on Startup)
```python
# Already runs pre-flight check on application startup
# Blocks deployment if vulnerabilities detected

# Manual verification:
from conductor_core.supply_chain.dependencies import DependencyVerifier

verifier = DependencyVerifier()
result = await verifier.verify("requirements.txt")
if result["has_risks"]:
    print(f"⚠️ Found {len(result['risks'])} vulnerabilities")
else:
    print("✅ All dependencies are safe")
```

---

## Security Configuration (conductor.json)

All security settings are controlled via `conductor.json`:

```json
{
  "settings": {
    "token_scrubber": true,           // ✅ Enable secret redaction
    "output_validator": true,         // ✅ Validate all agent outputs
    "dependency_check": true,         // ✅ Pre-flight vulnerability check
    "a2a_server": {
      "enabled": false,               // Change to true to start HTTP server
      "port": 8001,
      "use_mtls": true                // ✅ Enable mTLS for agent-to-agent
    }
  }
}
```

---

## Production Deployment

See `/docs/SECURITY_HARDENING.md` for complete guide covering:
- Pre-deployment security checklist
- mTLS certificate setup and rotation
- Secret management (environment variables, vaults)
- Monitoring and logging (OTEL traces)
- Incident response procedures
- Scaling recommendations

**Quick checklist:**
```bash
# 1. Verify all security layers active
python -c "from consumer_showcase.main import verify_security; verify_security()"

# 2. Run security tests
pytest tests/ -k security -v

# 3. Check dependencies
python -c "import conductor_core; print(conductor_core.__version__)"

# 4. Start with mTLS in production
python main.py --a2a-server --mtls --port 8001
```

---

Four configurations are included to showcase different pipeline shapes. Select via `--workflow`:

| YAML | Stages | Use case |
|---|---|---|
| `workflow_security.yaml` | triage → analysis → resolve → **plan** [HALT] | Review plan without applying code |
| `workflow_ado.yaml` | triage → resolve → **plan** [HALT] | ADO items — skip CVE analysis |
| `workflow_execute.yaml` | triage → analysis → resolve → plan → code → review → scribe → git → notify → feedback | Fully automated |
| `workflow_adversarial.yaml` | …plan → **review** (model=gpt-4-turbo) → scribe [HALT] | Per-stage model override demo |

```bash
python main.py --scenario snyk --workflow config/workflow_adversarial.yaml --store /tmp/runs.db
```

See [docs/workflow-yaml.md](../docs/workflow-yaml.md) for the full YAML reference.

---

## Agents

All 10 agents live in `conductor-agents` (Layer 2). This consumer just imports and wires them:

| Agent | Stage key | Role |
|---|---|---|
| `TriageAgent` | `triage` | Severity, risk, route decision |
| `SecurityAnalystAgent` | `security_analysis` | CVE scoring, CVSS, attack surface |
| `ResolverAgent` | `resolve` | Fix strategy mapping |
| `PlannerAgent` | `plan` | Ordered fix steps + PR description |
| `CodeAgent` | `code` | Produce diff/patch |
| `ReviewerAgent` | `review` | Adversarial review (different model) |
| `ScribeAgent` | `scribe` | PR body, changelog, ticket comment |
| `GitAgent` | `git` | Branch, commit, open PR |
| `NotifyAgent` | `notify` | Slack/Teams/ADO notification |
| `FeedbackAgent` | `feedback` | Capture reviewer feedback |

**To update an agent's prompts or behaviour:** edit the files in `conductor-agents/conductor_agents/agents/<name>/prompts/`. No Python changes needed. See [conductor-agents/README.md](../conductor-agents/README.md).

---

## Operational Scripts

Scripts have moved to **`conductor-cli`** — use the `conductor` command instead:

```bash
# List all runs (with workflow, source, tokens, cost)
conductor runs --store /tmp/runs.db

# Show fix plan
conductor plan SNYK-001-demo --store /tmp/runs.db

# Full reasoning trace (agent decisions, model used, confidence)
conductor trace SNYK-001-demo --store /tmp/runs.db

# Trace with prompts + raw LLM responses (full audit)
conductor trace SNYK-001-demo --store /tmp/runs.db --prompts --raw

# Everything (all runs + traces + plans)
conductor all --store /tmp/runs.db

# View structured logs
conductor logs --events
conductor logs --run SNYK-001-demo

# Delete a run
conductor clean SNYK-001-demo --store /tmp/runs.db
conductor clean --list --store /tmp/runs.db
```

See [conductor-cli/README.md](../conductor-cli/README.md) for full options reference.

---

## Persistence

Results are saved to SQLite automatically when `--store` is provided:

```bash
python main.py --all --store runs.db

# Query programmatically
import asyncio
from conductor_core.stores.sqlite_store import SQLiteResultStore

async def main():
    store = SQLiteResultStore("runs.db")
    runs = await store.list_runs(limit=10)
    for r in runs:
        print(r["run_id"], r["workflow"], r["total_tokens"], f"${r['estimated_cost_usd']:.4f}")

    # Get full reasoning trace with prompts + raw responses
    decisions = await store.get_decisions("SNYK-001-demo")
    for d in decisions:
        print(d["agent_name"], d["model_used"], d["recommendation"])
        print("  prompt:", d["prompt_user"][:80])
        print("  raw_response:", d["raw_llm_response"][:80])

asyncio.run(main())
```

Every decision stores: agent name, stage, round, confidence, model used, **system prompt verbatim**, **user prompt verbatim**, **raw LLM response verbatim**, reasoning bullets, tokens, latency, cost.

---

## Adding a Real LLM

Replace `StubLLM` with the Copilot provider:

```python
# main.py — swap this line:
llm = _build_stub_llm(scenario)

# with:
from conductor_core.providers.copilot import CopilotLLMProvider
llm = CopilotLLMProvider()           # reads GITHUB_TOKEN from env
```

Then set:
```bash
GITHUB_TOKEN=ghp_...                 # PAT with Copilot subscription
CONDUCTOR_PROVIDER_MODE=live
CONDUCTOR_LLM_MODEL=gpt-4o           # or gpt-4-turbo, o1-preview, etc.
CONDUCTOR_REVIEWER_MODEL=gpt-4-turbo # adversarial reviewer uses a different model
```

---

## Running Tests

```bash
cd consumer-showcase

# Unit tests (fast, no LLM)
pytest tests/unit -q

# Integration tests (end-to-end pipeline, still no real LLM)
pytest tests/integration -q

# All together
pytest tests/ -q     # 116 tests total across all packages
```

---

## Adapting for Your Domain

To use this as a starting point for your own consumer:

1. **Import agents** from `conductor-agents` — no need to copy or rewrite agent code
2. **Write** `config/workflow.yaml` — filters, routes, stages for your domain
3. **Update prompts** in `conductor-agents/conductor_agents/agents/<name>/prompts/` — no Python needed
4. **Replace** `StubLLM` with your real LLM provider
5. **Add** any custom agents if needed (extend `BaseAgent`, write prompt files)

See [docs/consumer-guide.md](../docs/consumer-guide.md) for a full step-by-step walkthrough.
