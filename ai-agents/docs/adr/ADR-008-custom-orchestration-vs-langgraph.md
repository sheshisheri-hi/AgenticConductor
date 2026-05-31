# ADR-008: Custom Orchestration vs LangGraph

**Status:** Accepted  
**Date:** 2026-05-01  

---

## Context

When migrating from the original Aspen Sentinel implementation to the generic Conductor framework, the primary design goal was to build a **reusable, domain-agnostic multi-agent orchestration layer** that any team could adopt. At the start of the project, two prominent frameworks were evaluated:

- **LangGraph** (LangChain ecosystem) — stateful graph-based agent orchestration with built-in DAG execution, state checkpointing, and tool calling
- **Custom YAML-driven pipeline** — purpose-built sequential/parallel runner with confidence gating and plan/execute modes

The original Aspen Sentinel implementation had tightly-coupled agents and no clear separation between orchestration logic and domain knowledge. The migration goal was to decouple these completely.

---

## Options Considered

| Option | Description | Pros | Cons |
|---|---|---|---|
| A | **LangGraph** | Rich ecosystem, active community, built-in state graph, tool use, React/ReAct loop | Large dependency footprint; opinionated state model; graph DSL adds learning curve; harder to make YAML-configurable; confidence-gating and plan/execute modes require custom wrapping anyway |
| B | **Custom pipeline (chosen)** | YAML-driven stages, sequential + parallel runners, confidence gating, plan/execute mode, zero framework lock-in | More code to maintain; no built-in graph visualizer |
| C | **CrewAI** | Role-based agents, easier to get started | Less control over stage transitions, no plan/execute mode concept |

---

## Decision

**Option B — custom YAML-driven pipeline** built on top of plain Python `async/await`.

---

## Reasoning

1. **YAML-configurable stages were the core requirement.** A security team should be able to change which agents run, in what order, and under what conditions — without writing Python code. LangGraph's programmatic graph definition would require wrapping in a YAML layer anyway.

2. **Confidence gating is first-class.** The `BaseAgent` multi-round reasoning loop (confidence threshold → enrich → retry) is central to the design. This is not natively supported by LangGraph and would require significant custom nodes.

3. **Plan/execute mode with `stop_before`.** The ability to halt the pipeline before a destructive stage (git push, PR creation) is a safety requirement. Implementing this cleanly in LangGraph would require state manipulation and conditional edges that add complexity without benefit.

4. **Dependency footprint.** `conductor-core` has zero optional dependencies beyond `pydantic` and `structlog`. Adding LangGraph would pull in the entire LangChain ecosystem (~30+ packages), making `conductor-core` unsuitable as a lightweight library.

5. **Session isolation (see ADR-004).** Each agent call uses a fresh LLM session with no shared conversation history. LangGraph's message-passing model assumes shared state across nodes, which conflicts with this design.

6. **Parallel runners via `asyncio.gather`.** Parallel agent groups are implemented with `asyncio.gather` — simple, debuggable, no graph state needed.

---

## What LangGraph Does Better

LangGraph is a better choice when:
- You need **ReAct-style tool use** (agents calling external tools and looping based on results)
- You need **human-in-the-loop checkpointing** with resume from a specific graph node
- Your graph topology changes **dynamically** at runtime (conditional branching based on LLM output)
- You're already deeply invested in the LangChain ecosystem

None of these apply to the current Conductor use case. If a future phase requires dynamic graph topology or ReAct tool use, revisiting LangGraph as an optional runner backend would be worth exploring.

---

## Consequences

- `conductor-core` remains dependency-light and framework-agnostic
- Workflow topology is fully YAML-configurable — no Python changes needed to add/remove/reorder stages
- Adding a LangGraph-backed runner in future is possible without breaking the `IAgent` / `WorkflowGraph` interfaces
- No built-in graph visualization (mitigated by OTEL traces + `conductor trace` CLI)
