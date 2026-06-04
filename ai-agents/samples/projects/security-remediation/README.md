# Security Remediation Conductor Sample

**Time to build:** ~12 hours  
**Level:** Intermediate  
**Purpose:** Demonstrate a production-style security scanning pipeline with token scrubbing and validated remediation plans.

---

## What This Pipeline Does

This sample walks a repository through a realistic remediation flow:

1. Load `conductor.json`
2. Build repository context (`owner`, `repo`, `branch`)
3. Parse a mock Snyk response into findings
4. Analyze each finding with deterministic pattern matching
5. Generate fix instructions with `@validated_agent` output validation
6. Prepare GitHub issue bodies without making outbound API calls
7. Log every step to console and `logs/project.log`

The sample is intentionally stubbed so it is safe to run locally without credentials.

---

## Why It Matters

### Token scrubbing prevents leaks

The workflow adds mock Snyk and GitHub tokens to the runtime context, then logs that context. A `TokenScrubber` from `conductor_core.secrets` is attached to the logger, so secrets are redacted before they ever reach the console or the file log.

This mirrors the consumer-showcase security posture: runtime telemetry is useful only if it is safe to persist.

### Schema validation prevents bad outputs

The `remediation_plan` agent is decorated with `@validated_agent`. In a full install, Conductor uses Pydantic-backed validation. In this sample, a lightweight fallback keeps the project runnable even when optional dependencies are not installed.

This guards the rest of the pipeline from malformed fix plans and documents the contract expected by downstream systems.

---

## File Structure

```
security-remediation/
├── conductor.json
├── main.py
├── agents/
│   ├── snyk_triage.py
│   ├── code_analyzer.py
│   ├── remediation_plan.py
│   └── github_reporter.py
├── logs/                 # created on first run
└── README.md
```

---

## Run It

```bash
cd security-remediation

python main.py --plan
python main.py
python main.py --owner acme --repo checkout-api --branch release/2026.06
python main.py --severity-threshold critical
python main.py --help
```

### Example output

```text
Conductor: security-remediation v1.0.0
Completed 3 finding(s).
Validated plans: 3
GitHub issue previews: 3
```

---

## Running Against Different Repositories

The sample never clones or scans a real repository. Instead, it uses repository metadata to show how the orchestration would vary per target:

```bash
python main.py --owner my-org --repo billing-api --branch hotfix/cve-2026-0042
```

That metadata flows into:

- the Snyk triage context
- remediation plan audit data
- generated GitHub issue titles and bodies
- scrubbed logs

---

## Extending the Sample

To turn this into a richer Phase 4 showcase:

1. Replace the embedded Snyk fixture with `mocks/github/snyk_response.json` or a real Snyk client.
2. Swap the pattern-matching analyzer with an LLM-backed security reviewer.
3. Publish issue previews through a real GitHub integration after human approval.
4. Add dependency verification using `conductor_core.supply_chain.dependencies`.
5. Persist run state into SQLite the way `consumer-showcase` does.

---

## Connection to consumer-showcase

This sample intentionally mirrors the production themes in `consumer-showcase`:

- secure logging
- human approval gates
- deterministic stub execution
- structured outputs for downstream automation
- clear separation between triage, analysis, planning, and reporting

Use this sample when you want a compact teaching artifact before moving to the full security-remediation consumer.
