"""Mock Snyk Security Scanner Agent.

In production, this would call Snyk API to scan for vulnerabilities.
This mock returns realistic sample vulnerability data for testing.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List


def mock_snyk_scan(project_key: str, repo_url: str = "") -> Dict[str, Any]:
    """Simulate Snyk vulnerability scan.
    
    Args:
        project_key: Project identifier (e.g., "repo-name")
        repo_url: Repository URL (optional, for real integration)
    
    Returns:
        Dict with vulnerabilities, metrics, and scan metadata
    
    Real integration would:
        - Call https://api.snyk.io/v1/projects/{project_id}/issues
        - Use SNYK_TOKEN environment variable for authentication
        - Filter by severity level
        - Integrate with GitHub/GitLab for context
    """
    
    vulnerabilities: List[Dict[str, Any]] = [
        {
            "id": "SNYK-PYTHON-DJANGO-1000001",
            "package": "django",
            "version": "3.0.0",
            "severity": "high",
            "cvss_score": 8.1,
            "title": "Django SQL Injection in ORM",
            "description": "Improper input validation in Django ORM allows SQL injection",
            "published": "2024-01-15",
            "fixed_in": "3.2.0",
            "paths": ["requirements.txt"],
        },
        {
            "id": "SNYK-PYTHON-REQUESTS-1000002",
            "package": "requests",
            "version": "2.25.0",
            "severity": "medium",
            "cvss_score": 5.3,
            "title": "Requests HTTP/2 Connection State Attack",
            "description": "Connection reuse could leak request headers between users",
            "published": "2024-02-20",
            "fixed_in": "2.31.0",
            "paths": ["requirements.txt"],
        },
        {
            "id": "SNYK-PYTHON-PYYAML-1000003",
            "package": "pyyaml",
            "version": "5.3",
            "severity": "high",
            "cvss_score": 9.8,
            "title": "YAML Deserialization Attack",
            "description": "Unsafe YAML loading allows arbitrary code execution",
            "published": "2023-12-01",
            "fixed_in": "6.0.0",
            "paths": ["requirements.txt"],
        },
    ]
    
    return {
        "project": project_key,
        "url": repo_url,
        "vulnerabilities_found": len(vulnerabilities),
        "vulnerabilities": vulnerabilities,
        "severity_breakdown": {
            "critical": 0,
            "high": 2,
            "medium": 1,
            "low": 0,
        },
        "scan_timestamp": datetime.utcnow().isoformat(),
        "scan_duration_seconds": 12.5,
        "recommendation": "Fix 2 high-severity issues before deployment",
    }


def mock_snyk_fix_suggestions(vulnerability_id: str) -> Dict[str, Any]:
    """Get fix suggestions for a specific vulnerability."""
    
    suggestions = {
        "SNYK-PYTHON-DJANGO-1000001": {
            "steps": [
                "Update django from 3.0.0 to 3.2.0 or higher",
                "Run: pip install --upgrade django>=3.2.0",
                "Test your application with new version",
                "Deploy to staging first",
            ],
            "effort": "low",
            "risk": "low",
        },
        "SNYK-PYTHON-REQUESTS-1000002": {
            "steps": [
                "Update requests from 2.25.0 to 2.31.0 or higher",
                "Run: pip install --upgrade requests>=2.31.0",
                "Verify no breaking changes in your code",
            ],
            "effort": "low",
            "risk": "minimal",
        },
        "SNYK-PYTHON-PYYAML-1000003": {
            "steps": [
                "Use safe_load() instead of load() when parsing YAML",
                "Update pyyaml from 5.3 to 6.0.0 or higher",
                "Run: pip install --upgrade pyyaml>=6.0.0",
                "Audit any custom YAML loading code",
            ],
            "effort": "medium",
            "risk": "low",
        },
    }
    
    return suggestions.get(vulnerability_id, {"error": "Unknown vulnerability ID"})


if __name__ == "__main__":
    # Example usage
    result = mock_snyk_scan("my-project", "https://github.com/user/repo")
    print(json.dumps(result, indent=2))
