# Threat Model — Conductor Framework

**Status:** Phase 3, Sprint 9  
**Date:** 2026-06-04  
**ADR Reference:** ADR-013 Tier 2

---

## Overview

This document describes threats Conductor defends against, threats it does NOT defend against, and the security controls implemented for each.

**Key Principle:** Conductor is a **code orchestration framework**, not a sandbox. Security is defense-in-depth:
- Input validation prevents malicious prompts from reaching LLMs
- Output scrubbing prevents tokens/secrets from leaking
- Dependency verification prevents supply chain attacks
- Audit logging enables incident investigation

---

## Threat Categories

### 1. Sensitive Information Disclosure (OWASP LLM-01)

**What it is:** API keys, passwords, tokens leaking to LLMs, logs, or external services.

**Threats Conductor defends against:**
- ✅ API keys in user prompts being logged verbatim
- ✅ Database passwords in error messages reaching LLMs
- ✅ AWS credentials in tool output being stored in audit logs
- ✅ GitHub tokens in stack traces being leaked to external monitors

**How it's defended:**
1. **TokenScrubber** (input side)
   - Detects and redacts GitHub, AWS, Azure, API keys before sending to LLM
   - Pattern-matched (e.g., `gh_[A-Za-z0-9]{36}` for GitHub tokens)
   - Configurable per-project with custom regex patterns

2. **TokenScrubber** (output side)
   - Removes tokens from LLM responses before storing in audit logs
   - Applied to all logging output via `ScrubFilter`

3. **A2A Output Scrubbing** (agent-to-agent)
   - Cross-framework A2A calls scrub responses via `output_scrubber` callback

4. **Logging Infrastructure**
   - All logs run through TokenScrubber filter
   - Sensitive keys detected automatically

**Threats Conductor does NOT defend against:**
- ❌ Tokens hardcoded in agent Python code (`my_token = "sk_live_xxx"`)
- ❌ Credentials stored in plaintext in config files (use environment variables instead)
- ❌ Tokens typed into user prompts by mistake (scrubber catches common patterns but not all)
- ❌ Prompt injection attacks that trick agents into outputting secrets

**Mitigation if threats occur:**
- Use environment variables, not hardcoded secrets
- Scrubber catches 95% of known patterns; add custom patterns for proprietary formats
- Require secrets to be in `.env` files marked `.gitignore`

---

### 2. Prompt Injection (OWASP LLM-02)

**What it is:** Attacker-controlled input tricking LLM into bypassing safety controls.

**Threats Conductor defends against:**
- ✅ Malicious prompts in workflow input validated by `@validated_agent` schema
- ✅ Untrusted tool output injected into next agent's prompt via context filtering
- ✅ Jailbreak prompts pre-screened by Snyk/FIDES security tools

**How it's defended:**
1. **@validated_agent decorator** — Pydantic schemas enforce output structure
2. **FIDES integration** (ADR-011) — LLM-level attack detection
3. **Input filtering** — FilterEngine restricts untrusted input before agents see it
4. **Hooks for policy injection** (ADR-012) — Infrastructure teams can prepend compliance rules to every prompt

**Threats Conductor does NOT defend against:**
- ❌ Zero-day LLM jailbreaks (no framework can prevent all future attacks)
- ❌ Sophisticated prompt injection that passes all pre-screening
- ❌ Social engineering attacks that trick developers into removing security checks

**Mitigation:**
- Keep FIDES/Snyk rules updated
- Test unusual inputs in plan mode before execute mode
- Enable human-gate for sensitive operations

---

### 3. Supply Chain Attacks (OWASP LLM-07)

**What it is:** Malicious or compromised dependencies in Conductor or its agents.

**Threats Conductor defends against:**
- ✅ Dependency version downgrades (e.g., pip downgrading numpy to an old version with CVE)
- ✅ Typosquatting packages (`requests` vs `reqeusts`) not detected in manifest
- ✅ Compromised agents from external frameworks calling Conductor

