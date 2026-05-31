# Git Agent

## Role
Physical gate for all git operations. No LLM, no prompts — pure logic governed by declarative YAML rules. Operates in two phases:
- **Phase 1** (pre-code): Validate allowlist, create branch, set up workspace
- **Phase 2** (post-review): Commit with Scribe message, push, create PR

## Core Principles
1. **Never target protected branches** — master/main/develop are always off-limits for direct writes.
2. **Never merge** — Git Agent only creates PRs. Merge decisions belong to human reviewers.
3. **Rules are code** — all constraints are in `rules/*.yaml`. Never bypass rules in Python logic.
4. **Allowlist is the gate** — Phase 1 fails entirely if the repo is not in the allowlist. No exceptions.
5. **Scribe output is verbatim** — Git Agent uses Scribe commit messages and PR descriptions without modification.

## Phase Activation
- **Phase 1**: After Planner Agent, before Code Agent
- **Phase 2**: After Scribe Agent completes
- **Capability tier** — None (pure rule-based; no LLM)

## Degrees of Freedom
| Decision | Freedom | Notes |
|---|---|---|
| Branch naming | **Low** — follows `rules/branch.yaml` | Format: `aspen/{campaign_id}/{repo_id}` |
| Commit message | **Low** — Scribe output verbatim | Do not edit or summarize |
| PR description | **Low** — Scribe output verbatim | Do not edit or summarize |
| Allowlist check | **Low** — binary pass/fail | No fuzzy matching |
| Push target | **Low** — created branch only | Never force-push to existing branches |
| PR base branch | **Low** — `repo.default_branch` | From `RepoRecord.default_branch` |

## In Scope
- Validating repo is in allowlist (Phase 1)
- Creating campaign branch per `rules/branch.yaml` (Phase 1)
- Setting `context.branch_map[repo_name] = branch_name` (Phase 1)
- Committing changes using Scribe commit message (Phase 2)
- Pushing branch to remote (Phase 2)
- Creating PR with Scribe title and description (Phase 2)
- Setting `context.pr_map[repo_name] = pr_url` (Phase 2)

## Out of Scope
- Generating prose for commits or PRs — belongs to Scribe Agent
- Merging PRs — human reviewers do this
- Writing code — belongs to Code Agent
- Running CI checks — belongs to CI/CD pipeline

## Input Contract — Phase 1
| Field | Type | Required | Description |
|---|---|---|---|
| `repo_scope` | `list[RepoScope]` | Yes | Repos to create branches for |
| `fix_plan` | dict | Yes | Needed to validate risk before branch creation |
| `campaign_id` | str | Yes | For branch naming |

## Input Contract — Phase 2
| Field | Type | Required | Description |
|---|---|---|---|
| `branch_map` | dict | Yes | Branches to commit to (from Phase 1) |
| `code_changes` | dict | Yes | File changes to commit |
| `scribe_output` | `ScribeOutput` | Yes | Commit messages, PR title, PR description |
| `repo_scope` | `list[RepoScope]` | Yes | For PR base branch |

## Output Contract
| Field | Type | Description |
|---|---|---|
| `branch_map` | `dict[repo_name, branch]` | Created branch per repo (Phase 1) |
| `pr_map` | `dict[repo_name, pr_url]` | Created PR URL per repo (Phase 2) |
| `ci_status` | `dict[repo_name, status]` | CI check status after PR creation (Phase 2) |

## Rules
- Never targets master/main directly (`rules/protection.yaml`)
- Never merges — only creates PRs (`rules/pr.yaml`)
- Branch name format: `aspen/{campaign_id}/{repo_id}` (`rules/branch.yaml`)
- Commit format: Conventional Commits (`rules/commit.yaml`)
- Ownership verified before any write (`rules/ownership.yaml`)
- Blocks if any upstream agent confidence < threshold

## Definition of Done
**Phase 1:**
- [ ] Allowlist check passed for all repos in scope
- [ ] Branch created for every repo in `repo_scope`
- [ ] `context.branch_map` populated with all created branches

**Phase 2:**
- [ ] All changes in `code_changes` committed to correct branch
- [ ] Scribe commit messages used verbatim
- [ ] Branch pushed to remote for all repos
- [ ] PR created with Scribe title and description verbatim
- [ ] `context.pr_map` populated with all PR URLs
- [ ] `context.ci_status` populated after PR creation

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---|---|---|
| Phase 1 blocks on allowlist | `repo_name` does not match allowlist key | Check `repo_registry.yaml` entry name |
| Branch already exists | Previous campaign run left branch open | Mock ignores; Live: use `--force-with-lease` |
| `branch_map` empty after Phase 1 | `repo_scope` is None | Check that Repo Resolver ran before Git Agent |
| PR creation fails | `scribe_output` is None | Check Scribe Agent ran and `scribe_output` is set |