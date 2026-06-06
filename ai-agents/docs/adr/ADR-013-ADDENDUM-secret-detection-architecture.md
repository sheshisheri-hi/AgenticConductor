# ADR-013 Addendum: Secret Detection Architecture

**Date:** 2026-06-03  
**Related:** ADR-012 (Hooks), ADR-013 (OWASP LLM Top 10)

---

## The Question

Can hooks (ADR-012) handle secret detection, or does it need to be in the core pipeline?

**Short answer:** Hooks handle **notification + logging**. Core pipeline handles **blocking + enforcement**. They work together.

---

## Why Hooks Alone Are Insufficient

Hooks are **fire-open** by design:

```json
{
  "hooks": {
    "preAgentRun": [
      { "type": "http", "url": "https://hooks.example.com/scan-secret" }
    ]
  }
}
```

**What happens if:**
- Network times out? Doesn't block the run (falls through)
- Hook returns non-200? Doesn't block the run
- Hook crashes? Doesn't block the run

This is **intentional** — optional notification systems shouldn't break the pipeline.

But for secrets, we **NEED fail-closed enforcement:**
- Secret found in CodeAgent output? **BLOCK IMMEDIATELY.**
- Secret found in ingest payload? **REDACT BEFORE SENDING TO LLM.**

**You cannot have a security gate that is fire-open.** That's a contradiction.

---

## Three-Layer Architecture

### Layer 1: Core Pipeline (MANDATORY, FAIL-CLOSED)

The `SecretDetector` runs **in the orchestrator** as part of the pipeline execution, not as optional middleware:

```python
class WorkflowOrchestrator:
    async def run(self, ingest_payload, ...):
        # LAYER 1: Scan input (fail-closed)
        redacted = await self.secret_detector.scan_input(ingest_payload)
        if redacted != ingest_payload:
            await self.telemetry.log("secret_redacted_from_input", ...)
        
        # Execute pipeline
        for agent in agents:
            result = await agent.run(context)
            
            # LAYER 1: Scan output (fail-closed)
            try:
                result = await self.secret_detector.scan_output(result)
            except SecretFoundError:
                # Immediately block
                await self.telemetry.log("secret_blocked", ...)
                raise  # ← FAIL-CLOSED
```

**Configuration:**
```json
{
  "secret_scanning": {
    "enabled": true,
    "block_on_detect": true,
    "patterns": ["sk_", "ghp_", "AKIA"],
    "entropy_threshold": 4.5
  }
}
```

**Guarantee:** Secret detector **always runs**, **always blocks** if `block_on_detect=true`.

---

### Layer 2: Hooks (OPTIONAL, FIRE-OPEN NOTIFICATION)

After the core pipeline detects a secret (or blocks it), hooks fire to **notify + integrate**:

```json
{
  "version": 1,
  "hooks": {
    "secretBlocked": [
      {
        "type": "http",
        "url": "https://slack.com/api/chat.postMessage",
        "headers": { "Authorization": "Bearer ${SLACK_BOT_TOKEN}" }
      },
      {
        "type": "command",
        "bash": "scripts/incident-response.sh"
      }
    ],
    "postSecretRedaction": [
      {
        "type": "http",
        "url": "https://audit-log.internal.com/log"
      }
    ]
  }
}
```

**New hook events added to ADR-012:**
- `secretBlocked` — fires after core pipeline blocks a run due to secret detection
- `postSecretRedaction` — fires after core pipeline redacts a secret from input

**Semantics:**
- These hooks fire **after** the core security action is complete
- If a hook times out or fails, **the security action has already happened**
- Hooks are notifications, not gates

---

### Layer 3: Telemetry (AUDIT TRAIL, NEVER LOG SECRETS)

```python
class TelemetryData:
    secret_detection_events: list = [
        {
            "timestamp": "2026-06-03T23:30:00Z",
            "run_id": "abc-123",
            "agent": "code_agent",
            "secret_type": "github_token",  # ← NOT the token itself!
            "action": "blocked",  # or "redacted"
            "location": "output",  # or "input"
        }
    ]
```

**Rule:** Never log the actual secret. Log the **type** and **action** for audit + compliance.

---

## Decision Matrix: What Happens Where?

| Scenario | Core Layer | Hooks Layer | Telemetry |
|---|---|---|---|
| Secret in input (e.g., API key in Snyk report) | Redact + allow | `postSecretRedaction` event → audit log | Log redaction |
| Secret in output (e.g., CodeAgent generates API key) + `block_on_detect=true` | Raise `SecretFoundError` **BLOCK** | `secretBlocked` event → Slack alert → incident script | Log block + security event |
| Secret in output + `block_on_detect=false` | Redact output + log warning | `postSecretRedaction` event | Log redaction |

