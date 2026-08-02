## Finding
$finding_summary

## Analysis Context
$analysis_context

## Repository
- **Repo:** $repo_name
- **Tech Stack:** $tech_stack
- **Default Branch:** $default_branch

## Related Code (from RAG)
$related_code

## RCA Context (product terms + similar defects + candidate repos)
$rca_context

## Prior Decisions
$prior_decisions

Create a fix plan for this finding.
Cite similar historical defects and resolved product terms in reasoning/evidence.
Only propose changes inside candidate_repos. If none, set requires_human=true.

**CRITICAL: Respond ONLY with the JSON object. Do NOT write prose, markdown, or any explanation outside the JSON. Your entire response must be parseable by `json.loads()`.**
