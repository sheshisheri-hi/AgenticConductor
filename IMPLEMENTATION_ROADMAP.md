# Conductor Framework — Implementation Roadmap

**Created:** 2026-06-03  
**Status:** Planning Phase

---

## Summary

We have defined 5 new ADRs (009–013 with addendum) capturing 50+ industry best practices from:
- GitHub Copilot CLI (plugin spec, ACP, hooks, CLI reference)
- Google A2A Protocol v1.0
- Microsoft Agent Framework BUILD 2026
- OWASP LLM Top 10 2023-24

**Immediate action:** Implement **MVP phase (4 ADRs, 35 days)** to unblock the entire framework.

---

## Phases Overview

| Phase | Duration | Goal | ADRs |
|---|---|---|---|
| **MVP** | 4 weeks | Foundation: manifest + CLI + hooks + security | ADR-009, 010-T1, 012, 013-T1 |
| **Phase 2** | 4 weeks | Interop: FIDES + A2A + CodeAct + ACP | ADR-011-T1, 010-T2, 011-T2, 011-ACP |
| **Phase 3** | 3 weeks | Hardening: dependencies + validation + telemetry | ADR-013-T2, 011-A2A-server |
| **Future** | TBD | Advanced: Vector/RAG, multi-tenancy, federation | Backlog |

**Total MVP → Phase 3:** ~11 weeks (2.5 months)

---

## MVP Phase (4 weeks)

### Goal
Conductor becomes **self-describing, self-configurable, and security-hardened**. Teams can scaffold a project with `conductor new`, deploy with `conductor.json`, and get deterministic security controls without code changes.

### ADRs in MVP

#### ✅ ADR-009: conductor.json Manifest (5 days)
**Status:** Design complete, ready to implement

**What it delivers:**
- Auto-discovery of agents, workflow YAML, filters, routes
- Eliminates ~60 lines of manual `main.py` wiring
- Foundation for all downstream work

**Files to create:**
- `conductor-core/core/manifest.py` — `ConductorManifest` dataclass + JSON schema validation
- `conductor-core/core/agent_registry.py` — `AgentRegistry.discover(paths)`
- `conductor-cli/cli/init_wizard.py` — `conductor init` scaffolding

**Definition of done:**
- `conductor new my-project` generates a working `conductor.json`
- `WorkflowOrchestrator.from_manifest("conductor.json")` loads all agents + config
- Existing `aspen-sentinel` runs with 5-line `main.py` (down from 60)
- `conductor check` verifies manifest integrity

**Success metrics:**
- ✅ Zero manual wiring in consumer `main.py`
- ✅ `conductor validate` catches all schema errors

---

#### ✅ ADR-010 (Tier 1): CLI Commands (8 days)
**Status:** Design complete, ready to implement

**What it delivers:**
- `conductor init` — auto-detect + generate manifest
- `conductor env` — show loaded config summary
- `conductor validate` — schema validation + CI-safe exits
- `conductor diagnose <RUN_ID>` — explain failures
- `conductor export <RUN_ID>` — Markdown/HTML/Gist export
- `conductor completion SHELL` — shell tab-completion

**Files to create:**
- `conductor-cli/conductor_cli/commands/init.py`
- `conductor-cli/conductor_cli/commands/env.py`
- `conductor-cli/conductor_cli/commands/validate.py`
- `conductor-cli/conductor_cli/commands/diagnose.py`
- `conductor-cli/conductor_cli/commands/export.py`
- `conductor-cli/conductor_cli/formatters/markdown.py`
- `conductor-cli/conductor_cli/formatters/html.py`

**Definition of done:**
- `conductor init` in an existing project auto-discovers agents
- `conductor env` shows all loaded agents, disabled agents, integrations
- `conductor validate` runs in CI with machine-readable JSON output on error
- `conductor export` produces shareable reports (no DB access needed)

**Success metrics:**
- ✅ 0 manual config needed after `conductor init`
- ✅ DevOps teams can validate config in CI/CD
- ✅ Sharing a run with stakeholders is 1-command

