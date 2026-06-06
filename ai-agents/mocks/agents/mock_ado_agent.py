"""Mock Azure DevOps Agent.

Simulates Azure DevOps REST API responses for work items, sprints, and team data.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List


def mock_ado_work_items(project: str, team: str = "Default") -> Dict[str, Any]:
    """Simulate ADO work items query.
    
    Real integration would:
        - Call https://dev.azure.com/{org}/{project}/_apis/wit/workitems
        - Use PAT (Personal Access Token) for authentication
        - Support WIQL queries
        - Filter by type, state, assigned user
    """
    
    work_items: List[Dict[str, Any]] = [
        {
            "id": 1001,
            "title": "Fix authentication token validation",
            "type": "Bug",
            "state": "Active",
            "priority": 1,
            "assigned_to": "alice@company.com",
            "created_date": "2024-05-15",
            "effort_estimate": 8,
            "sprint": "Sprint 24",
            "area_path": f"{project}/Backend",
        },
        {
            "id": 1002,
            "title": "Implement multi-factor authentication",
            "type": "Feature",
            "state": "New",
            "priority": 2,
            "assigned_to": "bob@company.com",
            "created_date": "2024-05-18",
            "effort_estimate": 21,
            "sprint": "Sprint 25",
            "area_path": f"{project}/Security",
        },
        {
            "id": 1003,
            "title": "Performance optimization for search",
            "type": "Task",
            "state": "Active",
            "priority": 3,
            "assigned_to": "carol@company.com",
            "created_date": "2024-05-10",
            "effort_estimate": 13,
            "sprint": "Sprint 24",
            "area_path": f"{project}/Infrastructure",
        },
        {
            "id": 1004,
            "title": "Add support for SSO integration",
            "type": "Feature",
            "state": "Resolved",
            "priority": 2,
            "assigned_to": "dave@company.com",
            "created_date": "2024-04-20",
            "effort_estimate": 34,
            "sprint": "Sprint 23",
            "area_path": f"{project}/Backend",
        },
    ]
    
    return {
        "project": project,
        "team": team,
        "work_items": work_items,
        "total_count": len(work_items),
        "by_state": {
            "New": 1,
            "Active": 2,
            "Resolved": 1,
            "Closed": 0,
        },
        "by_type": {
            "Bug": 1,
            "Feature": 2,
            "Task": 1,
        },
    }


def mock_ado_sprints(project: str) -> Dict[str, Any]:
    """Simulate ADO sprints query."""
    
    sprints = [
        {
            "id": "sprint-24",
            "name": "Sprint 24",
            "start_date": "2024-05-13",
            "end_date": "2024-05-27",
            "status": "active",
            "capacity": 100,
            "committed_effort": 95,
        },
        {
            "id": "sprint-25",
            "name": "Sprint 25",
            "start_date": "2024-05-28",
            "end_date": "2024-06-10",
            "status": "future",
            "capacity": 100,
            "committed_effort": 45,
        },
    ]
    
    return {
        "project": project,
        "sprints": sprints,
        "active_sprint": "sprint-24",
    }


def mock_ado_team(project: str) -> Dict[str, Any]:
    """Simulate ADO team members."""
    
    members = [
        {
            "name": "Alice Johnson",
            "email": "alice@company.com",
            "role": "Senior Developer",
            "active": True,
        },
        {
            "name": "Bob Smith",
            "email": "bob@company.com",
            "role": "Backend Developer",
            "active": True,
        },
        {
            "name": "Carol White",
            "email": "carol@company.com",
            "role": "DevOps Engineer",
            "active": True,
        },
        {
            "name": "Dave Brown",
            "email": "dave@company.com",
            "role": "Security Engineer",
            "active": True,
        },
    ]
    
    return {
        "project": project,
        "team_count": len(members),
        "members": members,
    }


if __name__ == "__main__":
    print(json.dumps(mock_ado_work_items("MyProject"), indent=2))
