# ADR-012: Structured Hooks System and Policy Conflict Resolution

**Status:** Pending  
**Date:** 2026-06-03  

---

## Context

Two GitHub Copilot reference pages surface patterns directly applicable to Conductor:

1. **[Hooks Reference](https://docs.github.com/en/copilot/reference/hooks-reference)** — Copilot CLI and cloud agent define a rich lifecycle hook system with 10 named events, three hook types (command, HTTP, prompt), JSON payload contracts, regex matchers, and clear fail-open / fail-closed semantics per hook type.

2. **[Policy Conflicts](https://docs.github.com/en/copilot/reference/policy-conflicts)** — When multiple organizations with different Copilot policies grant a user a license, GitHub resolves conflicts using two rules: **least restrictive wins** for most features, **most restrictive wins** for sensitive operations (privacy, metrics access, code matching).

Conductor currently has:
- **No structured hook system** — there is a `hooks` field placeholder in the manifest (ADR-009) but no defined events, payload format, or execution semantics.
- **No policy conflict resolution** — when `conductor.json` files conflict (e.g., different teams deploying Conductor with different confidence thresholds, integration permissions, or human-gate settings), there is no defined merge/resolution strategy.

This ADR defines what to adopt from each.

---

## Decision

**Pending** — implement both:
1. A structured `conductor-hooks` system modelled on the Copilot hooks reference
2. A `PolicyResolver` for `conductor.json` policy conflict resolution modelled on Copilot's least/most restrictive rules

---

## Part 1 — Conductor Hooks System

### Hook Events (mapped from Copilot → Conductor)

| Copilot event | Conductor equivalent | Fires when |
|---|---|---|
| `sessionStart` | `runStart` | A pipeline run begins (`WorkflowOrchestrator.run()` called) |
| `sessionEnd` | `runEnd` | A pipeline run completes (any reason: complete, error, blocked, timeout) |
| `preToolUse` | `preAgentRun` | Before an agent's `run()` method is called |
| `postToolUse` | `postAgentRun` | After an agent's `run()` method completes successfully |
| `postToolUseFailure` | `postAgentRunFailure` | After an agent raises an exception |
| `agentStop` | `stageComplete` | A workflow stage completes; hook can block and force re-run |
| `subagentStart` | `parallelAgentStart` | A parallel runner spawns a child agent |
| `subagentStop` | `parallelAgentStop` | A parallel runner child agent completes |
| `permissionRequest` | `humanGateRequest` | A human-gate is reached before proceeding to a destructive stage |
| `errorOccurred` | `errorOccurred` | Any unhandled exception in the pipeline |

### Hook Types (all three from Copilot, adapted)

#### 1. Command hooks
Run a shell command. **Fail-closed** for `preAgentRun` (non-zero exit = agent is denied). **Fail-open** for all post/notification hooks.

```json
{
  "version": 1,
  "hooks": {
    "preAgentRun": [
      {
        "type": "command",
        "bash": "python scripts/pre_agent_check.py",
        "env": { "CONDUCTOR_RUN_ID": "${run_id}" },
        "timeoutSec": 30,
        "matcher": { "agentName": "code_agent" }
      }
    ]
  }
}
```

#### 2. HTTP hooks
POST the event payload as JSON to a URL. **Fail-open** always (network errors never block the pipeline). Required for Slack/Teams/PagerDuty/webhook integrations without writing a full `INotifier`.

```json
{
  "version": 1,
  "hooks": {
    "runEnd": [
      {
        "type": "http",
        "url": "https://hooks.slack.com/services/T00/B00/xxx",
        "headers": { "Content-Type": "application/json" },
        "timeoutSec": 10
      }
    ],
    "humanGateRequest": [
      {
        "type": "http",
        "url": "https://internal.example.com/conductor/approvals",
        "headers": { "Authorization": "Bearer ${CONDUCTOR_API_TOKEN}" },
        "allowedEnvVars": ["CONDUCTOR_API_TOKEN"]
      }
    ]
  }
}
```

#### 3. Inject hooks (analogous to Copilot's `prompt` type)
Inject additional context into the agent's prompt at `runStart` or `preAgentRun`. Lets infrastructure teams prepend security policies, repo context, or compliance rules to every agent run without modifying agent code.

```json
{
  "version": 1,
  "hooks": {
    "preAgentRun": [
      {
        "type": "inject",
        "context": "POLICY: Do not propose changes to files in /infra/. Always preserve existing copyright headers.",
        "matcher": { "agentName": "code_agent" }
      }
    ]
  }
}
```

### Key Design Decisions from Copilot Hooks

#### Fail-closed vs. fail-open semantics
Directly adopted from Copilot's model:

| Hook event | Command hooks | HTTP hooks |
|---|---|---|
| `preAgentRun` | **Fail-closed** — crash or non-zero exit denies agent execution | **Fail-open** — network error falls through |
| `humanGateRequest` | **Fail-closed** — unanswered gate = deny | **Fail-open** — timeout = use default gate behavior |
| All post/notification events | Fail-open | Fail-open |

This is a security-critical distinction: `preAgentRun` hooks are the right place to enforce compliance checks (e.g., "block CodeAgent if the repo has an open security freeze flag"). They must be fail-closed.

#### Matcher regex on `agentName` and `stageName`
Hooks fire selectively. A hook with `"matcher": { "agentName": "code_agent" }` fires only for CodeAgent. A hook with `"matcher": { "stageName": "^(code|deploy).*" }` fires only for code and deploy stages. This prevents hook proliferation — one hooks.json can cover all agents with targeted matchers.

```json
{
  "hooks": {
    "preAgentRun": [
      {
        "type": "command",
        "bash": "scripts/security-freeze-check.sh",
        "matcher": { "agentName": "code_agent|git_agent|deploy_agent" }
      }
    ]
  }
}
```

#### `stageComplete` can block and force re-run
Directly from `agentStop` semantics. A `stageComplete` hook with `decision: "block"` forces the stage to re-run (up to a configurable max retry count). This enables external quality gates:

```bash
# hooks/quality-gate.sh — called on stageComplete for code_agent
# Reads the proposed patch from the run store, runs an internal linter
# Exits 1 (block) if the patch fails, 0 (allow) to proceed
conductor trace --run $CONDUCTOR_RUN_ID --format json | python scripts/lint_patch.py
```

#### Hook configuration loading order (multi-source, merged)
Adopted from Copilot's layered loading:

1. `conductor.json` inline `hooks` field (project-level, committed)
2. `config/hooks.json` (project-level, separate file)
3. `~/.conductor/hooks/*.json` (user-level, machine-specific)
4. Integration plugins declaring their own hooks

When the same event appears in multiple sources, **all entries run** (not first-wins). This allows an infrastructure team's user-level hook (e.g., a compliance HTTP hook) to coexist with a project's own command hook.

### Hook Event Payloads

Conductor adopts camelCase format with a consistent base envelope:

```typescript
// Base fields on every Conductor hook payload
{
  runId: string;           // UUID for this pipeline run
  timestamp: number;       // Unix ms
  workflowName: string;    // e.g. "security-remediation"
  mode: "plan" | "execute";
  source: string;          // e.g. "snyk", "ado", "github"
}

// preAgentRun / postAgentRun additional fields
{
  agentName: string;       // e.g. "code_agent"
  stageName: string;       // e.g. "code_generation"
  round: number;           // enrichment round index
}

// postAgentRun additional fields
{
  confidence: number;
  recommendation: string;
  tokensUsed: number;
  latencyMs: number;
}

// postAgentRunFailure additional fields
{
  error: { message: string; name: string; stack?: string };
  errorContext: "model_call" | "tool_execution" | "system";
  recoverable: boolean;
}

// runEnd additional fields
{
  reason: "complete" | "error" | "blocked" | "timeout";
  blocked: boolean;
  blockedReason?: string;
  totalTokens: number;
  estimatedCostUsd: number;
  decisionCount: number;
}
```

---

## Part 2 — Policy Conflict Resolution

### What the Copilot policy conflict system does

When an enterprise has multiple orgs with different policies, Copilot resolves conflicts using:
- **Least restrictive wins** for most features (if any org enables it, the user gets it everywhere)
- **Most restrictive wins** for sensitive operations (if any org disables it, the user loses it everywhere)

The key insight: **the sensitivity of the operation determines which resolution rule applies**, not a single blanket rule.

### What this means for Conductor

Conductor is deployed by teams with different `conductor.json` configurations. In a monorepo or shared infrastructure scenario, multiple teams may have conflicting settings:

| Setting | Team A | Team B | Which wins? |
|---|---|---|---|
| `confidence_threshold: 0.8` | 0.8 | 0.6 | Most restrictive (0.8) — code changes |
| `human_gate: code_agent` | required | optional | Most restrictive — gate required |
| `disabled_agents: []` | `[]` | `["notify_agent"]` | Most restrictive — agent stays disabled |
| `integrations: ["snyk"]` | snyk | snyk + ado | Least restrictive — union of integrations |
| `notifications: ["slack"]` | slack | teams | Least restrictive — union of channels |
| `strict: true` | true | false | Most restrictive — strict always wins |
| `mode: "plan"` | plan | execute | Most restrictive — plan wins |

### Proposed `PolicyResolver` rules

```python
# conductor-core/conductor_core/policy.py

class PolicyResolver:
    """
    Merges multiple ConductorManifests (e.g., project + user + org level)
    using least/most restrictive rules per field.
    """

    # Most restrictive wins — if any config restricts, all are restricted
    MOST_RESTRICTIVE = {
        "confidence_threshold",   # max of all values
        "human_gate_stages",      # union (any config requiring a gate = gate required)
        "disabled_agents",        # union (any config disabling = disabled everywhere)
        "strict",                 # True if any config sets True
        "mode",                   # plan > execute (plan is more restrictive)
        "max_enrichment_rounds",  # min of all values (fewer rounds = more restrictive)
    }

    # Least restrictive wins — union/enable if any config enables
    LEAST_RESTRICTIVE = {
        "integrations",           # union of all enabled integrations
        "notifications",          # union of all notification channels
        "enabled_agents",         # union (if any config enables, it's enabled)
        "allowed_sources",        # union
    }
```

### Hook policy: always use most restrictive

A `preAgentRun` hook from **any** config layer fires, and any hook returning `deny` wins. This is the direct analog of Copilot's "most restrictive for sensitive operations":

- User-level hooks cannot override project-level security hooks
- A project-level security freeze hook cannot be disabled by a user-level config
- Hook sources are additive, but `deny` decisions are absolute

### Config layer hierarchy (most → least authority)

```
org-level conductor-policies.json  (most authority — set by platform team)
    ↓
project conductor.json             (project team authority)
    ↓
user ~/.conductor/settings.json    (individual developer, least authority)
```

Higher-authority layers can **lock** fields to prevent override:

```json
{
  "policies": {
    "confidence_threshold": { "value": 0.75, "locked": true },
    "human_gate_stages": { "value": ["code_agent", "git_agent"], "locked": true }
  }
}
```

---

## Summary of Changes Required

### `conductor-core`

| File | Change |
|---|---|
| `core/hooks/` (new dir) | `HookEngine` — loads, merges, and fires hooks; `HookEvent` dataclass; `HookResult` with `decision`, `additionalContext` |
| `core/hooks/command_hook.py` | `CommandHook` — subprocess execution, fail-closed/fail-open semantics, timeout |
| `core/hooks/http_hook.py` | `HttpHook` — httpx POST, JSON payload, fail-open always |
| `core/hooks/inject_hook.py` | `InjectHook` — prepend context string to agent prompt |
| `core/hooks/matcher.py` | `HookMatcher` — regex match on `agentName`, `stageName` |
| `core/hooks/loader.py` | `HookLoader` — reads hooks from manifest, `hooks.json`, user dir, merges all |
| `core/orchestrator.py` | Fire hook events at `runStart`, `runEnd`, `preAgentRun`, `postAgentRun`, `postAgentRunFailure`, `stageComplete`, `humanGateRequest`, `errorOccurred` |
| `core/policy.py` (new) | `PolicyResolver` — merge multiple manifests with least/most restrictive rules; `locked` field support |
| `core/manifest.py` (ADR-009) | Add `policies` block; add `hooks` field support |

### `conductor-cli`

| File | Change |
|---|---|
| `cli/validate.py` (ADR-010) | Add hook config validation: verify referenced scripts exist, URLs are reachable, JSON schema valid |

### `conductor-integrations`

| File | Change |
|---|---|
| Each ingest/notifier client | Register default HTTP hooks for key events (e.g., Snyk client registers a `runEnd` HTTP hook to post results back) |

### `config/` (consumer project)

| File | Change |
|---|---|
| `hooks.json` (new example) | Example hooks file scaffolded by `conductor init` / `conductor new` |

---

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Simple before/after callbacks in Python | Not configurable without code changes; ops teams cannot add compliance hooks without editing agent code |
| Single pre/post hook only (no per-event granularity) | Insufficient — `preAgentRun` (security gate) vs. `postAgentRunFailure` (recovery guidance) have fundamentally different semantics |
| Always fail-closed for all hooks | `runEnd` HTTP notification hooks failing should never block run completion — blanket fail-closed is too aggressive |
| Flat policy (first-config-wins) | Fails for security: a user-level config could accidentally disable a platform-team security hook |
| Most restrictive for everything | Too aggressive — disabling Slack notifications in one team config shouldn't suppress all notifications everywhere |

---

## Consequences

**Positive:**
- Any team can add compliance hooks (security freezes, audit logging, cost alerts) to Conductor without modifying framework code
- HTTP hooks make Slack/Teams/PagerDuty/webhook integration trivially one-liner config, no `INotifier` implementation needed for simple cases
- `inject` hooks let infra teams prepend compliance policies to agent prompts without forking agent code
- Fail-closed `preAgentRun` gives a deterministic security enforcement point (complements FIDES from ADR-011)
- `PolicyResolver` enables safe multi-team Conductor deployments with predictable conflict resolution
- Platform teams can `"locked": true` critical settings and prevent project/user overrides

**Negative / Trade-offs:**
- Hook execution adds latency per agent turn (mitigated by `timeoutSec` cap)
- Multiple config layers increase debugging complexity (`conductor env` from ADR-010 should show merged hook list)
- HTTP hooks are fire-and-forget — no retry on failure; important events should use command hooks if reliability matters
- `stageComplete` block-and-retry hook requires careful max-retry cap to prevent infinite loops

---

## References

- [GitHub Copilot Hooks Reference](https://docs.github.com/en/copilot/reference/hooks-reference)
- [GitHub Copilot Policy Conflicts](https://docs.github.com/en/copilot/reference/policy-conflicts)
- [ADR-009: conductor.json Project Manifest](ADR-009-conductor-json-manifest.md)
- [ADR-010: Conductor CLI Command Surface](ADR-010-conductor-cli-command-surface.md)
- [ADR-011: ACP, A2A, and MAF BUILD 2026 Patterns](ADR-011-acp-a2a-maf-build2026-patterns.md)
- [ADR-002: YAML-Driven Workflow Graph](ADR-002-yaml-driven-workflow-graph.md)
