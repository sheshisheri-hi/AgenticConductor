"""Integration tests for A2A Server HTTP transport."""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from conductor_core.a2a.server.agent_server import AgentServer, AgentServerStatus
from conductor_core.a2a.server.http_transport import create_a2a_app
from fastapi.testclient import TestClient


@pytest.fixture
def sample_agent_callable():
    """Create a sample agent callable for testing."""
    async def mock_agent(context: dict, query: str = "", **kwargs):
        """Mock agent that echoes input."""
        return {
            "agent": "mock_agent",
            "query": query,
            "context_keys": list(context.keys()),
            "status": "success",
        }
    return mock_agent


@pytest.fixture
async def agent_server(sample_agent_callable):
    """Create a test agent server."""
    server = AgentServer(
        agent_id="test_agent",
        agent_name="TestAgent",
        agent_callable=sample_agent_callable,
        capabilities=["query", "analyze"],
        version="1.0.0",
    )
    return server


@pytest.fixture
def http_client(agent_server):
    """Create FastAPI test client with registered agent."""
    app, transport = create_a2a_app()
    transport.register_agent(agent_server)
    return TestClient(app), transport


class TestA2AHTTPTransport:
    """Test A2A HTTP transport endpoints."""

    def test_health_check(self, http_client):
        """Test health check endpoint."""
        client, _ = http_client
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["agents"] >= 1

    def test_agent_info(self, http_client):
        """Test agent info endpoint."""
        client, _ = http_client
        response = client.get("/a2a/info?agent_id=test_agent")
        
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test_agent"
        assert data["agent_name"] == "TestAgent"
        assert "query" in data["capabilities"]
        assert "analyze" in data["capabilities"]
        assert data["version"] == "1.0.0"

    def test_agent_info_not_found(self, http_client):
        """Test agent info for non-existent agent."""
        client, _ = http_client
        response = client.get("/a2a/info?agent_id=nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_list_agents(self, http_client):
        """Test list agents endpoint."""
        client, _ = http_client
        response = client.get("/a2a/agents")
        
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "count" in data
        assert data["count"] >= 1
        
        # Verify test_agent is in list
        agent_ids = [a["agent_id"] for a in data["agents"]]
        assert "test_agent" in agent_ids

    def test_call_agent_success(self, http_client):
        """Test calling agent via A2A protocol."""
        client, _ = http_client
        
        payload = {
            "agent_id": "test_agent",
            "context": {"user": "test_user", "repo": "test_repo"},
            "params": {"query": "test query"},
        }
        
        response = client.post("/a2a/call", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["agent_id"] == "test_agent"
        assert data["result"]["agent"] == "mock_agent"
        assert data["result"]["query"] == "test query"
        assert "timestamp" in data

    def test_call_agent_missing_id(self, http_client):
        """Test calling agent without agent_id."""
        client, _ = http_client
        
        payload = {
            "context": {"user": "test"},
            "params": {"query": "test"},
        }
        
        response = client.post("/a2a/call", json=payload)
        
        assert response.status_code == 400
        assert "Missing 'agent_id'" in response.json()["detail"]

    def test_call_agent_not_found(self, http_client):
        """Test calling non-existent agent."""
        client, _ = http_client
        
        payload = {
            "agent_id": "nonexistent",
            "context": {},
            "params": {"query": "test"},
        }
        
        response = client.post("/a2a/call", json=payload)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_call_agent_invalid_json(self, http_client):
        """Test calling agent with invalid JSON."""
        client, _ = http_client
        
        response = client.post(
            "/a2a/call",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )
        
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_agent_stats(self, http_client):
        """Test agent statistics endpoint."""
        client, _ = http_client
        
        # Make a call first
        payload = {
            "agent_id": "test_agent",
            "context": {},
            "params": {"query": "test"},
        }
        client.post("/a2a/call", json=payload)
        
        # Get stats
        response = client.get("/a2a/stats/test_agent")
        
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test_agent"
        assert data["total_calls"] >= 1
        assert data["successful_calls"] >= 1
        assert "last_call_at" in data

    def test_agent_stats_not_found(self, http_client):
        """Test stats for non-existent agent."""
        client, _ = http_client
        response = client.get("/a2a/stats/nonexistent")
        
        assert response.status_code == 404


class TestA2AMultipleAgents:
    """Test A2A transport with multiple agents."""

    @pytest.fixture
    async def agent_1(self):
        """First test agent."""
        async def agent_func(context: dict, **kwargs):
            return {"agent": "agent_1", "context": context}
        
        return AgentServer(
            agent_id="agent_1",
            agent_name="Agent1",
            agent_callable=agent_func,
            capabilities=["analyze"],
        )

    @pytest.fixture
    async def agent_2(self):
        """Second test agent."""
        async def agent_func(context: dict, **kwargs):
            return {"agent": "agent_2", "context": context}
        
        return AgentServer(
            agent_id="agent_2",
            agent_name="Agent2",
            agent_callable=agent_func,
            capabilities=["generate"],
        )

    def test_multiple_agents_registration(self, agent_1, agent_2):
        """Test registering and calling multiple agents."""
        app, transport = create_a2a_app()
        transport.register_agent(agent_1)
        transport.register_agent(agent_2)
        
        client = TestClient(app)
        
        # List agents
        response = client.get("/a2a/agents")
        assert response.status_code == 200
        assert response.json()["count"] == 2
        
        # Call agent 1
        response = client.post("/a2a/call", json={
            "agent_id": "agent_1",
            "context": {"test": "data"},
            "params": {},
        })
        assert response.status_code == 200
        assert response.json()["result"]["agent"] == "agent_1"
        
        # Call agent 2
        response = client.post("/a2a/call", json={
            "agent_id": "agent_2",
            "context": {"test": "data"},
            "params": {},
        })
        assert response.status_code == 200
        assert response.json()["result"]["agent"] == "agent_2"
