## Fix Plan
$fix_plan

## Current Code (PRESERVE ALL OF THIS)
$current_code

## Target Repository
- **Repo:** $repo_name
- **Branch:** $branch_name
- **Tech Stack:** $tech_stack

## Finding Details
$finding_summary

## Review Feedback (from previous round)
$review_feedback

IMPORTANT: For every file you modify, start from the FULL content shown in "Current Code" above and add only what the fix plan requires. Do not remove, shorten, or simplify any existing code.

You MUST implement EVERY file listed in the Fix Plan's `affected_files` — do not skip any. For new files not shown in "Current Code", write the complete file from scratch. For existing files, start from the full content shown and apply only surgical additions.

YOUR ENTIRE RESPONSE MUST BE VALID JSON. Start your response with `{` and end with `}`. No prose before or after. No markdown. No explanation. Strictly follow this exact structure:

```
{
  "confidence": 0.9,
  "recommendation": "proceed",
  "reasoning": ["implemented X", "modified Y"],
  "evidence": ["file A updated", "file B created"],
  "concerns": [],
  "requires_human": false,
  "code_changes": [
    {
      "file_path": "path/to/File.cs",
      "content": "COMPLETE FILE CONTENT HERE — ALL LINES",
      "change_type": "create|modify",
      "explanation": "what changed and why"
    }
  ]
}
```

The `code_changes` array must contain one entry per file in `affected_files`. If you start writing prose or markdown instead of `{`, your response will be discarded.