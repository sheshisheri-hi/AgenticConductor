## Finding Details
- **Source:** $source
- **CVE:** $cve_id
- **Package:** $package v$package_version
- **Severity:** $severity
- **Title:** $title
- **Description:** $description

> **NOTE:** If Source is `ado`, `github`, `jira`, or `linear` and CVE is `N/A` or empty, this is a **work item (Mode B)**. Perform architectural security review — do NOT treat it as a miscategorized vulnerability. Never set `requires_human: true` solely because there is no CVE to analyze.

## Repository Context
- **Repo:** $repo_name
- **Tech Stack:** $tech_stack
- **Affected Files:** $affected_files

## Source File Content
$source_files

## Prior Decisions
$prior_decisions

## Tool Findings
$tool_findings

Analyze this finding and produce your security assessment.