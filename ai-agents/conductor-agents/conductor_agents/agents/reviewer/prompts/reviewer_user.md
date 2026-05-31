## Finding
$finding_summary

## Fix Plan
$fix_plan

## LINE COUNT REGRESSION CHECK (pre-computed — trust these numbers)
$line_count_check

Any file marked "REGRESSION RISK" MUST be blocked unless the fix plan explicitly asked to remove that code.

## Code Changes (Round $round)
$code_changes

## Prior Security Analysis
$security_analysis

## Prior Concerns Sent to Coder
$prior_concerns

## Tool Results
$tool_findings

Review this fix for correctness and quality.

**First, check the LINE COUNT REGRESSION CHECK table above.** Any file with "REGRESSION RISK" means the submitted content is dramatically shorter than the original. Block it and state exactly what was removed. Do not rely on reading the raw code_changes to count lines — use the pre-computed table.

If "Prior Concerns Sent to Coder" is not "None", check whether each concern was addressed before raising new ones.