# conductor-integrations

**Pre-built mock clients** for common enterprise scanning and work-item tools. These are Layer 2 of the Conductor framework — domain-specific adapters that consumers can use out of the box, or extend with real API calls.

All clients ship as **mocks by default** (no tokens required), switchable to live mode via `CONDUCTOR_PROVIDER_MODE=live`.

---

## Install

```bash
pip install conductor-integrations    # from PyPI (future)
pip install -e .                      # editable local install
```

Depends on `conductor-core`.

---

## Included Integrations

### Security Scanners (Sources)

| Integration | Class | Mock data | Live API |
|---|---|---|---|
| **Snyk** | `SnykSourceAgent` | Pre-baked CVE fixtures | Snyk REST API |
| **SonarQube/Cloud** | `SonarSourceAgent` | SQL injection + credential | SonarCloud API |
| **Black Duck** | `BlackDuckSourceAgent` | GPL license violation | Black Duck API |
| **Azure DevOps** | `AdoSourceAgent` | Defect + story fixtures | ADO REST API |

### Git Operations

| Integration | Class | Mock behaviour | Live behaviour |
|---|---|---|---|
| **Mock Git** | `MockGitAgent` | Logs operations, returns success | — |
| **GitHub Git** | `GitHubGitAgent` | — | Branch / commit / PR via PyGithub |

### Notifications

| Integration | Class | Behaviour |
|---|---|---|
| **Mock Notifier** | `MockNotifyAgent` | Logs notification, no-op |

---

## Module Map

```
conductor_integrations/
├── models.py            # WorkItem dataclass (shared across all sources)
├── sources/
│   ├── snyk.py          # SnykSourceAgent + MockSnykClient
│   ├── sonar.py         # SonarSourceAgent + MockSonarClient
│   ├── blackduck.py     # BlackDuckSourceAgent + MockBlackDuckClient
│   └── ado.py           # AdoSourceAgent + MockAdoClient
├── git/
│   └── mock_git_agent.py   # MockGitAgent (IAgent)
└── notify/
    └── mock_notify_agent.py # MockNotifyAgent (IAgent)
```

---

## WorkItem Model

All source agents produce `WorkItem` objects — the canonical payload shape consumed by any Conductor workflow:

```python
from conductor_integrations.models import WorkItem

item = WorkItem(
    id="CVE-2023-001",
    source="snyk",
    severity="HIGH",
    type="vulnerability",
    title="Requests 2.18.0 — CVE-2023-32681",
    description="Certificate verification bypass via SSRF...",
    file_path="requirements.txt",
    repo_name="my-service",
    metadata={"cve": "CVE-2023-32681", "cvss": 8.1},
)

# Convert to workflow payload
payload = {"work_item": item.model_dump()}
```

---

## Using Mock Sources

```python
from conductor_integrations.sources.snyk import MockSnykClient

client = MockSnykClient()
items = await client.get_open_findings(project="my-service")
# Returns list[WorkItem] from mocks/snyk/*.json fixtures
```

Each mock client reads from JSON fixtures in the `mocks/` directory at the repo root:

```
mocks/
├── snyk/snyk_finding_001.json
├── sonar/sonar_findings.json
├── blackduck/blackduck_finding.json
└── ado/ado_defect.json
```

---

## Using the Mock Git Agent

`MockGitAgent` implements `IAgent` — plug it into any stage that should "do git work" without real credentials:

```python
from conductor_integrations.git.mock_git_agent import MockGitAgent

orch = WorkflowOrchestrator(
    agents={
        "triage":  TriageAgent(llm),
        "planner": PlannerAgent(llm),
        "git":     MockGitAgent(),      # logs: branch, commit, PR — no real ops
    },
    graph=graph,
)
```

**Mock Git logs:**
```json
{"event": "mock_git.branch_created", "branch": "fix/CVE-2023-001", "run_id": "..."}
{"event": "mock_git.commit_pushed",  "message": "fix: upgrade requests", "run_id": "..."}
{"event": "mock_git.pr_opened",      "title": "Fix: CVE-2023-001", "run_id": "..."}
```

---

## Switching to Live Mode

Set `CONDUCTOR_PROVIDER_MODE=live` in `.env` and provide scanner tokens:

```bash
# .env
CONDUCTOR_PROVIDER_MODE=live

# Snyk
CONSUMER_SNYK_TOKEN=snyk-...

# SonarCloud
CONSUMER_SONAR_TOKEN=...
CONSUMER_SONAR_URL=https://sonarcloud.io

# Black Duck
CONSUMER_BLACKDUCK_TOKEN=...
CONSUMER_BLACKDUCK_URL=https://your-bd-instance.example.com

# Azure DevOps
CONSUMER_ADO_PAT=...
CONSUMER_ADO_ORG=myorg
CONSUMER_ADO_PROJECT=myproject
```

Each source agent checks `CONDUCTOR_PROVIDER_MODE` and delegates to either the mock client or the real API client automatically.

---

## Extending with Your Own Source

```python
from conductor_integrations.models import WorkItem
from conductor_core.interfaces import IAgent
from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision

class JiraSourceAgent:
    """Fetches open security issues from Jira."""

    async def run(self, ctx: WorkflowContext) -> AgentDecision:
        # fetch from Jira API or mock
        item = WorkItem(
            id=ctx.payload["jira_key"],
            source="jira",
            ...
        )
        ctx.payload["work_item"] = item.model_dump()
        return AgentDecision(
            recommendation="proceed",
            confidence=1.0,
            reasoning=["fetched from Jira"],
        )
```

---

## Tests

```bash
cd conductor-integrations
pytest tests/unit -q          # 11 tests, no tokens needed
```

Tests cover: all mock source clients return correct `WorkItem` shapes, MockGitAgent logs operations, MockNotifyAgent no-ops cleanly.
