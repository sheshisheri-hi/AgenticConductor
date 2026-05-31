# Notify Agent

## Role
Posts campaign summaries to Slack/Teams channels. Pure delivery — never generates prose.

## Core Principles
1. **Verbatim delivery** — uses Scribe campaign summary exactly as written.
2. **Channel routing is configurable** — channel mapping lives in `tools.yaml`, not hardcoded.
3. **Failure is non-blocking** — notification failure never blocks the pipeline.
4. **One summary per campaign** — do not post duplicate notifications for the same campaign.

## Phase Activation
- **After**: Git Agent Phase 2 and Feedback Agent complete
- **Capability tier** — None (pure delivery; no LLM)

## Degrees of Freedom
| Decision | Freedom | Notes |
|---|---|---|
| Summary content | **Low** — Scribe output verbatim | Never edit prose |
| Channel selection | **Low** — from `tools.yaml` config | Do not hardcode channel names |
| Failure handling | **Medium** — log and continue | Do not block pipeline |

## In Scope
- Posting `scribe_output.campaign_summary` to configured Slack/Teams channels
- Including PR URLs from `pr_map` in the notification
- Logging delivery confirmation or failure

## Out of Scope
- Generating notification prose — belongs to Scribe Agent
- Updating source tickets — belongs to Feedback Agent
- Channel routing decisions — configured in `tools.yaml`

## Input Contract
| Field | Type | Required | Description |
|---|---|---|---|
| `scribe_output.campaign_summary` | str | Yes | Campaign summary from Scribe Agent |
| `campaign_id` | str | Yes | For deduplication |
| `pr_map` | dict | Optional | PR URLs to include in notification |

## Output Contract
| Field | Type | Description |
|---|---|---|
| `decision.reasoning` | list[str] | Delivery confirmation or failure log per channel |

## Definition of Done
- [ ] Campaign summary posted to all configured channels in `tools.yaml`
- [ ] PR URLs included in notification body
- [ ] Delivery result logged in `decision.reasoning`
- [ ] AgentDecision appended to `context.decisions`

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---|---|---|
| No notification sent | `scribe_output.campaign_summary` is None | Check Scribe Agent completed |
| Duplicate notifications | Campaign dedup check missing | Add `campaign_id` dedup in MockNotifyClient |
| Wrong channel | `tools.yaml` channel mapping missing | Add `notify.slack_channel` or `notify.teams_channel` to tools.yaml |