---

## Example: End-to-End Flow

**Setup:**
```json
conductor.json:
{
  "secret_scanning": {
    "enabled": true,
    "block_on_detect": true,
    "patterns": ["sk_", "ghp_"]
  }
}

config/hooks.json:
{
  "version": 1,
  "hooks": {
    "secretBlocked": [
      {
        "type": "http",
        "url": "https://slack.com/api/chat.postMessage",
        "headers": { "Authorization": "Bearer xoxb-..." }
      }
    ]
  }
}
```

**Runtime:**
```
1. Snyk ingest payload arrives:
   {
     "vulnerability": "SQL injection in login.py",
     "api_key_for_testing": "sk_live_abc123..."  ← SECRET!
   }

2. Core pipeline Layer 1 scans input:
   SecretDetector finds "sk_live_abc123"
   Redacts it: "api_key_for_testing": "[SECRET_REDACTED]"
   Logs to telemetry: { action: "redacted", location: "input", ... }

3. CodeAgent runs with redacted payload (no API key to leak)

4. CodeAgent generates output:
   {
     "fix": "UPDATE login SET password = md5(...)",
     "confidence": 0.95,
     "github_token_created": "ghp_abc123..."  ← SECRET!
   }

5. Core pipeline Layer 1 scans output:
   SecretDetector finds "ghp_abc123"
   Raises SecretFoundError("github_token detected")
   Logs to telemetry: { action: "blocked", location: "output", ... }
   BLOCKS THE RUN

6. Hook Layer 2 fires:
   Hook engine publishes event: { secretBlocked: { secret_type: "github_token", ... } }
   HTTP hook POSTs to Slack: "⚠️ Secret detected (github_token) in code_agent, run blocked"
   (If Slack times out, doesn't matter — run is already blocked)

7. Incident response script runs (optional):
   scripts/incident-response.sh
   Emails security team, pages on-call, etc.

8. User sees error: "SecretFoundError: github_token detected in agent output"
```

---

## Configuration Responsibility

| Who | What | Where |
|---|---|---|
| **Security team / platform** | Secret patterns, `block_on_detect` policy | `conductor.json` (committed) |
| **Project team** | Slack notification hook | `config/hooks.json` (committed) |
| **Ops/SRE** | Incident response script path | `scripts/incident-response.sh` (committed) |

**All configuration is committed** — infrastructure-as-code, auditable, versioned.

---

## Why This Design Is Correct

| Principle | How Achieved |
|---|---|
| **Security cannot be optional** | Core layer is mandatory, always runs |
| **Security cannot fail-open** | Block exception raised, run halts |
| **Notifications shouldn't break pipelines** | Hooks fire after security action is complete |
| **Multi-tenancy safe** | One team cannot disable another's security via hooks |
| **Audit trail** | Telemetry logs all detections + actions (no secrets in logs) |
| **Configurable alerts** | Teams can add Slack/email/PagerDuty hooks without code |

---

## Summary of Changes to ADR-012 (Hooks)

Add two new hook events:

```typescript
// New hook event: secretBlocked
{
  runId: string;
  timestamp: number;
  secretType: "github_token" | "api_key" | "aws_credential" | ...;
  location: "input" | "output";
  agent?: string;  // Which agent generated the secret (for output)
  error: string;   // Error message
}

// New hook event: postSecretRedaction
{
  runId: string;
  timestamp: number;
  secretType: string;
  location: "input" | "output";
  agent?: string;
  action: "redacted";  // Secret was redacted, run continues
}
```

---

## Implementation Checklist

**Core Pipeline (ADR-013, Layer 1):**
- [ ] `conductor-core/core/security/secret_detector.py` — regex + entropy scanning
- [ ] `conductor-core/core/orchestrator.py` — call `scan_input()` at start, `scan_output()` after each agent
- [ ] Raise `SecretFoundError` to block run
- [ ] Log to telemetry (never log actual secret)

**Hooks (ADR-012, Layer 2):**
- [ ] Update `HookEngine` to fire `secretBlocked` and `postSecretRedaction` events
- [ ] Hooks are fire-open, no blocking semantics

**Telemetry (ADR-013, Layer 3):**
- [ ] Add `secret_detection_events` to `TelemetryData`
- [ ] Never include actual secret values in logs/telemetry

---

## References

- [ADR-012: Hooks and Policy Conflicts](ADR-012-hooks-and-policy-conflict-resolution.md)
- [ADR-013: OWASP LLM Top 10 — #6 Information Disclosure](ADR-013-owasp-llm-top-10-security-controls.md)
