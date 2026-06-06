# Conductor Quick Start Guide

**⏱️ Time:** 10 minutes  
**🎯 Goal:** Run your first Conductor project

---

## What is Conductor?

Conductor is a **multi-agent LLM orchestration framework** that:
- ✅ Coordinates multiple AI agents in workflows
- ✅ Validates inputs/outputs (no garbage in, no garbage out)
- ✅ Manages secrets securely (token scrubbing, mTLS)
- ✅ Audits every decision (who decided what, when, why)
- ✅ Integrates with Snyk, SonarQube, GitHub, Azure DevOps, etc.

**Use cases:**
- Automated security remediation (CVEs → code fixes → PRs)
- Code quality improvement (style, complexity, anti-patterns)
- DevOps automation (infrastructure, deployments)
- Custom workflows (anything multi-stage)

---

## Installation

### 1. Clone or download

```bash
cd /path/to/Conductor
```

### 2. Install

```bash
cd ai-agents
pip install -e conductor-core/
pip install -e conductor-cli/
pip install -e conductor-agents/
```

Or quick install:

```bash
make setup  # from ai-agents/ — creates .venv and installs all
```

### 3. Verify

```bash
conductor --version
# conductor 1.0.0 (ADR-009-013)

conductor check
# ✅ Dependencies verified
# ✅ Secrets detector working
# ✅ Validator ready
```

---

## 5-Minute Tutorial

### Step 1: Copy hello-world Sample

```bash
cd samples/projects
cp -r hello-world my-first-app
cd my-first-app
```

### Step 2: Run (Plan Mode)

```bash
python main.py --plan
```

**Output:**
```
============================================================
Conductor: hello-world v1.0.0
============================================================

📋 Plan: Call greeter_agent with name='World'
   Context: {'run_id': 'HELLO-20260604-...', 'user': 'developer', 'mode': 'plan'}

✋ PLAN MODE — Not executing (use --execute to run)
```

**What this shows:**
- What agents will run
- What parameters they'll receive
- The context (audit trail metadata)
- **Halts before execution** (safer than blindly executing)

### Step 3: Run (Execute Mode)

```bash
python main.py --name Alice
```

**Output:**
```
============================================================
Conductor: hello-world v1.0.0
============================================================

📋 Plan: Call greeter_agent with name='Alice'
   Context: {'run_id': 'HELLO-20260604-...', 'user': 'developer', 'mode': 'execute'}

▶️  Executing agent...

✅ Success!
   Greeting: 👋 Hello, Alice!
   Timestamp: 2026-06-04T00:12:34
   Context keys: ['run_id', 'user', 'mode']

📝 Logged to logs/hello-world.log

============================================================
✨ You've built your first Conductor app! Next steps:
   1. Read QUICKSTART.md for API overview
   2. Check samples/security-remediation/ for production pipeline
   3. Add your own agents in agents/ directory
============================================================
```

### Step 4: Inspect Logs

```bash
cat logs/hello-world.log
# HELLO-20260604-001234 | 👋 Hello, Alice! | 2026-06-04T00:12:34
```

**Why logs matter:**
- Audit trail of every decision
- Reproducible runs (run_id + timestamp)
- Cost tracking (tokens, latency)
- Debugging (what went wrong, when)

---

## Key Concepts

### 1. conductor.json (Manifest)

Every Conductor project needs a `conductor.json`:

```json
{
  "name": "my-app",
  "version": "1.0.0",
  "agents": [
    {"name": "analyzer", "capabilities": ["analyze"]},
    {"name": "fixer", "capabilities": ["fix"]}
  ],
  "integrations": ["snyk", "github"]
}
```

**Purpose:** Declare your project structure upfront.

### 2. Agents

Agents are async functions that take input and return output:

```python
# agents/analyzer.py
async def analyzer(context: dict, code: str = "", **kwargs):
    """Analyze code for issues."""
    return {
        "agent": "analyzer",
        "issues_found": 3,
        "severity": "high",
    }
```

**Pattern:**
- Name: snake_case
- Input: `context` dict + keyword args
- Output: structured dict
- Async: supports concurrent execution

### 3. Context (Metadata)

Every agent receives context about the run:

```python
context = {
    "run_id": "SNYK-20260604-123456",  # Unique ID for audit
    "user": "alice@company.com",       # Who triggered it
    "repo": "my-app",                  # Which repo/resource
    "mode": "execute",                 # "plan" or "execute"
}
```

**Used for:**
- Logging (who did what, when, why)
- Auditing (compliance, security review)
- Debugging (trace execution flow)

### 4. Workflow (YAML or Code)

Define how agents work together:

