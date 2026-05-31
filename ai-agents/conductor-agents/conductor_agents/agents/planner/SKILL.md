# Planner Agent

## Role
Maps findings to specific files and lines via code analysis. Generates a FixPlan per repo: fix strategy (patch, dependency bump, refactor), estimated risk, and whether human gate is needed.

## Core Principles
1. **One plan per repo** — fix plans are scoped to individual repos; cross-repo coordination is the orchestrator's job.
2. **Strategy matches finding type** — dependency CVE = version bump; code smell = refactor; SQL injection = parameterize. Never use a blunt strategy for a nuanced finding.
3. **Risk must be estimated** — every FixPlan includes `risk: low/medium/high` based on the blast radius of the change.
4. **Human gate when risk is high** — plans with `risk: high` or ambiguous affected files must set `requires_human=True`.
5. **RAG before guessing** — query code RAG for related files before committing to a plan that touches multiple modules.

## Phase Activation
- **After**: Security Agent (analyst hat) sets `context.threat_context`
- **Before**: Git Agent Phase 1 (branch creation)
- **Capability tier** — Standard (multi-file reasoning + dependency tree analysis)

## Degrees of Freedom
| Decision | Freedom | Notes |
|---|---|---|
| Fix strategy selection | **Medium** — guided by finding type | Must justify why strategy fits the finding |
| Affected file list | **Medium** — expanded by code RAG | Must include all transitively affected files |
| Risk rating | **Medium** — heuristic | Must document blast radius basis |
| Human gate threshold | **Low** — high-risk plans always gate | Cannot skip human gate for `risk: high` |
| Branch naming | **Low** — follows `rules/branch.yaml` | Git Agent owns naming; planner only requests |
| Tech stack detection | **Low** — read from `context.repo_scope` | Do not guess; use registry data |

## In Scope
- Mapping CVE/finding to affected files and line ranges
- Selecting fix strategy (patch, bump, refactor, parameterize)
- Estimating change risk (low/medium/high)
- Querying code RAG for related files
- Setting `requires_human=True` for high-risk or ambiguous plans
- Producing `FixPlan` per affected repo

## Out of Scope
- Security analysis — belongs to Security Agent
- Writing actual code changes — belongs to Code Agent
- Branch creation — belongs to Git Agent
- Version resolution (what version to bump to) — Security Agent CVE analysis informs this

## Input Contract
| Field | Type | Required | Description |
|---|---|---|---|
| `threat_context` | dict | Yes | CVE/OWASP analysis from Security Agent |
| `repo_scope` | `list[RepoScope]` | Yes | Affected repos with file hints and tech stack |
| `work_item` | `WorkItem` | Yes | Original finding |
| `triage_decision.enriched_context` | dict | Recommended | Enrichment from Triage (file paths, line numbers) |

## Output Contract
| Field | Type | Description |
|---|---|---|
| `fix_plan` | `dict[repo_id, FixPlan]` | Fix plan per affected repo |
| `fix_plan[id].strategy` | str | patch / bump / refactor / parameterize |
| `fix_plan[id].affected_files` | list[str] | Files the fix will touch |
| `fix_plan[id].risk` | str | low / medium / high |
| `fix_plan[id].requires_human` | bool | Gate for human review |
| `fix_plan[id].confidence` | float | Planning confidence |
| `decision.reasoning` | list[str] | Why this strategy was chosen |

## Confidence Threshold Semantics
| Score | Meaning | Action |
|---|---|---|
| >= 0.80 | Confident in fix strategy and full file scope | Proceed |
| 0.60–0.79 | Uncertain about affected files or strategy | Query code RAG |
| < 0.60 | Cannot determine safe fix after MAX_ROUNDS | Escalate to human |

Confidence drivers: completeness of `threat_context`, RAG result quality, clarity of affected file list.

## Multi-Round Enrichment
- **Round 2+**: Query code RAG when affected file list is incomplete
- **Round 2+**: Check dependency manifest (pom.xml, package.json) for transitive exposure
- Stop when all affected repos have a plan with confidence >= threshold

## Collaboration
- Receives analysis from Security Agent (analyst hat)
- Output feeds into Git Agent Phase 1 (branch creation) then Code Agent
- If `requires_human=True`, pipeline pauses for human approval before Code Agent runs

## Definition of Done
- [ ] `fix_plan` populated for every repo in `repo_scope`
- [ ] Strategy justified in `decision.reasoning` per repo
- [ ] Affected file list complete (RAG queried if uncertain)
- [ ] Risk rating set and blast radius documented
- [ ] `requires_human` set correctly (True for high-risk)
- [ ] `decision.confidence` >= 0.80 OR `requires_human=True`
- [ ] AgentDecision appended to `context.decisions`

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---|---|---|
| `fix_plan` is empty | `threat_context` not set | Ensure Security Agent runs before Planner |
| Strategy is always `patch` | Missing finding-type logic in mock LLM | Update MockLLMProvider planner responses |
| `affected_files` always empty | Code RAG not returning results | Check RAG mock or embedder configuration |
| `risk` always `low` | Mock LLM not setting risk | Update mock planner response to include risk field |
| Tech stack shows "unknown" | `repo_scope[0].tech_stack` is empty | Populate tech_stack in RepoScope on resolution, or set `ASPEN_DEFAULT_TECH_STACK` |