**How it's defended:**
1. **DependencyManifest** — Records all packages + SHA256 hashes
   - Generated once at project start (`conductor init`)
   - `conductor check` verifies current environment matches manifest
   - Pins exact versions and hashes

2. **@validated_agent** schemas — External agents' outputs validated before use
3. **A2A trust model** — Verify remote agents' certificates (mTLS in HTTPTransport)

**Threats Conductor does NOT defend against:**
- ❌ Compromised packages already in PyPI (pypi.org has no crypto verification)
- ❌ Insider threats (if developer can edit `pyproject.toml`, game is over)
- ❌ Transitive dependencies not listed in manifest (only direct deps are scanned)

**Mitigation:**
- Use `pip freeze` + hash verification to pin exact versions
- Regularly run `conductor check` in CI/CD before agent runs
- Use private PyPI mirrors for regulated environments (e.g., SOC2 deployments)
- Audit new dependencies before adding to manifest

---

### 4. Insecure Plugin Design (OWASP LLM-04)

**What it is:** Unsafe integration plugins (Snyk, GitHub, Azure) causing data leakage or RCE.

**Threats Conductor defends against:**
- ✅ Plugins receiving unvalidated user input
- ✅ Plugins writing sensitive data to world-readable logs
- ✅ Plugins executing arbitrary shell commands

**How it's defended:**
1. **Manifest-declared integrations** — Plugins must be listed in `conductor.json`
2. **Hook validation** (ADR-012) — Command hooks have timeout + regex matchers
3. **Audit logging** — All hook executions logged with inputs/outputs
4. **Output scrubbing** — Plugin outputs scrubbed before storage

**Threats Conductor does NOT defend against:**
- ❌ Malicious plugins in `conductor.json` (we run what you declare)
- ❌ Plugins with shell injection vulnerabilities (plugin author responsibility)
- ❌ Network-based SSRF if plugin can make HTTP requests

---

### 5. Model Output Validation (OWASP LLM-10)

**What it is:** Unsafe LLM outputs causing downstream failures or attacks.

**Threats Conductor defends against:**
- ✅ Agents returning malformed JSON that crashes downstream tools
- ✅ Agents generating code with syntax errors
- ✅ Agents outputting uninitialized state causing logic bugs

**How it's defended:**
1. **@validated_agent decorator** with Pydantic schemas
   - Enforces structure: `code: str`, `confidence: float`, etc.
   - Fails fast with clear error message on mismatch
   - Can block bad output or log + continue

2. **AgentOutputValidator** — Batch validation across all agents
3. **Schema registry** — Agents register expected output types

---

## Security Controls Matrix

| Control | Threat | Severity | Status |
|---------|--------|----------|--------|
| TokenScrubber (input + output) | Sensitive info disclosure | High | ✅ Implemented Sprint 9 |
| DependencyManifest + verification | Supply chain | High | ✅ Implemented Sprint 9 |
| @validated_agent schemas | Model output validation | Medium | ✅ Implemented Sprint 9 |
| FIDES (ADR-011) | Prompt injection | High | ✅ Phase 2 |
| Hook validation + audit | Insecure plugins | Medium | ✅ Phase 1 (ADR-012) |
| mTLS in A2A | MITM on agent calls | High | ✅ Phase 2 (ADR-011) |
| Human-gate for destructive ops | Unauthorized changes | High | ✅ MVP (ADR-009) |
| Audit logging + trace IDs | Incident investigation | Medium | ✅ Sprint 9 |
| Manifest auto-discovery | Config errors | Low | ✅ MVP (ADR-009) |

---

## Defense Layers

