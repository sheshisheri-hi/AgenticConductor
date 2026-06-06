"""Mock SonarQube Agent.

Simulates SonarQube REST API for code quality metrics and issues.
"""

import json
from datetime import datetime
from typing import Any, Dict, List


def mock_sonar_metrics(project_key: str) -> Dict[str, Any]:
    """Simulate SonarQube metrics query.
    
    Real integration would:
        - Call https://sonarqube.company.com/api/measures/component
        - Use SonarQube token for authentication
        - Support multiple metrics (ncloc, duplicated_lines, coverage, etc.)
        - Filter by branch
    """
    
    metrics = {
        "ncloc": 12450,  # Non-comment lines of code
        "duplicated_lines_density": 3.2,  # 3.2% duplicated code
        "coverage": 78.5,  # 78.5% test coverage
        "tests": 2340,  # Total tests
        "test_success_density": 99.2,  # 99.2% passing
        "code_smells": 45,  # Code smell violations
        "bugs": 8,  # Bug violations
        "vulnerabilities": 3,  # Security vulnerabilities
        "security_hotspots": 12,  # Security hotspots
        "maintainability_rating": "A",  # A/B/C/D/E
        "reliability_rating": "A",
        "security_rating": "A",
    }
    
    return {
        "project_key": project_key,
        "metrics": metrics,
        "analysis_date": datetime.utcnow().isoformat(),
        "quality_gate": "PASSED",
        "quality_gate_details": {
            "status": "OK",
            "conditions": [
                {"metric": "coverage", "threshold": 80, "actual": 78.5, "status": "WARN"},
                {"metric": "duplicated_lines_density", "threshold": 3.0, "actual": 3.2, "status": "WARN"},
            ],
        },
    }


def mock_sonar_issues(project_key: str) -> Dict[str, Any]:
    """Simulate SonarQube issues query."""
    
    issues: List[Dict[str, Any]] = [
        {
            "key": "AVmxF68gC-Nz1NhPVAV3",
            "type": "BUG",
            "severity": "HIGH",
            "message": "Potential SQL injection vulnerability",
            "component": "src/database/query_builder.py",
            "line": 156,
            "status": "OPEN",
            "creation_date": "2024-05-20",
            "effort_to_fix": "30min",
        },
        {
            "key": "AVmxF68gC-Nz1NhPVAV4",
            "type": "VULNERABILITY",
            "severity": "CRITICAL",
            "message": "Hard-coded credentials detected",
            "component": "src/config/settings.py",
            "line": 42,
            "status": "OPEN",
            "creation_date": "2024-05-18",
            "effort_to_fix": "15min",
        },
        {
            "key": "AVmxF68gC-Nz1NhPVAV5",
            "type": "CODE_SMELL",
            "severity": "MEDIUM",
            "message": "Cognitive complexity is too high (15 > 10)",
            "component": "src/orchestrator/workflow_engine.py",
            "line": 234,
            "status": "OPEN",
            "creation_date": "2024-05-25",
            "effort_to_fix": "1h",
        },
        {
            "key": "AVmxF68gC-Nz1NhPVAV6",
            "type": "SECURITY_HOTSPOT",
            "severity": "MEDIUM",
            "message": "Review this potential security issue",
            "component": "src/api/handlers.py",
            "line": 89,
            "status": "REVIEW",
            "creation_date": "2024-05-22",
            "effort_to_fix": "20min",
        },
    ]
    
    return {
        "project_key": project_key,
        "issues": issues,
        "total_count": len(issues),
        "by_severity": {
            "CRITICAL": 1,
            "HIGH": 1,
            "MEDIUM": 2,
            "LOW": 0,
            "INFO": 0,
        },
        "by_type": {
            "BUG": 1,
            "VULNERABILITY": 1,
            "CODE_SMELL": 1,
            "SECURITY_HOTSPOT": 1,
        },
        "by_status": {
            "OPEN": 3,
            "CONFIRMED": 0,
            "REVIEW": 1,
            "RESOLVED": 0,
            "CLOSED": 0,
        },
    }


def mock_sonar_hotspots(project_key: str) -> Dict[str, Any]:
    """Simulate SonarQube security hotspots."""
    
    hotspots = [
        {
            "key": "AX7dLPvLqm...",
            "component": "src/auth/jwt_handler.py",
            "line": 45,
            "message": "Verify that JWT validation is secure",
            "status": "TO_REVIEW",
            "creation_date": "2024-05-28",
        },
        {
            "key": "AX7dLPvLqm...",
            "component": "src/db/connection.py",
            "line": 78,
            "message": "Review database connection security",
            "status": "TO_REVIEW",
            "creation_date": "2024-06-01",
        },
    ]
    
    return {
        "project_key": project_key,
        "security_hotspots": hotspots,
        "total_count": len(hotspots),
        "to_review": len(hotspots),
        "reviewed": 0,
    }


if __name__ == "__main__":
    print(json.dumps(mock_sonar_metrics("my-project"), indent=2))
