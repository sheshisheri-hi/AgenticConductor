# conductor-agents

**The 10 domain agents for security-remediation pipelines.** This is Layer 2 of the Conductor stack — reusable, prompt-driven agents that any consumer can import and wire into their own workflow YAML.

All agents extend `BaseAgent` from `conductor-core`. Each agent has:
- `agent.py` — the Python class (model, prompt loading, decision logic)
- `SKILL.md` — **human-readable spec** (role, inputs, outputs, behaviour, troubleshooting)
- `prompts/` — **Markdown prompt templates** (edit these to change agent behaviour — no code changes needed)

---

## Install

```bash
pip install conductor-agents        # from PyPI (future)
pip install -e .                    # editable local install
```

Depends on `conductor-core`.

---

## All 10 Agents

| Agent | Class | Stage key | Role |
|---|---|---|---|
| **Triage** | `TriageAgent` | `triage` | Classify severity, route, deduplicate |
| **Security Analyst** | `SecurityAnalystAgent` | `security_analysis` | CVE scoring, CVSS, attack surface |
| **Resolver** | `ResolverAgent` | `resolve` | Map finding to fix strategy |
| **Planner** | `PlannerAgent` | `plan` | Generate ordered fix steps + PR description |
| **Code** | `CodeAgent` | `code` | Produce diff/patch for the fix |
| **Reviewer** | `ReviewerAgent` | `review` | Adversarial code + plan review |
| **Scribe** | `ScribeAgent` | `scribe` | Generate PR body, ticket comment, changelog |
| **Git** | `GitAgent` | `git` | Branch, commit, open PR (execute mode) |
| **Notify** | `NotifyAgent` | `notify` | Post Slack/Teams/ADO comment |
| **Feedback** | `FeedbackAgent` | `feedback` | Capture reviewer feedback, update confidence |

---

## Quick Import

```python
from conductor_agents import (
    TriageAgent,
    SecurityAnalystAgent,
    ResolverAgent,
    PlannerAgent,
    CodeAgent,
    ReviewerAgent,
    ScribeAgent,
    GitAgent,
    NotifyAgent,
    FeedbackAgent,
)
```

Or import individual agents:

```python
from conductor_agents.agents.triage import TriageAgent
from conductor_agents.agents.reviewer import ReviewerAgent
```

---

## Wiring Agents into a Consumer

```python
# my_consumer/main.py
from conductor_core.orchestrator import WorkflowOrchestrator
from conductor_core.graph import WorkflowGraph
from conductor_core.context import WorkflowContext
from conductor_agents import TriageAgent, PlannerAgent, ReviewerAgent

llm = MyCopilotProvider()  # or StubLLM for testing

graph = WorkflowGraph.from_yaml("config/workflow.yaml")
orch  = WorkflowOrchestrator(
    agents={
        "triage":   TriageAgent(llm),
        "planner":  PlannerAgent(llm),
        "reviewer": ReviewerAgent(llm),
    },
    graph=graph,
)

ctx    = WorkflowContext(run_id="MY-001", payload={"work_item": item.model_dump()})
result = await orch.run(ctx)
```

You only need to provide the agents your workflow YAML references. If `workflow.yaml` only has `triage` and `plan` stages, only pass `TriageAgent` and `PlannerAgent`.

---

## Agent Reference

### TriageAgent — `agents/triage/`

Classifies work items and decides whether to proceed with remediation.

**Key decisions:** `proceed` / `block` / `escalate`  
**Reads from payload:** `work_item.severity`, `work_item.source`, `work_item.repo_name`  
**Writes to payload:** nothing (decision only)  
**Prompts:** `triage_system.md`, `triage_user.md`

---

### SecurityAnalystAgent — `agents/security/`

Deep CVE/SAST analysis: CVSS scoring, attack surface, exploitability.

**Key decisions:** `proceed` (attach analysis) / `block` (un-exploitable or out of scope)  
**Reads from payload:** `work_item` + triage decision context  
**Writes to payload:** nothing (decision only)  
**Prompts:** `analyst_system.md`, `analyst_user.md`, `gatekeeper_system.md`, `gatekeeper_user.md`

---

### ResolverAgent — `agents/resolver/`

Maps a finding to a concrete fix strategy (library upgrade, code patch, config change).

**Key decisions:** `proceed` (with resolution strategy) / `block` (no fix available)  
**Reads from payload:** `work_item` + security analysis decision  
**Prompts:** `resolver_system.md`, `resolver_user.md`

---

### PlannerAgent — `agents/planner/`

Generates an ordered, file-level fix plan + PR description.

**Key decisions:** `proceed` (with `action_items`) / `block`  
**Reads from payload:** `work_item` + all prior decisions  
**Writes to payload:** `fix_plan` dict (steps, files, effort estimate)  
**Prompts:** `planner_system.md`, `planner_user.md`

---

### CodeAgent — `agents/code/`

Produces the actual diff/patch to fix the finding.

**Key decisions:** `proceed` (with `code_diff`) / `block`  
**Reads from payload:** `fix_plan` + `work_item`  
**Writes to payload:** `code_diff`  
**Prompts:** `code_system.md`, `code_user.md`

---

### ReviewerAgent — `agents/reviewer/`

Adversarial review of the plan and code diff. Uses a **different model** by default (`CONDUCTOR_REVIEWER_MODEL`, defaults to `gpt-4o`) to avoid confirmation bias.

