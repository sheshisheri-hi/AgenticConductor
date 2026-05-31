# Repo Resolver Agent

## Role
Runs only when the source system does not provide a repo (e.g., BlackDuck package-level CVE). Scans dependency manifests across allowlisted repos to find affected repositories.

## Inputs
- PipelineContext with package/CVE info but no repo_name
- Repo registry (allowlisted repos only)

## Outputs
- RepoScope list with confidence per repo

## Collaboration
- Invoked by Triage when repo_name is absent
- Output feeds back into PipelineContext for Analysis Layer