# Conductor Mocks

Use mocks instead of real APIs during development and testing.

## Structure

### `api-responses/`
Mock API responses (JSON files):
- **ado_defect.json** — Azure DevOps defect response
- **ado_user_story.json** — Azure DevOps user story response
- **snyk_findings.json** — Snyk vulnerability findings
- **sonar_findings.json** — SonarQube code quality findings
- **blackduck_findings.json** — BlackDuck license findings

### `agents/`
Mock agent implementations:
- **mock_snyk_agent.py** — Returns mock Snyk findings
- **mock_ado_agent.py** — Returns mock ADO items
- **mock_github_agent.py** — Returns mock GitHub data
- **mock_sonar_agent.py** — Returns mock SonarQube data

### `github/`
Mock GitHub API responses:
- **github_repos.json** — Repository listing
- **github_prs.json** — Pull request data
- **github_issues.json** — Issue data
- **github_users.json** — User data

## Usage

Toggle mock mode in your agent:

```python
class SnykAgent:
    def __init__(self, use_mock=True):
        self.use_mock = use_mock
    
    async def run(self, context):
        if self.use_mock:
            return load_mock("mocks/api-responses/snyk_findings.json")
        else:
            return await self.call_snyk_api()
```

## Adding Mocks

1. Create mock JSON file in `api-responses/` or `github/`
2. Base on real API response format
3. Include realistic data for testing
4. Update agent to check `use_mock=True`

See samples/projects/ for examples using mocks.