---

#### ✅ ADR-012: Hooks + Policy Resolver (10 days)
**Status:** Design complete, ready to implement

**What it delivers:**
- 10 lifecycle hook events (`runStart`, `runEnd`, `preAgentRun`, etc.)
- 3 hook types: command, HTTP, inject
- Fail-closed `preAgentRun` for security gates
- Fail-open post/notification hooks
- `PolicyResolver` for multi-config merging

**Files to create:**
- `conductor-core/core/hooks/` directory (entire module)
  - `engine.py` — `HookEngine` orchestrator
  - `command_hook.py` — subprocess execution
  - `http_hook.py` — JSON POST
  - `inject_hook.py` — prompt injection
  - `matcher.py` — regex matching
  - `loader.py` — multi-source loading
- `conductor-core/core/policy.py` — `PolicyResolver` with least/most restrictive rules
- `conductor-core/core/orchestrator.py` — call hooks at lifecycle points

**Definition of done:**
- Teams can add a Slack webhook (`config/hooks.json`) with zero code
- `preAgentRun` hooks with `decision: "deny"` block agent execution (fail-closed)
- `conductor validate` checks hook command paths + URL reachability
- Policy resolver merges org + project + user configs predictably

**Success metrics:**
- ✅ Compliance hooks (security freeze, audit logging) work without code changes
- ✅ Multi-team deployments don't conflict (least/most restrictive rules work)
- ✅ Hooks fire in order, all fire if multiple match

---

#### ✅ ADR-013 (Tier 1): OWASP LLM Top 10 Security (12 days)
**Status:** Design complete, ready to implement

**What it delivers (4 Tier-1 controls):**
1. `SecretDetector` — redact API keys from input, block from output
2. `PromptSanitizer` — strip injection patterns from untrusted input
3. `OutputFilter` — block dangerous code patterns (os.system, etc.)
4. `TokenBudget` + `InputSizeLimiter` — DoS protection (token budget, input size caps, timeouts)

**Files to create:**
- `conductor-core/core/security/secret_detector.py`
- `conductor-core/core/security/prompt_sanitizer.py`
- `conductor-core/core/security/output_filter.py`
- `conductor-core/core/security/token_budget.py`
- `conductor-core/core/security/input_size_limiter.py`
- Update `conductor-core/core/orchestrator.py` to call security checks before/after each agent
- Update `conductor-core/core/telemetry.py` to log detections (no secrets in logs)

**Definition of done:**
- Input payloads scanned for secrets, redacted before LLM sees them
- Agent outputs scanned for secrets, blocked if `block_on_detect=true`
- Token budget enforced per agent (default 100k tokens)
- Input size capped (default 50k chars per field)
- All detections logged (secret type + action, never the secret itself)

**Success metrics:**
- ✅ Secrets never reach LLM (redacted on input)
- ✅ Secrets never leave LLM (blocked on output)
- ✅ Snyk finding with 1M-line description is rejected (DoS protected)
- ✅ Audit trail shows what was detected, not the secrets

---

### MVP Implementation Order (sequential dependency chain)

```
Week 1: ADR-009 (conductor.json)
  ↓
Week 2: ADR-010-T1 (CLI) — builds on ADR-009
  ↓ (parallel)
Week 2-3: ADR-012 (Hooks) — builds on ADR-009
Week 3: ADR-013-T1 (Security) — builds on ADR-009, ADR-012
  ↓
Week 4: Integration testing + documentation
```

**Critical path:** ADR-009 → all others depend on it

---

## Phase 2 (4 weeks after MVP)

### Goal
Conductor becomes **interoperable** with external agents and LLM tools, and **performant** via CodeAct.

### ADRs in Phase 2

#### ADR-011 (Tier 1): FIDES + A2A Client (8 days)
- FIDES integrity labels (trusted/untrusted) on all content
- A2A client for calling external agents as pipeline stages
- Agent Cards for capability discovery

