# ADR-004: Per-Call LLM Session Isolation

**Status:** Accepted  
**Date:** 2026-05-15  

---

## Context

The GitHub Copilot SDK supports two session models:

| Model | Description |
|-------|-------------|
| A | **Persistent session** — one session per pipeline run, all agents append messages to the same chat history |
| B | **Per-call session** — each `llm.call()` creates a new session, sends one prompt, closes (chosen) |

Option A mirrors how a human uses a chat interface: each agent response builds on the previous ones. This could be seen as useful context accumulation but introduces a critical problem for adversarial and parallel agent scenarios: **agents become anchored to each other's outputs**.

---

## Decision

**Each `CopilotLLM.call()` creates an independent session** using `async with await client.create_session(...) as session`. The session is destroyed when the `async with` block exits.

Context from prior stages is passed **explicitly** as text in the prompt template (via `_format_prior_decisions()` in `BaseAgent`), not as LLM chat history. Each agent sees:
- Its own `system_prompt` (role definition)  
- A `user_prompt` that includes relevant context from `WorkflowContext.payload` (work item, prior decisions, fix plan, etc.)

```python
async with await client.create_session(
    system_message={"mode": "append", "content": system_prompt},
    model=effective_model,
) as session:
    await session.send_and_wait(user_prompt, timeout=600)
    messages = await session.get_messages()
# session destroyed here — no history leaks to next call
```

---

## Consequences

**Positive:**
- **Adversarial integrity**: `reviewer` and `security_gatekeeper` in the parallel gate cannot be anchored by each other's outputs — they reason independently
- **Reproducibility**: given the same prompt inputs, the same LLM response is expected (no accumulated chat history divergence between runs)
- **Debuggability**: every LLM call is a self-contained `(system_prompt, user_prompt) → response` tuple — fully logged and replayable
- **Parallel safety**: `asyncio.gather()` can fire multiple sessions simultaneously with no shared state

**Negative:**
- Each call starts a cold 2-turn conversation — no incremental context accumulation
- For multi-round agents (feedback loops), the prior round's reasoning must be re-injected via `_format_prior_decisions()` — slightly larger prompts
- Startup overhead per call (~100ms for session creation, excluded from `latency_ms` reported)

**Explicitly rejected:**
- Persistent session per pipeline run: would contaminate adversarial review with groupthink
- Shared `messages=[]` history: would prevent parallel agent execution

**Note on `_format_prior_decisions()`:**
This helper in `BaseAgent` serializes prior `AgentDecision` objects into text and injects them into the user prompt. This is the designed mechanism for cross-agent context passing — it is explicit, auditable, and token-bounded.