**Key decisions:** `proceed` (approved) / `block` (reject) / `escalate` (needs human)  
**Reads from payload:** `fix_plan`, `code_diff`, prior decisions  
**Prompts:** `reviewer_system.md`, `reviewer_user.md`  
**Model override:** set `CONDUCTOR_REVIEWER_MODEL=gpt-4-turbo` (or any model)

---

### ScribeAgent — `agents/scribe/`

Generates PR body, ADO ticket comment, changelog entry.

**Key decisions:** always `proceed`  
**Reads from payload:** `fix_plan`, `code_diff`, `work_item`  
**Writes to payload:** `scribe_output` dict  
**Prompts:** `scribe_system.md`, `scribe_user.md`

---

### GitAgent — `agents/git/`

Creates branch, commits diff, opens PR. **Only runs in `execute` mode.** In `plan` mode the orchestrator halts before reaching this stage if `stop_before: true` is set.

**Key decisions:** `proceed` (PR opened) / `block` (git error)  
**Reads from payload:** `code_diff`, `work_item`, `scribe_output`  
**No LLM call** — pure Git operations

---

### NotifyAgent — `agents/notify/`

Posts a Slack/Teams/ADO comment with the plan or PR link.

**Key decisions:** always `proceed`  
**Reads from payload:** `scribe_output`, `work_item`  
**No LLM call** — pure API call

---

### FeedbackAgent — `agents/feedback/`

Captures human reviewer feedback and updates the run's final confidence score.

**Key decisions:** `proceed` (positive) / `block` (rejection feedback)  
**Reads from payload:** `reviewer_comment` (injected by approval gate)

---

## How to Update Agent Prompts

All agent prompts are Markdown files in `agents/<name>/prompts/`. No Python changes needed.

```
conductor-agents/conductor_agents/agents/
├── triage/
│   ├── SKILL.md              ← spec / contract (read to understand the agent)
│   ├── agent.py              ← Python class (rarely change)
│   └── prompts/
│       ├── triage_system.md  ← EDIT to change system role / persona
│       └── triage_user.md    ← EDIT to change what context is sent per call
├── planner/
│   └── prompts/
│       ├── planner_system.md
│       └── planner_user.md
...
```

**Example: make the planner produce JSON output instead of Markdown:**

1. Open `agents/planner/prompts/planner_system.md`
2. Change the output format instruction at the bottom
3. Restart the pipeline — no Python changes needed

**Example: add a new field to the triage user prompt:**

1. Open `agents/triage/prompts/triage_user.md`
2. Add `Repository size: $repo_size` to the template
3. Open `agents/triage/agent.py` → update `_get_prompt_variables()` to return `repo_size`

---

## How to Update Agent Skills (SKILL.md)

`SKILL.md` is a **human-readable spec** used for:
- Documenting what the agent can and cannot do
- Onboarding new team members
- Reference when debugging unexpected agent behaviour
- LLM-assisted development (feed to Copilot to generate agent code)

It does **not** affect runtime. Updating `SKILL.md` never requires a deployment.

---

## Adversarial Reviewer — Model Override

The `ReviewerAgent` intentionally uses a different model than the planner/coder to avoid confirmation bias:

```bash
# .env
CONDUCTOR_LLM_MODEL=gpt-4o            # planner, coder, triage use this
CONDUCTOR_REVIEWER_MODEL=gpt-4-turbo  # reviewer uses this
```

You can also override the model per-stage in `workflow.yaml`:

```yaml
stages:
  - name: adversarial_gate
    agent: reviewer
    model: o1-preview    # overrides both env vars for this stage only
    on_proceed: scribe
    on_block: terminal
```

Priority (highest → lowest):
1. YAML `model:` field on the stage
2. `ReviewerAgent.MODEL_OVERRIDE` (set from `CONDUCTOR_REVIEWER_MODEL`)
3. `CONDUCTOR_LLM_MODEL` global

---

## Adding a New Agent

1. Create the folder:
   ```
   conductor_agents/agents/my_new_agent/
   ├── __init__.py
   ├── SKILL.md      (copy from another agent and edit)
   ├── agent.py
   └── prompts/
       ├── my_new_agent_system.md
       └── my_new_agent_user.md
   ```

2. Implement `agent.py`:
   ```python
   from pathlib import Path
   from conductor_core.base_agent import BaseAgent
   from conductor_core.context import WorkflowContext
   from conductor_core.decisions import AgentDecision

   class MyNewAgent(BaseAgent):
       AGENT_NAME = "my_new_agent"

       def __init__(self, llm, **kwargs):
           super().__init__(llm, prompts_dir=Path(__file__).parent / "prompts", **kwargs)

       def _get_system_prompt_name(self) -> str:
           return "my_new_agent_system"

       def _get_user_prompt_name(self) -> str:
           return "my_new_agent_user"

       def _get_prompt_variables(self, ctx: WorkflowContext, round_num: int) -> dict:
           item = ctx.payload.get("work_item", {})
           return {"title": item.get("title", ""), "description": item.get("description", "")}
   ```

3. Export from `conductor_agents/agents/__init__.py`

4. Add to your consumer's `workflow.yaml` and `agents` dict

---

## Tests

```bash
cd conductor-agents
pytest tests/ -q
```
