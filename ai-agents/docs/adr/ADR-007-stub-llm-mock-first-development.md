# ADR-007: StubLLM Mock-First Development Pattern

**Status:** Accepted  
**Date:** 2026-05-01  
**Mirrors:** Original Coding-Agent `docs/decisions/ADR-001-mock-first-provider-pattern.md`

---

## Context

Running `./dev.sh demo snyk` should work with zero GitHub credentials, zero network access, and zero LLM spend. During development and CI, all unit tests and demo smoke tests must run without a Copilot subscription.

The framework also needs to be testable without a real LLM for:
- Unit tests of orchestrator routing logic
- Unit tests of `ParallelRunner` merge strategies
- Unit tests of `FilterEngine` and `RouterEngine`
- CI pipeline (no secrets in standard PRs)

---

## Decision

`ILLMProvider` is a protocol with a single method `call(prompt: LLMPrompt) -> LLMResponse`. All agents accept `ILLMProvider` at construction — never a concrete class.

`StubLLM` is the mock implementation. It returns deterministic, configurable responses without any network call:

```python
class StubLLM:
    def __init__(self, responses: dict[str, str] | None = None): ...
    async def call(self, prompt: LLMPrompt) -> LLMResponse:
        # Returns agent-name-matched response from self._responses
        # Falls back to a generic "proceed with 0.90 confidence" stub
```

`--mode mock` (or `CONDUCTOR_MODE=mock`) selects `StubLLM` in `consumer-showcase/main.py`. `--mode sample` (or `CONDUCTOR_MODE=sample`) selects `CopilotLLM`.

The `consumer-showcase` ships with a `fixtures/stub_responses.json` file that maps agent names to canned responses with realistic confidence scores, recommendations, and token counts.

---

## Consequences

**Positive:**
- `./dev.sh demo snyk` works with zero credentials — first-run experience is always successful
- All 142 unit tests run in CI without any GitHub token or network access
- `StubLLM` latency is ~0ms — full pipeline runs in <100ms in mock mode (vs 3–25 seconds with real LLM)
- Stub responses can be tuned to test specific routing paths (e.g. a stub that returns `block` for the security_gatekeeper only)
- `ParallelRunner` tests inject `StubLLM` agents directly — test all 3 merge strategies without network

**Negative:**
- Stub responses are static — they don't test prompt quality or actual model behavior
- A passing mock demo does not guarantee sample mode works (different failure modes)
- `stub_responses.json` must be updated when agent prompts change substantially

**Verification rule:**
`./dev.sh demo-all` (mock) must pass before any PR merge. `./dev.sh sample-all` (real LLM) must be run manually before tagging a release.

---

## Interface Contract

```python
class ILLMProvider(Protocol):
    async def call(self, prompt: LLMPrompt) -> LLMResponse: ...
    async def verify_access(self) -> bool: ...

# Both implement ILLMProvider:
# - StubLLM (conductor-core — no external deps)
# - CopilotLLM (conductor-integrations[copilot] — requires github-copilot-sdk)
```

---

## References

- `conductor-core/conductor_core/providers/stub.py` — StubLLM implementation
- `conductor-core/conductor_core/interfaces.py` — ILLMProvider protocol
- `conductor-integrations/conductor_integrations/llm/copilot.py` — CopilotLLM
- `consumer-showcase/main.py` — mode dispatch (`--mode mock` vs `--mode sample`)
- `conductor-integrations/tests/unit/test_copilot_llm.py` — 18 unit tests using StubLLM patterns
