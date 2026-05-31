# ADR-005: Parallel Runners via asyncio.gather (Not Group Chat)

**Status:** Accepted  
**Date:** 2026-05-20  

---

## Context

The original Aspen-Sentinel pipeline ran all agents sequentially. Post-code review involved a `SecurityAgent` and a `ReviewerAgent` running one-after-the-other on the same code diff. The second agent could be anchored by the first's output (if context was passed naively).

Two multi-agent execution patterns were considered:

| Pattern | Description |
|---------|-------------|
| A | **Group chat** — agents see each other's messages in a shared thread; take turns; moderator decides consensus (AutoGen, LangChain Multi-Agent) |
| B | **Parallel runners** — agents fire simultaneously with no inter-agent visibility; outputs are merged by a strategy function (chosen) |

Pattern A (group chat) is relevant when agents need to _debate_ — where the second agent's quality improves by reading the first. This is the planned Phase D for code fix panels (`GroupChatRunner`).

Pattern B is correct for **review gates** — where the adversarial property requires agents to reason independently.

---

## Decision

`ParallelRunner.run()` uses `asyncio.gather(*tasks)` to fire all agents simultaneously. No agent can see another's output before returning its decision. Three merge strategies are supported:

| Strategy | Behavior |
|----------|----------|
| `all_must_pass` | Any `block` recommendation → gate blocks |
| `majority_vote` | Strictly > 50% must recommend `proceed`; ties block |
| `first_pass` | First non-blocking decision wins; subsequent tasks cancelled |

The merge strategy is declared in the workflow YAML, not in code:

```yaml
parallel_groups:
  - trigger_stage: review_gate
    agents: [security_gatekeeper, reviewer]
    merge_strategy: all_must_pass
    next_stage_on_pass: document
    next_stage_on_block: terminal
```

---

## Consequences

**Positive:**
- **Adversarial integrity**: `security_gatekeeper` and `reviewer` cannot groupthink — one cannot anchor the other
- **Wall-clock latency**: parallel agents run in `max(t_a, t_b)` time instead of `t_a + t_b`; in practice ~50% wall-clock reduction at the review gate
- **Deterministic merge**: merge strategy is explicit in YAML — behaviour is transparent and auditable
- **Testable without LLM**: `ParallelRunner` is tested with mock `BaseAgent` subclasses; 16 unit tests covering all strategies and edge cases

**Negative:**
- Agents cannot challenge each other's reasoning in real time (no debate loop)
- `majority_vote` with an even number of agents ties-block — caller must be aware
- `first_pass` cancels remaining tasks after first non-block — may skip useful signal

**Planned:**
- `GroupChatRunner` (Phase D) will implement debate-style multi-agent panels for code fix, using a separate YAML `group_chats:` section — it will not replace `parallel_groups:` but complement it for the `code` stage

---

## References

- `conductor-core/conductor_core/runners/parallel.py` — implementation
- `conductor-core/tests/unit/test_parallel_runner.py` — 16 unit tests
- `consumer-showcase/config/workflow_adversarial.yaml` — live usage
- `consumer-showcase/config/workflow_execute.yaml` — live usage (parallel at `review_gate` and `notify_feedback`)