#### ADR-010 (Tier 2): CLI Commands (10 days)
- `conductor run` — execute pipeline from CLI
- `conductor model` — switch LLM models
- `conductor resume` — resume blocked runs
- `conductor diff` — review changes
- `conductor fleet` — parallel batch processing

#### ADR-011 (Tier 2): CodeAct + Hyperlight (6 days)
- CodeAct Python generator
- Hyperlight sandbox integration
- Collapse multi-step CodeAgent into 1 model turn (50%+ speedup)

#### ADR-011 (Tier 2): ACP Server (8 days)
- `conductor --acp --stdio` (IDE integration)
- `conductor --acp --port 3000` (TCP/CI integration)
- Bidirectional streaming via ACP protocol

**Phase 2 total:** 32 days (4.5 weeks)

---

## Phase 3 (3 weeks after Phase 2)

### Goal
Conductor becomes **hardened and enterprise-grade** with supply-chain verification and schema validation.

### ADRs in Phase 3

#### ADR-013 (Tier 2): OWASP LLM Top 10 (8 days)
- Dependency manifest + verification (`conductor check`)
- `@validated_agent` decorator + Pydantic schema validation
- Token scrubbing + telemetry encryption + retention policy

#### ADR-011 (Tier 3): A2A Server (8 days)
- Expose each Conductor agent as an A2A server
- Other frameworks can call Conductor agents as peers

**Phase 3 total:** 16 days (2.5 weeks)

---

## Summary: Effort & Timeline

| Phase | Duration | Effort | Start | End | Blockers |
|---|---|---|---|---|---|
| MVP | 4 weeks | 35 days | Week 1 | Week 4 | None (parallel with Phase 2 planning) |
| Phase 2 | 4.5 weeks | 32 days | Week 5 | Week 9 | MVP complete |
| Phase 3 | 2.5 weeks | 16 days | Week 10 | Week 12 | Phase 2 complete (except CodeAct depends on Hyperlight GA) |

**Total time:** 11 weeks (2.5 months) for production-hardened Conductor

---

## Critical Success Factors

### ✅ MVP Phase (Do These First)

1. **ADR-009 is the foundation** — everything else depends on it. Do this first.
2. **Security (ADR-013-T1) must land in MVP** — a framework without secret detection is not production-ready.
3. **Hooks (ADR-012) unblock teams** — compliance teams can add audit hooks without code changes.
4. **CLI (ADR-010-T1) is the interface** — developers interact via CLI, not Python scripts.

### ⚠️ Risks to Mitigate

| Risk | Mitigation |
|---|---|
| ADR-009 manifest parsing is slow | Add caching + lazy loading |
| `SecretDetector` regex has false positives | Tunable patterns + allow-list in config |
| Hooks fire order is non-deterministic | Define fixed execution order (pre → post → notification) |
| CodeAct (Phase 2) blocked on Hyperlight alpha | Start Phase 2 anyway, CodeAct is optional optimization |
| Policy resolver conflicts are hard to debug | Add `conductor env --show-policy-layers` for visibility |

---

## Success Metrics

### MVP Phase
- ✅ `conductor new my-project` produces runnable code (0 manual edits)
- ✅ `conductor.json` is the single source of truth (no code wiring)
- ✅ Secrets never reach LLM (input redacted, output blocked)
- ✅ Compliance teams add Slack hooks via config (no code)
- ✅ CI pipelines validate configs before execution
- ✅ Existing `aspen-sentinel` runs with <10 lines of `main.py`

### Phase 2
- ✅ External A2A agents drop into pipelines (1-line YAML)
- ✅ CodeAgent is 50% faster (CodeAct collapse + Hyperlight)
- ✅ Any editor with ACP support can drive Conductor

### Phase 3
- ✅ Supply chain verified at startup (`conductor check`)
- ✅ All agent outputs validated against schema
- ✅ Telemetry is encrypted at rest

---

## Team & Assignments (Recommendation)

