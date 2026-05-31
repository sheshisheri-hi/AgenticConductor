# Feedback Agent

## Role
Updates origin systems (ADO ticket, Snyk finding, Sonar annotation) with Scribe Agent ticket update body. Pure delivery — never generates prose.

## Core Principles
1. **Verbatim delivery** — uses Scribe ticket update body exactly as written. No editing, no summarizing.
2. **All sources updated** — every source system referenced in `work_item` gets an update.
3. **Idempotent** — posting the same update twice should not create duplicate comments. Check before posting.
4. **Failure is non-blocking** — if a notification fails (e.g. ADO token expired), log the error and continue. Do not block the pipeline.

## Phase Activation
- **After**: Git Agent Phase 2 (PRs created)
- **Capability tier** — None (pure delivery; no LLM)

## Degrees of Freedom
| Decision | Freedom | Notes |
|---|---|---|
| Update content | **Low** — Scribe output verbatim | Never edit prose |
| Which systems to update | **Low** — all sources in `work_item.source` | Do not skip any source system |
| Failure handling | **Medium** — log and continue | Do not block pipeline on delivery failure |
| Update format | **Low** — source system API determines this | Use native API format for each source |

## In Scope
- Posting `scribe_output.ticket_updates` to ADO, Snyk, SonarQube APIs
- Confirming delivery success per source system
- Logging delivery failures without blocking pipeline

## Out of Scope
- Generating ticket update prose — belongs to Scribe Agent
- Sending Slack/Teams notifications — belongs to Notify Agent
- Closing tickets — that is a human decision

## Input Contract
| Field | Type | Required | Description |
|---|---|---|---|
| `scribe_output.ticket_updates` | `dict[source, str]` | Yes | Update text per source system |
| `work_item.source` | str | Yes | Which source systems to update |
| `work_item.id` | str | Yes | Finding ID for update targeting |
| `pr_map` | dict | Yes | PR URLs to include in updates |

## Output Contract
| Field | Type | Description |
|---|---|---|
| `decision.action` | str | "proceed" (always — failure is non-blocking) |
| `decision.reasoning` | list[str] | Delivery confirmation or failure log per source |

## Definition of Done
- [ ] Update posted to every source system in `work_item.source`
- [ ] PR URL included in each update
- [ ] Delivery failures logged in `decision.reasoning`
- [ ] AgentDecision appended to `context.decisions`

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---|---|---|
| ADO update fails silently | MockNotifyClient not logging | Check MockNotifyClient implementation |
| Update posted multiple times | Idempotency check missing | Add check for existing comments before posting |
| `ticket_updates` is None | Scribe Agent did not run | Check pipeline stage ordering |