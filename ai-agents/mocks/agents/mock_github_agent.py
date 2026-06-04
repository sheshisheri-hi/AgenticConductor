"""Mock GitHub Agent.

Simulates GitHub REST API for repositories, pull requests, and issues.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List


def mock_github_repos(owner: str = "conductor-team") -> Dict[str, Any]:
    """Simulate GitHub repos list.
    
    Real integration would:
        - Call https://api.github.com/users/{owner}/repos
        - Use GitHub token (would be scrubbed by TokenScrubber)
        - Support pagination
        - Handle rate limiting (60 req/hr without token, 6000 with)
    """
    
    repos: List[Dict[str, Any]] = [
        {
            "name": "conductor-framework",
            "description": "Multi-agent LLM orchestration with production security",
            "url": f"https://github.com/{owner}/conductor-framework",
            "stars": 1250,
            "forks": 89,
            "created_at": "2024-01-10",
            "updated_at": "2024-06-03",
            "language": "Python",
            "topics": ["orchestration", "llm", "multi-agent", "security"],
        },
        {
            "name": "security-remediation-agent",
            "description": "Autonomous security issue remediation with Snyk integration",
            "url": f"https://github.com/{owner}/security-remediation-agent",
            "stars": 456,
            "forks": 34,
            "created_at": "2024-02-15",
            "updated_at": "2024-06-01",
            "language": "Python",
            "topics": ["security", "remediation", "snyk"],
        },
    ]
    
    return {
        "owner": owner,
        "repos": repos,
        "total_count": len(repos),
    }


def mock_github_prs(repo: str, owner: str = "conductor-team") -> Dict[str, Any]:
    """Simulate GitHub pull requests."""
    
    prs: List[Dict[str, Any]] = [
        {
            "number": 156,
            "title": "Add mTLS support for A2A communication",
            "author": "alice-dev",
            "state": "open",
            "created_at": "2024-05-28",
            "updated_at": "2024-06-03",
            "changed_files": 12,
            "additions": 450,
            "deletions": 85,
            "description": "Implements certificate-based authentication for agent-to-agent calls",
            "labels": ["enhancement", "security", "sprint-10"],
        },
        {
            "number": 155,
            "title": "Implement TokenScrubber for log sanitization",
            "author": "bob-security",
            "state": "closed",
            "created_at": "2024-05-15",
            "updated_at": "2024-05-27",
            "changed_files": 8,
            "additions": 320,
            "deletions": 45,
            "description": "Prevents accidental secret leakage in logs",
            "labels": ["security", "bug-fix", "sprint-9"],
        },
    ]
    
    return {
        "owner": owner,
        "repo": repo,
        "pull_requests": prs,
        "open_count": 1,
        "closed_count": 1,
    }


def mock_github_issues(repo: str, owner: str = "conductor-team") -> Dict[str, Any]:
    """Simulate GitHub issues."""
    
    issues: List[Dict[str, Any]] = [
        {
            "number": 201,
            "title": "Consider adding distributed tracing",
            "author": "carol-ops",
            "state": "open",
            "created_at": "2024-06-01",
            "updated_at": "2024-06-02",
            "comments_count": 3,
            "labels": ["enhancement", "observability"],
            "body": "Add support for OpenTelemetry to trace agent calls across services",
        },
        {
            "number": 200,
            "title": "[Security] Add rate limiting to A2A server",
            "author": "dave-security",
            "state": "open",
            "created_at": "2024-05-30",
            "updated_at": "2024-06-03",
            "comments_count": 5,
            "labels": ["security", "high-priority"],
            "body": "Prevent DDoS attacks on HTTP A2A endpoints",
        },
        {
            "number": 199,
            "title": "Update documentation for Phase 4",
            "author": "eve-docs",
            "state": "open",
            "created_at": "2024-05-25",
            "updated_at": "2024-06-01",
            "comments_count": 2,
            "labels": ["documentation"],
            "body": "Add guides for new samples and mocks",
        },
    ]
    
    return {
        "owner": owner,
        "repo": repo,
        "issues": issues,
        "open_count": 3,
        "closed_count": 0,
    }


def mock_github_users() -> Dict[str, Any]:
    """Simulate GitHub users."""
    
    users = [
        {
            "login": "alice-dev",
            "name": "Alice Johnson",
            "avatar_url": "https://avatars.githubusercontent.com/u/...",
            "profile_url": "https://github.com/alice-dev",
            "public_repos": 34,
            "followers": 250,
            "following": 45,
            "bio": "Full-stack developer, security enthusiast",
        },
        {
            "login": "bob-security",
            "name": "Bob Smith",
            "avatar_url": "https://avatars.githubusercontent.com/u/...",
            "profile_url": "https://github.com/bob-security",
            "public_repos": 12,
            "followers": 180,
            "following": 60,
            "bio": "Security engineer, penetration tester",
        },
        {
            "login": "carol-ops",
            "name": "Carol White",
            "avatar_url": "https://avatars.githubusercontent.com/u/...",
            "profile_url": "https://github.com/carol-ops",
            "public_repos": 28,
            "followers": 320,
            "following": 85,
            "bio": "DevOps engineer, Kubernetes expert",
        },
    ]
    
    return {
        "users": users,
        "total_count": len(users),
    }


if __name__ == "__main__":
    print(json.dumps(mock_github_repos(), indent=2))
