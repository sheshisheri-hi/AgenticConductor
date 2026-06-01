# ADR-003: GitHub Copilot SDK over Direct OpenAI API

**Status:** Accepted  
**Date:** 2026-05-15  
**Supersedes:** Original Coding-Agent `docs/adr/ADR-001-llm-integration-pattern.md`

---

## Context

The framework needs an LLM provider. Two options exist:

| Option | Auth | Cost | Available models |
|--------|------|------|-----------------|
| A | OpenAI API key (`OPENAI_API_KEY`) | Pay-per-token | gpt-4o, gpt-4-turbo, etc. |
| B | GitHub Copilot SDK (`github-copilot-sdk`) | Covered by Copilot subscription | gpt-4.1, gpt-5.x, claude-sonnet-4.x, etc. |

The original repo used the GitHub Copilot SDK. During a mid-session regression, the default model was incorrectly set to `gpt-4o` — which is **not available via the Copilot SDK** (only via direct OpenAI API). This was discovered when `Model "gpt-4o" is not available` was returned at runtime. Available models were confirmed via `client.list_models()`.

---

## Decision

**Use `github-copilot-sdk` exclusively.** The default model is `gpt-4.1`.

The LLM provider is injected via `ILLMProvider` — the framework never imports `CopilotLLM` directly. `conductor-integrations[copilot]` is the optional extras group that installs the SDK.

Available models confirmed via `client.list_models()` (as of 2026-05):
```
auto, gpt-4.1, gpt-5.2, gpt-5.4, claude-sonnet-4.5, claude-sonnet-4.6, claude-haiku-4.5, ...
```

`gpt-4o` is **not** in this list — it is only available via direct OpenAI API key.

---

## Consequences

**Positive:**
- No OpenAI billing account or API key needed — works under any active GitHub Copilot subscription
- `CONDUCTOR_LLM_MODEL` env var selects the model at runtime without code changes
- `CONDUCTOR_REVIEWER_MODEL` can point to a different model for adversarial review (e.g. `claude-sonnet-4.6`)
- Token resolution order is explicit: `CONDUCTOR_GITHUB_TOKEN` → `GITHUB_COPILOT_TOKEN` → `COPILOT_GITHUB_TOKEN` → `GITHUB_TOKEN`
- `conductor check` validates access before any LLM spend

**Negative:**
- Copilot SDK wraps a local CLI subprocess (~1–2s cold start)
- SDK is in public preview — API may change (same caveat as original ADR-001)
- `gpt-4o` name must **never** be used as a default — it resolves to a different model family via Copilot SDK

**Guard:**
- Default model is `gpt-4.1` hardcoded in `_DEFAULT_MODEL` in `copilot.py` and in `settings.py`
- Any future model change must be verified via `client.list_models()` first

---

## Migration Trigger

Revisit when GitHub Copilot SDK exits public preview or when multi-provider support (Azure OpenAI + Copilot) is required.