**YAML (declarative):**
```yaml
stages:
  - name: triage
    agent: triage_agent
    inputs: [findings]
  
  - name: analyze
    agent: security_analyzer
    inputs: [triage.output]
    
  - name: fix
    agent: code_fixer
    inputs: [analyze.output]
    human_gate: true  # Require approval
    
  - name: commit
    agent: git_agent
    inputs: [fix.output]
```

**Code (imperative):**
```python
async def main():
    # Run agents in sequence
    triage_result = await triage_agent(context)
    analyze_result = await analyzer(context, findings=triage_result)
    fix_result = await fixer(context, issues=analyze_result)
```

### 5. Human Gates

Pause execution for approval:

```yaml
stages:
  - name: approve_pr
    human_gate: true  # Wait for human decision
    prompt: "Create PR with changes?"
```

**Security:** Destructive operations (commits, PRs, deployments) require human approval.

---

## Common Commands

### Initialize a new project

```bash
conductor init my-project
cd my-project
# Generates conductor.json + agents/ directory
```

### Run in plan mode (no side effects)

```bash
conductor plan
# Show what WOULD happen without executing
```

### Run in execute mode (real side effects)

```bash
conductor run --execute
# Actually make PRs, commit, etc.
```

### Check health

```bash
conductor check
# Verify dependencies, secrets, tokens
```

### View run history

```bash
conductor runs --store runs.db
# List all previous runs with status, tokens, cost

conductor trace <run_id> --store runs.db
# Full reasoning trace: who decided what, confidence, model used
```

---

## Example: Security Remediation

Here's a real-world pipeline (from `samples/security-remediation/`):

```
User runs: conductor run --plan
           ↓
           Agent: triage
           ├─ Input: vulnerability findings from Snyk
           ├─ Decides: severity, fix urgency
           └─ Output: risk assessment
           ↓
           Agent: security_analyzer
           ├─ Input: risk assessment
           ├─ Analyzes: CVE details, attack surface
           └─ Output: fix strategy
           ↓
           Agent: code_fixer
           ├─ Input: fix strategy
           ├─ Generates: code patch
           └─ Output: diff/patch
           ↓
           Agent: reviewer
           ├─ Input: code patch
           ├─ Checks: quality, security
           └─ Output: approval/rejection
           ↓
           Agent: git_agent
           ├─ Input: approved patch
           ├─ Creates: branch, commit, PR
           └─ Output: PR URL
           ↓
           Agent: notifier
           ├─ Input: PR URL
           ├─ Posts: comment to Slack/Teams
           └─ Output: notification receipt
           ↓
User sees: ✅ PR #1234 opened with fix
           📝 Slack notification sent
           💰 Estimated cost: $0.12 (tokens)
```

**With Conductor:**
- ✅ All decisions logged (audit trail)
- ✅ Can pause before PR (human gate)
- ✅ Secrets scrubbed (no tokens in logs)
- ✅ Can replay run (same run_id)

---

## Next Steps

1. **Run hello-world sample** (already done above)
2. **Try security-remediation** sample:
   ```bash
   cd samples/projects/security-remediation
   python main.py --plan
   ```
3. **Read full docs:**
   - [ARCHITECTURE.md](./ARCHITECTURE.md) — Deep dive (30 min)
   - [API_REFERENCE.md](./API_REFERENCE.md) — Class docs
   - [SECURITY_HARDENING.md](./SECURITY_HARDENING.md) — Production checklist
4. **Build your own:**
   ```bash
   conductor init my-app
   # Edit conductor.json
   # Write agents/ code
   # Add integrations
   # Deploy
   ```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` | Run `make setup` from ai-agents/ |
| `conductor: command not found` | Run `pip install -e conductor-cli/` |
| `No output` | Check logs: `cat logs/*.log` |
| `Agent timed out` | Increase timeout: `conductor run --timeout 120` |
| `mTLS certificate error` | Run `conductor init-certs` to generate |

---

## Key Takeaways

✅ **Conductor** = multi-agent orchestrator with audit trail  
✅ **conductor.json** = project manifest (structure)  
✅ **Agents** = async functions (input → output)  
✅ **Context** = metadata (audit trail, credentials)  
✅ **Plan mode** = show what would happen (safer)  
✅ **Execute mode** = actually do it (with human gates)  
✅ **Logs** = every decision recorded (compliance)  
✅ **Secrets** = automatically scrubbed (security)  

---

## More Info

- [samples/hello-world/README.md](../samples/projects/hello-world/README.md) — Tutorial
- [samples/security-remediation/README.md](../samples/projects/security-remediation/README.md) — Production example
- [consumer-showcase/](../consumer-showcase/) — Reference implementation (production-grade)
- [docs/ARCHITECTURE.md](./ARCHITECTURE.md) — Deep dive
- [docs/THREAT_MODEL.md](./THREAT_MODEL.md) — Security threats + defenses
- [docs/DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) — Production checklist

---

**Questions?** Check out docs/ directory or ask in discussions.
