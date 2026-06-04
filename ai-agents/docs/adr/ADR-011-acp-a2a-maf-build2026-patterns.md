# ADR-011: ACP, A2A, and Microsoft Agent Framework BUILD 2026 Patterns

**Status:** Pending  
**Date:** 2026-06-03  

---

## Context

Three major industry developments landed in 2026 that are directly relevant to Conductor's architecture:

1. **ACP (Agent Client Protocol)** — GitHub Copilot CLI now exposes itself as an ACP server. ACP standardizes communication between editors/IDEs and coding agents, analogous to how LSP standardized language-server integration. ([Copilot CLI ACP docs](https://docs.github.com/en/copilot/reference/copilot-cli-reference/acp-server), [agentclientprotocol.com](https://agentclientprotocol.com/get-started/introduction))

2. **A2A (Agent2Agent) Protocol v1.0** — Google's open protocol (now under the Linux Foundation) for agent-to-agent communication. JSON-RPC 2.0 over HTTP(S), with Agent Cards for capability discovery, streaming via SSE, and async push notifications. First-class Python SDK: `pip install a2a-sdk`. ([a2a-protocol.org](https://a2a-protocol.org), [github.com/google-a2a/A2A](https://github.com/google-a2a/A2A))

3. **Microsoft Agent Framework (MAF) BUILD 2026 announcements** — MAF 1.0 GA (convergence of AutoGen + Semantic Kernel), with four new features highly relevant to Conductor:
   - **CodeAct + Hyperlight micro-VM**: collapses multi-step tool calls into a single sandboxed Python program — 52% faster, 64% fewer tokens vs. sequential tool calls
   - **Foundry Hosted Agents**: per-session VM-isolated sandbox, scale-to-zero, filesystem persistent across restarts
   - **FIDES**: information-flow control middleware against prompt injection (integrity + confidentiality labels per content item)
   - **Agent Harness**: `TodoProvider`, `AgentModeProvider`, `BackgroundAgentsProvider` — production-tested patterns for plan/execute mode, parallel fan-out, and session-scoped memory ([devblogs.microsoft.com/agent-framework](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-at-build-2026-announce/))

This ADR analyzes each, maps the relevant ideas onto Conductor, and defines the implementation work for each.

---

## Decision

**Pending** — adopt four distinct improvements from these three sources. Prioritized below.

---

## Part 1 — ACP: Expose Conductor as an ACP Server

### What ACP is

ACP (Agent Client Protocol) standardizes how a code editor (VS Code, JetBrains, Neovim, etc.) communicates with an agent process. The agent runs as a subprocess or remote server; the editor sends prompts and receives streamed responses over NDJSON (stdio) or HTTP (TCP). GitHub Copilot CLI already exposes itself as an ACP server via `copilot --acp --stdio`.

### What this means for Conductor

Currently, triggering a Conductor pipeline run requires either a Python script or the CLI. ACP would let any ACP-compatible editor (VS Code with the ACP extension, a custom IDE plugin, or a CI/CD runner) send a prompt to Conductor and stream back the pipeline output — without any editor-specific glue code.

```bash
# Conductor as an ACP server — stdio mode (IDE subprocess)
conductor --acp --stdio

# Conductor as an ACP server — TCP mode (CI/CD sidecar)
conductor --acp --port 3000
```

The ACP session model maps onto Conductor's run model cleanly:
- ACP `newSession` → `WorkflowOrchestrator.start_run()`
- ACP `prompt` → ingest payload → pipeline execution
- ACP `sessionUpdate` chunks (agent_message_chunk) → streaming trace events back to the editor
- ACP `requestPermission` → Conductor's human-gate approval flow

### Benefits
- Any ACP-compatible editor can trigger Conductor runs with zero custom integration code
- CI/CD pipelines can drive Conductor via ACP stdio (no Python install required in the CI image)
- Sets up Conductor for future multi-agent coordination where Conductor itself is a peer agent in an ACP ecosystem

### Changes Required

| File | Change |
|---|---|
| `conductor-cli/conductor_cli/acp_server.py` (new) | `ConductorACPServer` — wraps `WorkflowOrchestrator` behind ACP `newSession` / `prompt` API |
| `conductor-cli/conductor_cli/main.py` | Add `--acp`, `--stdio`, `--port` flags to the `conductor` entry point |
| `conductor-core/conductor_core/acp/` (new) | ACP transport layer: NDJSON stdio reader/writer + TCP socket handler |
| `pyproject.toml` | Add optional `acp` dependency group: `agentclientprotocol` (TypeScript SDK is reference; Python binding is emerging) |

---

## Part 2 — A2A: Agent Cards + Cross-Framework Agent Interop

### What A2A is

A2A (Agent2Agent Protocol) is an open standard (Linux Foundation, contributed by Google) that lets agents from different frameworks communicate without sharing internal state. Key primitives:

- **Agent Card** (`/.well-known/agent.json`) — advertises the agent's name, capabilities, input/output modalities, authentication requirements
- **Task lifecycle** — create task → execute steps → stream results (SSE) or poll → get artifacts
- **Transport** — JSON-RPC 2.0 over HTTP(S); Python SDK: `pip install a2a-sdk`
- **Opacity** — agents collaborate without exposing internal memory, prompts, or tools

### What this means for Conductor

Conductor's agents currently exist only inside the Python process. A2A would allow:

1. **Each Conductor agent exposed as a standalone A2A server** — TriageAgent, SecurityAgent, PlannerAgent etc. each get an Agent Card and can be called by any A2A-compatible orchestrator, not just Conductor's own orchestrator.

2. **Conductor's orchestrator as an A2A client** — call external agents (a company's proprietary ReviewerAgent, a third-party ThreatIntelAgent, etc.) as first-class pipeline stages, with no code changes to those agents beyond A2A compliance.

3. **Cross-framework multi-agent pipelines** — Conductor's pipeline could include a LangGraph agent, a MAF agent, and an AutoGPT agent as peers, all coordinated via A2A.

```python
# conductor-core: calling an external A2A agent as a pipeline stage
from a2a_sdk import A2AClient

class ExternalA2AAgent(BaseAgent):
    def __init__(self, agent_card_url: str):
        self._client = A2AClient.from_card_url(agent_card_url)

    async def run(self, context: WorkflowContext) -> WorkflowContext:
        task = await self._client.create_task(input=context.payload)
        result = await self._client.wait_for_completion(task.task_id)
        return context.with_payload_update(result.artifacts)
```

```json
// conductor agent card: /.well-known/agent.json
{
  "name": "conductor-triage-agent",
  "description": "Triages security defects and assigns severity, priority, and pipeline routing",
  "version": "1.0.0",
  "capabilities": ["triage", "severity-scoring", "routing"],
  "inputModes": ["application/json"],
  "outputModes": ["application/json"],
  "endpoint": "http://localhost:8001"
}
```

### Benefits
- Conductor agents become reusable across any A2A-compatible orchestrator (MAF, LangGraph, CrewAI, custom)
- External agents (from other teams or vendors) can be dropped into Conductor pipelines with no adapter code
- Inter-team agent sharing without sharing codebases — preserves opacity
- A2A is already v1.0 stable with Python, Go, .NET, Java, Rust, JS SDKs

### Changes Required

| File | Change |
|---|---|
| `conductor-core/conductor_core/a2a/` (new) | `A2AServer` — wraps any `BaseAgent` as an A2A-compliant HTTP server; `A2AClient` — calls external A2A agents |
| `conductor-core/conductor_core/a2a/agent_card.py` (new) | `AgentCardBuilder` — generates `/.well-known/agent.json` from agent metadata |
| `conductor-core/conductor_core/base_agent.py` | Add `@a2a_agent` decorator option to expose any `BaseAgent` as an A2A server |
| `conductor-integrations/conductor_integrations/a2a_client.py` (new) | `ExternalA2AAgent` — wraps any A2A agent card URL as a Conductor `BaseAgent` usable in workflow YAML |
| `workflow.yaml` | Add `type: a2a` agent type with `card_url` field for external agents |
| `pyproject.toml` | Add `a2a-sdk` to optional `a2a` dependency group |

---

## Part 3 — CodeAct + Hyperlight: Collapse Multi-Step Tool Calls

### What CodeAct + Hyperlight is

MAF's CodeAct replaces sequential tool-call loops (one model turn per tool) with a single model turn that produces a short Python program. The program is executed once inside a **Hyperlight micro-VM** — a fresh, isolated execution environment per call. Benchmarks on multi-step workloads: **52% faster, 64% fewer tokens**.

Hyperlight micro-VMs are:
- Locally isolated (per-call VM, not per-session container)
- Near-zero startup overhead (microsecond-scale VM initialization)
- Strongly sandboxed — model-generated code cannot escape

### What this means for Conductor

Conductor's `CodeAgent` is the pipeline stage most likely to chain many tool calls: read file → analyze → read dependency → check version → propose patch → verify syntax. Each of these is currently a separate model round, driving up latency and cost. CodeAct would collapse this into a single program:

```python
# CodeAgent today: ~6 model turns, ~2000 tokens, ~8 seconds
read_file("src/auth.py")
analyze_imports(...)
check_dependency_version("PyJWT")
propose_patch(...)
verify_syntax(...)
run_tests(...)

# CodeAgent with CodeAct: 1 model turn, ~700 tokens, ~3 seconds
# Model generates:
result_1 = call_tool("read_file", path="src/auth.py")
result_2 = call_tool("check_dependency_version", name="PyJWT")
patch = call_tool("propose_patch", context=result_1, dep_version=result_2)
call_tool("verify_syntax", patch=patch)
```

The Hyperlight sandbox also solves a current gap: Conductor has no isolated execution environment for model-generated code changes. Running proposed patches and tests today is unsafe without containment.

### Benefits
- CodeAgent: estimated 50%+ latency reduction, 60%+ token reduction for multi-step fix generation
- Strong isolation for model-generated code — eliminates the risk of runaway patches escaping the sandbox
- Fewer model round-trips means lower cost per run (critical for high-volume security scanning pipelines)

### Changes Required

| File | Change |
|---|---|
| `conductor-core/conductor_core/runners/codeact_runner.py` (new) | `CodeActRunner` — generates Python tool-call program, submits to Hyperlight sandbox, returns consolidated result |
| `conductor-core/conductor_core/sandbox/hyperlight.py` (new) | `HyperlightSandbox` — thin wrapper around `agent_framework_hyperlight.HyperlightCodeActProvider` |
| `conductor-agents/conductor_agents/agents/code_agent.py` | Add `CodeActRunner` as optional execution backend; falls back to sequential runner |
| `workflow.yaml` | Add `code_agent.runner: codeact` option to enable CodeAct for specific stages |
| `pyproject.toml` | Add `agent-framework-hyperlight` to optional `codeact` dependency group (alpha) |

---

## Part 4 — FIDES: Prompt Injection Defense via Information-Flow Control

### What FIDES is

FIDES (Flow Integrity Deterministic Enforcement System) is a MAF middleware that assigns every content item an **integrity label** (trusted / untrusted) and a **confidentiality label** (public / private). Labels propagate automatically through the agent's reasoning chain. When untrusted content (e.g., text from an issue body, a code comment, a tool result) tries to influence a trusted action (e.g., writing a file, calling an API), FIDES blocks it deterministically — not with a heuristic prompt.

Prompt injection is the #1 risk on the OWASP LLM Top 10. Conductor processes content from:
- Snyk/Sonar/BlackDuck vulnerability reports (untrusted external data)
- Source code files (potentially attacker-controlled)
- ADO/Jira work item descriptions (user-controlled text)
- GitHub issue bodies (public, untrusted)

Any of these could contain injected instructions trying to hijack pipeline actions.

### What this means for Conductor

```python
# conductor-core: FIDES-style label propagation
from conductor_core.security import IntegrityLabel, ConfidentialityLabel, FlowPolicy

class BaseAgent:
    def label_context(self, context: WorkflowContext) -> WorkflowContext:
        # Mark ingest payload as untrusted
        return context.with_labels(
            integrity=IntegrityLabel.UNTRUSTED,
            confidentiality=ConfidentialityLabel.PUBLIC,
        )

    def check_flow(self, action: AgentAction, context: WorkflowContext):
        # Block untrusted content from influencing file writes or API calls
        if context.integrity == IntegrityLabel.UNTRUSTED and action.is_write():
            raise FlowViolationError(f"Untrusted content tried to trigger {action}")
```

### Benefits
- Deterministic, non-bypassable prompt injection defense (not a system prompt heuristic)
- Audit trail of label propagation for compliance (SOC2, ISO 27001)
- Particularly critical for Conductor: security remediation pipelines are a high-value injection target (an attacker who controls a Snyk finding description could try to hijack CodeAgent)

### Changes Required

| File | Change |
|---|---|
| `conductor-core/conductor_core/security/` (new) | `IntegrityLabel`, `ConfidentialityLabel`, `FlowPolicy` enums + `FlowViolationError` |
| `conductor-core/conductor_core/context.py` | Add `integrity_label` and `confidentiality_label` fields to `WorkflowContext` |
| `conductor-core/conductor_core/base_agent.py` | Add `check_flow(action, context)` pre-action hook; raise `FlowViolationError` on violation |
| `conductor-integrations/conductor_integrations/` | All ingest clients (`SnykIngestClient`, `AdoIngestClient`, etc.) tag payloads as `UNTRUSTED` on creation |
| `conductor-core/conductor_core/telemetry.py` | Log label propagation events and flow violations to telemetry |

---

## Summary: What to Implement and When

| Feature | Source | Priority | Depends on |
|---|---|---|---|
| FIDES-style prompt injection defense | MAF BUILD 2026 | **Tier 1** (security, independent) | Nothing — add to `conductor-core` now |
| A2A Agent Cards + A2AClient for external agents | A2A Protocol v1.0 | **Tier 1** (interop, independent) | `a2a-sdk` stable |
| ACP server (`conductor --acp`) | GitHub Copilot CLI ACP | **Tier 2** (after manifest ADR-009 + CLI ADR-010) | ADR-009, ADR-010 |
| CodeAct + Hyperlight sandbox for CodeAgent | MAF BUILD 2026 | **Tier 2** (performance, alpha) | `agent-framework-hyperlight` exits alpha |
| A2A server (expose Conductor agents externally) | A2A Protocol v1.0 | **Tier 3** (future) | A2AClient + stable hosting |

---

## What Does NOT Apply to Conductor

| MAF / ACP concept | Why not applicable |
|---|---|
| Foundry Hosted Agents (Azure-specific) | Conductor targets on-prem / self-hosted; Azure dependency is optional |
| ACP diff rendering types | Conductor is a pipeline, not an IDE extension; diff output is handled by `conductor diff` CLI |
| MAF `FileMemoryProvider` / `TodoProvider` | Conductor has its own `SQLiteResultStore` and `WorkflowContext`; these are equivalents already |
| A2A `QuerySkill()` dynamic negotiation | Conductor's agents have fixed capabilities per workflow graph; dynamic skill negotiation is out of scope for v1 |

---

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Ignore all three protocols | All three are production-stable (A2A v1.0, MAF 1.0 GA, ACP in public preview). Not adopting them means Conductor becomes an island — incompatible with the emerging standard agent ecosystem. |
| Adopt all three simultaneously | Too large a surface change for one release. Tier 1 items (FIDES + A2A client) are independent and safe; Tier 2 items need foundation work first. |
| Build custom prompt injection heuristics instead of FIDES | FIDES is deterministic; heuristics fail silently. For a security-remediation pipeline, silent failure is unacceptable. |
| Use MCP instead of A2A for inter-agent calls | MCP is tool-oriented (agent calls tools). A2A is agent-oriented (agent calls agents). Conductor's stages are agents, not tools — A2A is the correct protocol. |

---

## Consequences

**Positive:**
- FIDES labels make Conductor's injection attack surface deterministic and auditable
- A2A client enables drop-in external agents (vendor tools, other team agents) without forking Conductor
- ACP server makes Conductor callable from any ACP-compatible editor or CI runner
- CodeAct could cut CodeAgent costs by ~60% — meaningful at production scan volumes
- Conductor aligns with the emerging open standard for multi-agent systems (A2A is Linux Foundation)

**Negative / Trade-offs:**
- Three new protocol dependencies increase the maintenance surface
- Hyperlight is still in alpha — CodeAct adoption is gated on its stability
- A2A server exposes Conductor agents as network endpoints — requires authentication/TLS configuration
- FIDES label propagation adds ~1 additional field to `WorkflowContext` and small overhead per action check

---

## References

- [GitHub Copilot CLI ACP Server](https://docs.github.com/en/copilot/reference/copilot-cli-reference/acp-server)
- [Agent Client Protocol Introduction](https://agentclientprotocol.com/get-started/introduction)
- [Agent2Agent (A2A) Protocol — GitHub](https://github.com/google-a2a/A2A)
- [A2A Protocol Documentation](https://a2a-protocol.org)
- [Microsoft Agent Framework at BUILD 2026](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-at-build-2026-announce/)
- [FIDES: Prompt Injection Defense](https://devblogs.microsoft.com/agent-framework/fides/)
- [CodeAct + Hyperlight](https://devblogs.microsoft.com/agent-framework/codeact-with-hyperlight/)
- [ADR-009: conductor.json Manifest](ADR-009-conductor-json-manifest.md)
- [ADR-010: CLI Command Surface](ADR-010-conductor-cli-command-surface.md)
- [ADR-005: Parallel Runners](ADR-005-parallel-runners-not-group-chat.md)