| Component | Lead | Size | Effort |
|---|---|---|---|
| **ADR-009: Manifest** | Backend lead | 1 person | 5 days |
| **ADR-010-T1: CLI** | CLI engineer | 2 people | 8 days |
| **ADR-012: Hooks** | Infrastructure lead | 2 people | 10 days |
| **ADR-013-T1: Security** | Security engineer | 2 people | 12 days |
| **Testing + Integration** | QA | 1 person | 5 days |
| **Docs + Migration** | Tech writer | 1 person | 5 days |

**Recommended structure:** 4 parallel work streams (W1-4), all start Week 1.

---

## Quick Start: First Sprint Tasks

### Sprint 1 (Week 1-2)

#### ADR-009: conductor.json
```python
# Create these files
conductor-core/core/manifest.py           # ConductorManifest + JSON schema
conductor-core/core/agent_registry.py     # AgentRegistry.discover()
conductor-cli/cli/init_wizard.py          # conductor init command
```

**Definition of done:**
- `conductor init` in existing repo detects agents + generates `conductor.json`
- `ConductorManifest.load("conductor.json")` parses and validates
- JSON schema in `docs/conductor-json-schema.json` published

#### ADR-013-T1: SecretDetector (start parallel)
```python
# Create these files
conductor-core/core/security/secret_detector.py  # Regex + entropy scanning
# Add to orchestrator: call scan_input() at start, scan_output() after agents
```

**Definition of done:**
- `SecretDetector.scan_input(payload)` redacts API keys
- `SecretDetector.scan_output(context)` blocks if secret found + `block_on_detect=true`
- Test with sample Snyk payloads containing fake credentials

### Sprint 2 (Week 2-3)

#### ADR-010-T1: CLI commands
- `conductor init` wrapper around manifest wizard
- `conductor env` show loaded config
- `conductor validate` schema check + CI output
- `conductor completion bash|zsh|fish`

#### ADR-012: Hooks system
- `HookEngine` loads + fires hooks
- `preAgentRun` command hooks (fail-closed)
- `postAgentRun` HTTP hooks (fire-open)
- `PolicyResolver` merges manifests

### Sprint 3 (Week 3-4)

#### Integration + Docs
- Wire everything: manifest → orchestrator → hooks → security
- Update `aspen-sentinel` to use `conductor.json` + new CLI
- Documentation for each ADR
- Migration guide for existing projects

---

## Next Steps

### Immediate (This Week)
1. ✅ **Review all 5 ADRs** — clarify any design questions
2. ✅ **Get stakeholder sign-off** — confirm MVP scope
3. ✅ **Create JIRA epics** — one per ADR, link to this roadmap

### Next Week (Implementation Kickoff)
1. **Set up feature branches** — one per ADR
2. **Create design docs** — expand each ADR into implementation spec
3. **Sprint planning** — week-by-week task breakdown
4. **Assign teams** — pair senior/junior engineers

### Week 2 (Parallel Sprints Start)
- ADR-009 team: Build manifest parser
- ADR-010 team: Build CLI commands
- ADR-012 team: Build hook system
- ADR-013 team: Build security layer
- All teams: Daily syncs to track blockers

---

## References

- [ADR-009: conductor.json Manifest](docs/adr/ADR-009-conductor-json-manifest.md)
- [ADR-010: CLI Command Surface](docs/adr/ADR-010-conductor-cli-command-surface.md)
- [ADR-011: ACP, A2A, MAF BUILD 2026](docs/adr/ADR-011-acp-a2a-maf-build2026-patterns.md)
- [ADR-012: Hooks + Policy Conflict Resolution](docs/adr/ADR-012-hooks-and-policy-conflict-resolution.md)
- [ADR-013: OWASP LLM Top 10 Security](docs/adr/ADR-013-owasp-llm-top-10-security-controls.md)
- [ADR-013 Addendum: Secret Detection Architecture](docs/adr/ADR-013-ADDENDUM-secret-detection-architecture.md)