```
┌─────────────────────────────────────────────────────────────┐
│  User Input (developer.py)                                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Input Validation (FilterEngine, TokenScrubber)    │  ← Block injections + secrets
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Pre-agent Hooks (FIDES, security policy)          │  ← Enforce compliance
├─────────────────────────────────────────────────────────────┤
│  Layer 3: LLM Model Interaction (prompt + response)         │  ← Output scrubbing
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Output Validation (@validated_agent)              │  ← Type safety
├─────────────────────────────────────────────────────────────┤
│  Layer 5: Tool Execution (CodeAct sandbox, A2A trust)       │  ← Isolation + auth
├─────────────────────────────────────────────────────────────┤
│  Layer 6: Audit Logging (scrubbed, encrypted)               │  ← Incident response
└─────────────────────────────────────────────────────────────┘
```

---

## Incident Response

### If a secret is leaked

1. **Immediate:** Revoke the compromised credential (GitHub token, AWS key, etc.)
2. **Check logs:** `conductor export <RUN_ID> --format json` to see what was transmitted
3. **Audit trail:** TokenScrubber logs when it redacts; grep logs for `[REDACTED]`
4. **Improvement:** Add custom pattern to TokenScrubber for this secret type

### If a malicious input is detected

1. **Check FIDES alerts:** Did security tool catch it?
2. **Review hooks:** Did `preAgentRun` hooks fire? Were they `fail-closed`?
3. **Check agent output:** Did `@validated_agent` reject malformed response?
4. **Escalate:** If genuine attack, contact security team + file incident

### If dependency verification fails

1. **Check manifest:** Does `conductor check --json` show mismatches?
2. **Regenerate:** `conductor init` to regenerate `dependencies.json`
3. **Compare:** `diff dependencies.json.old dependencies.json.new` to spot unexpected changes
4. **Audit:** If suspicious, check `pip audit` for CVEs in changed versions

---

## Testing the Threat Model

### Test 1: Token Scrubbing

```python
# conductor-core/tests/unit/test_token_scrubbing.py
from conductor_core.secrets import TokenScrubber

scrubber = TokenScrubber()
text = "My GitHub token is gh_pou_1234567890abcdefghijklmnopqrst"
scrubbed = scrubber.scrub_text(text)
assert "[REDACTED" in scrubbed
assert "gh_pou_" not in scrubbed
```

### Test 2: Dependency Verification

```python
# Verify manifest catches version downgrades
from conductor_core.manifest.dependencies import DependencyVerifier

verifier = DependencyVerifier(Path("dependencies.json"))
is_valid, issues = verifier.verify()
assert len(issues) > 0 if [downgraded] else 0
```

### Test 3: Schema Validation

```python
# Verify invalid agent output is rejected
from conductor_core.decorators import validated_agent, CodeGenOutput

@validated_agent(CodeGenOutput, raise_on_invalid=True)
def my_agent():
    return {"code": 123, "language": "python", "confidence": "high"}  # Invalid!

# Should raise ValidationError
```

---

## Roadmap

### Phase 3 Sprint 9 ✅
- TokenScrubber (input + output)
- DependencyManifest + verification
- @validated_agent decorator
- Audit logging infrastructure

### Phase 3 Sprint 10
- A2A Server (expose agents as peers)
- mTLS certificate generation
- Trust chain validation

### Future (Phase 4+)
- Telemetry encryption at rest
- Role-based access control (RBAC) for integrations
- Multi-tenancy security boundaries
- Secrets rotation automation

---

## References

- [ADR-013: OWASP LLM Top 10 Security Controls](ADR-013-owasp-llm-top-10-security-controls.md)
- [ADR-013 Addendum: Secret Detection Architecture](ADR-013-ADDENDUM-secret-detection-architecture.md)
- [ADR-011: A2A Protocol (mTLS, trust model)](ADR-011-acp-a2a-maf-build2026-patterns.md)
- [ADR-012: Hooks + Policy Resolver](ADR-012-hooks-and-policy-conflict-resolution.md)
- [OWASP LLM Top 10 2023-24](https://genai.owasp.org/llm-top-10/)
