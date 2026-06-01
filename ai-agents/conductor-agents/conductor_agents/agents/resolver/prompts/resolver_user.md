## Resolution Mode: $resolution_mode

## Finding
- **Title / Package:** $package
- **Version / CVE:** $package_version / $cve_id
- **Description:** $description
- **File:** $file_path (line $line_number)
- **Repo:** $repo_registry

## Dependency Manifests (for dependency_scan mode)
$dependency_manifests

## File Contents (for code_level mode)
$files_block

## Prior Decisions
$prior_decisions

## Round $round

Identify which repos and files are affected. For code_level mode, if file content is provided, confirm the vulnerability is present and proceed — do not escalate unless the content is genuinely unclear.

**CRITICAL: Respond ONLY with the JSON object. Do NOT write prose, markdown, or any explanation outside the JSON. Your entire response must be parseable by `json.loads()`.**